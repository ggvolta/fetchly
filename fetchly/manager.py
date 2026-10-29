"""Download list, queue, scheduler and persistence. Pure Python (no Qt) so it can be tested headless.

The UI calls tick() periodically and drains `events` (a queue of tuples) to react to changes.
"""
import collections
import datetime
import json
import os
import queue
import shutil
import threading
import time

from .config import app_data_dir
from .engine import Downloader, RateLimiter
from .models import COMPLETE, DOWNLOADING, ERROR, PAUSED, QUEUED, DownloadItem
from .utils import category_for, filename_from_url, is_hls_url, sanitize_filename


class DownloadManager:
    def __init__(self, settings, db_path=None):
        self.settings = settings
        self.items = collections.OrderedDict()
        self.downloaders = {}
        self.events = queue.Queue()
        self._finished = queue.Queue()
        self.glimit = RateLimiter()
        self.apply_speed_limit()
        self.queue_running = False
        self._queue_did_work = False
        self._samples = {}
        self._dirty = False
        self._last_save = 0.0
        self._last_sched = None
        self.extension_seen = 0.0      # last time the browser extension talked to us
        self.extension_browser = ""
        self.lock = threading.RLock()
        self.db_path = db_path or os.path.join(app_data_dir(), "downloads.json")
        self.load()

    # ---- persistence ---------------------------------------------------
    def load(self):
        try:
            with open(self.db_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for d in data.get("items", []):
                it = DownloadItem.from_dict(d)
                self.items[it.id] = it
        except (OSError, ValueError):
            pass

    def save(self):
        with self.lock:
            data = {"version": 1, "items": [it.to_dict() for it in self.items.values()]}
        tmp = self.db_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.replace(tmp, self.db_path)
        self._dirty = False
        self._last_save = time.monotonic()

    def mark_dirty(self):
        self._dirty = True

    # ---- settings ------------------------------------------------------
    def apply_speed_limit(self):
        s = self.settings
        self.glimit.set_rate(s.speed_limit_kb * 1024 if s.speed_limit_enabled else 0)
        from . import engine
        engine.PROXY = (s.proxy or "").strip()

    # ---- items ---------------------------------------------------------
    def find_by_url(self, url):
        for it in self.items.values():
            if it.url == url:
                return it
        return None

    def add(self, url, filename="", save_dir=None, category=None, referrer="", cookies="", user_agent="",
            description="", auth=None, kind=None, start=True, in_queue=False, overwrite=False,
            size=-1, resumable=None):
        filename = sanitize_filename(filename) if filename else ""
        auto_dir = not filename and not save_dir and not category
        guess = filename or filename_from_url(url)   # good first guess until the server tells us the real name
        category = category or category_for(guess)
        it = DownloadItem(url, filename, save_dir or self.settings.dir_for(category), category)
        it.referrer, it.cookies, it.user_agent, it.description = referrer, cookies, user_agent, description
        if auth:
            it.auth_user, it.auth_pass = auth
        it.kind = kind or ("hls" if is_hls_url(url) else "http")
        it.max_connections = self.settings.max_connections
        it.overwrite = overwrite
        it.auto_dir = auto_dir
        it.size = size if size is not None else -1
        it.resumable = resumable
        it.in_queue = in_queue
        it.queue_order = int(time.time() * 1000)
        it.status = QUEUED if in_queue else PAUSED
        with self.lock:
            self.items[it.id] = it
        self.mark_dirty()
        self.events.put(("added", it.id))
        if start:
            self.start(it.id)
        return it

    def start(self, item_id):
        with self.lock:
            it = self.items.get(item_id)
            if not it or item_id in self.downloaders or it.status == COMPLETE:
                return False
            it.status = DOWNLOADING
            d = Downloader(it, self.glimit, self._on_done, self.settings.dir_for, settings=self.settings)
            self.downloaders[item_id] = d
            self._samples[item_id] = collections.deque(maxlen=12)
        d.start()
        self.events.put(("started", item_id))
        self.mark_dirty()
        return True

    def stop(self, item_id):
        d = self.downloaders.get(item_id)
        if d:
            d.stop()
        else:
            it = self.items.get(item_id)
            if it and it.status == QUEUED:
                it.status = PAUSED
                self.mark_dirty()

    def stop_all(self):
        for d in list(self.downloaders.values()):
            d.stop()
        self.queue_running = False

    def set_item_speed_limit(self, item_id, kb):
        it = self.items.get(item_id)
        if not it:
            return
        it.speed_limit_kb = kb
        d = self.downloaders.get(item_id)
        if d:
            d.set_item_limit(kb)
        self.mark_dirty()

    def remove(self, ids, delete_files=False):
        for item_id in ids:
            d = self.downloaders.get(item_id)
            if d:
                d.stop()
                d.join(5)
            with self.lock:
                it = self.items.pop(item_id, None)
                self.downloaders.pop(item_id, None)
            if not it:
                continue
            self._remove_partials(it)
            if delete_files and it.status == COMPLETE and it.saved_path and os.path.isfile(it.saved_path):
                try:
                    os.remove(it.saved_path)
                except OSError:
                    pass
            self.events.put(("removed", item_id))
        self.mark_dirty()

    def _remove_partials(self, it):
        p = it.part_path
        if not p:
            return
        try:
            if os.path.isdir(p):
                shutil.rmtree(p, ignore_errors=True)
            elif os.path.isfile(p):
                os.remove(p)
        except OSError:
            pass

    def remove_completed(self):
        ids = [i for i, it in self.items.items() if it.status == COMPLETE]
        self.remove(ids)
        return len(ids)

    def redownload(self, item_id):
        it = self.items.get(item_id)
        if not it or item_id in self.downloaders:
            return
        self._remove_partials(it)
        it.segments, it.hls_done, it.hls_bytes, it.hls_total = [], [], 0, 0
        it.part_path = it.saved_path = ""
        it.size, it.resumable, it.error = -1, None, ""
        it.status = PAUSED
        self.start(item_id)

    def update_address(self, item_id, url):
        it = self.items.get(item_id)
        if it and url and url != it.url:
            it.url = url
            if it.status == ERROR:
                it.status = PAUSED
            self.mark_dirty()

    # ---- queue ---------------------------------------------------------
    def queue_items(self):
        return sorted((it for it in self.items.values() if it.in_queue), key=lambda x: x.queue_order)

    def set_in_queue(self, ids, flag):
        base = int(time.time() * 1000)
        for n, i in enumerate(ids):
            it = self.items.get(i)
            if it:
                it.in_queue = flag
                if flag:
                    it.queue_order = base + n
                    if it.status in (PAUSED, ERROR) and i not in self.downloaders:
                        it.status = QUEUED
                elif it.status == QUEUED:
                    it.status = PAUSED
        self.mark_dirty()

    def move_in_queue(self, item_id, delta):
        q = self.queue_items()
        idx = next((n for n, it in enumerate(q) if it.id == item_id), None)
        if idx is None:
            return
        j = idx + delta
        if 0 <= j < len(q):
            q[idx].queue_order, q[j].queue_order = q[j].queue_order, q[idx].queue_order
            self.mark_dirty()

    def start_queue(self):
        self.queue_running = True
        self._queue_did_work = False
        for it in self.queue_items():
            if it.status in (PAUSED, ERROR) and it.id not in self.downloaders:
                it.status = QUEUED
        self.events.put(("queue_started",))

    def stop_queue(self):
        self.queue_running = False
        for it in self.queue_items():
            d = self.downloaders.get(it.id)
            if d:
                d.stop()
            elif it.status == QUEUED:
                it.status = PAUSED
        self.events.put(("queue_stopped",))

    def _process_queue(self):
        if not self.queue_running:
            return
        q = self.queue_items()
        active = [it for it in q if it.id in self.downloaders]
        waiting = [it for it in q if it.id not in self.downloaders and it.status == QUEUED]
        slots = max(1, self.settings.max_simultaneous) - len(active)
        for it in waiting[:max(0, slots)]:
            self._queue_did_work = True
            self.start(it.id)
        if not active and not waiting:
            self.queue_running = False
            self.events.put(("queue_done", self.settings.scheduler.get("on_done", "none")
                             if self._queue_did_work else "none"))

    def _check_scheduler(self):
        sch = self.settings.scheduler
        if not sch.get("enabled") and not sch.get("stop_enabled"):
            return
        now = datetime.datetime.now()
        key = now.strftime("%Y%m%d%H%M")
        if key == self._last_sched:
            return
        self._last_sched = key
        hm = now.strftime("%H:%M")
        if now.weekday() not in sch.get("days", list(range(7))):
            return
        if sch.get("enabled") and hm == sch.get("start_time") and not self.queue_running:
            self.start_queue()
            if sch.get("once"):
                sch["enabled"] = False
        if sch.get("stop_enabled") and hm == sch.get("stop_time") and self.queue_running:
            self.stop_queue()

    # ---- engine callbacks / periodic work ------------------------------
    def _on_done(self, downloader, result):
        self._finished.put((downloader.item.id, result))

    def tick(self):
        """Call ~twice a second from the UI thread."""
        while True:
            try:
                item_id, result = self._finished.get_nowait()
            except queue.Empty:
                break
            with self.lock:
                self.downloaders.pop(item_id, None)
            it = self.items.get(item_id)
            if it:
                it.speed, it.eta = 0.0, -1
            self._samples.pop(item_id, None)
            self.events.put((result, item_id))
            self.mark_dirty()

        now = time.monotonic()
        for item_id, d in list(self.downloaders.items()):
            it = d.item
            samples = self._samples.setdefault(item_id, collections.deque(maxlen=12))
            samples.append((now, it.downloaded()))
            if len(samples) >= 2 and samples[-1][0] - samples[0][0] > 0.2:
                (t0, b0), (t1, b1) = samples[0], samples[-1]
                it.speed = max(0.0, (b1 - b0) / (t1 - t0))
            if it.speed > 0 and it.size > 0 and it.kind != "hls":
                it.eta = (it.size - it.downloaded()) / it.speed
            elif it.speed > 0 and it.kind == "hls" and it.hls_total and it.hls_done:
                avg = it.hls_bytes / len(it.hls_done)
                it.eta = avg * (it.hls_total - len(it.hls_done)) / it.speed
            else:
                it.eta = -1

        self._process_queue()
        self._check_scheduler()
        if (self._dirty or self.downloaders) and now - self._last_save > 3:
            try:
                self.save()
            except OSError:
                pass

    def active_count(self):
        return len(self.downloaders)

    def total_speed(self):
        return sum(d.item.speed for d in self.downloaders.values())

    def shutdown(self):
        for d in list(self.downloaders.values()):
            d.stop()
        for d in list(self.downloaders.values()):
            d.join(5)
        self.tick()
        self.save()
