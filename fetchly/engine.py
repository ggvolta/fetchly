"""Download engine.

HTTP downloads use IDM-style *dynamic segmentation*: the file is split into N ranges, each
fetched over its own connection. Whenever a connection finishes its range, the largest range
still in progress is split in half and the free connection takes the second half, so every
connection stays busy until the very end. Progress is persisted per segment, so downloads
resume after a pause, a crash, or a restart of the app.

HLS (.m3u8) streams are downloaded segment-by-segment in parallel and joined (optionally
remuxed to MP4 when ffmpeg is installed).
"""
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.parse

import requests

from .models import COMPLETE, DOWNLOADING, ERROR, PAUSED, Segment
from .utils import filename_from_cd, filename_from_url, guess_ext, is_hls_url, sanitize_filename, unique_path

DEFAULT_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")
CHUNK = 64 * 1024
MIN_SPLIT = 512 * 1024        # never create a piece smaller than this
MAX_RETRIES = 10
TIMEOUT = (15, 30)            # connect, read
FATAL_HTTP = {400, 401, 403, 404, 405, 410, 451}
PROXY = ""   # set by the manager from settings; "" = system proxy


class StopRequested(Exception):
    pass


class DownloadError(Exception):
    def __init__(self, msg, fatal=False):
        super().__init__(msg)
        self.fatal = fatal


class RateLimiter:
    """Token bucket shared between threads. rate = bytes/sec, 0 = unlimited."""

    def __init__(self, rate=0):
        self.rate = rate
        self.lock = threading.Lock()
        self.allowance = 0.0
        self.last = time.monotonic()

    def set_rate(self, rate):
        with self.lock:
            self.rate = max(0, int(rate))
            self.allowance = 0.0
            self.last = time.monotonic()

    def consume(self, n, stop_event=None):
        while True:
            with self.lock:
                if self.rate <= 0:
                    return
                now = time.monotonic()
                self.allowance = min(self.rate, self.allowance + (now - self.last) * self.rate)
                self.last = now
                if self.allowance >= 0:
                    self.allowance -= n
                    return
                wait = -self.allowance / self.rate
            time.sleep(min(wait, 0.25))
            if stop_event is not None and stop_event.is_set():
                return


def make_session(url, referrer="", cookies="", user_agent="", auth=None):
    s = requests.Session()
    s.headers.update({"User-Agent": user_agent or DEFAULT_UA, "Accept": "*/*",
                      "Accept-Encoding": "identity", "Connection": "keep-alive"})
    if referrer:
        s.headers["Referer"] = referrer
    if cookies:
        # Scope the browser cookies to the original host so they never leak to redirect targets.
        host = urllib.parse.urlsplit(url).hostname or ""
        for part in cookies.split(";"):
            if "=" in part:
                k, v = part.split("=", 1)
                s.cookies.set(k.strip(), v.strip(), domain=host)
    if auth and auth[0]:
        s.auth = (auth[0], auth[1] or "")
    if PROXY:
        s.proxies = {"http": PROXY, "https": PROXY}
    return s


def item_session(item):
    return make_session(item.url, item.referrer, item.cookies, item.user_agent,
                        (item.auth_user, item.auth_pass) if item.auth_user else None)


def open_probe(session, url):
    """First request: learn size, resume support, filename and final URL. Returns (info, response) with the
    response still open, so the caller can keep downloading from it (no wasted round trip)."""
    r = session.get(url, headers={"Range": "bytes=0-"}, stream=True, timeout=TIMEOUT, allow_redirects=True)
    if r.status_code >= 400:
        r.close()
        raise DownloadError(f"HTTP {r.status_code} {r.reason}", fatal=r.status_code in FATAL_HTTP)
    size, resumable = -1, False
    if r.status_code == 206:
        m = re.match(r"bytes\s+(\d+)-\d+/(\d+)", r.headers.get("Content-Range", ""))
        if m:
            size, resumable = int(m.group(2)), True
            if int(m.group(1)) != 0:
                r.close()
                r = None
    else:
        cl = r.headers.get("Content-Length", "")
        size = int(cl) if cl.isdigit() else -1
        resumable = "bytes" in r.headers.get("Accept-Ranges", "").lower() and size > 0
    hdrs = r.headers if r is not None else {}
    ct = hdrs.get("Content-Type", "").split(";")[0].strip().lower()
    final = r.url if r is not None else url
    name = filename_from_cd(hdrs.get("Content-Disposition")) or filename_from_url(final) or filename_from_url(url)
    if name and not os.path.splitext(name)[1]:
        name += guess_ext(ct)
    if not name:
        name = "download" + guess_ext(ct)
    info = {"size": size, "resumable": resumable, "filename": name, "final_url": final,
            "content_type": ct, "hls": is_hls_url(final, ct), "status": r.status_code if r is not None else 206}
    return info, r


def probe(session, url):
    info, r = open_probe(session, url)
    if r is not None:
        r.close()
    return info


class Downloader:
    """Runs one DownloadItem on background threads."""

    def __init__(self, item, global_limiter, on_done, dir_for=None):
        self.item = item
        self.dir_for = dir_for
        self.glimit = global_limiter
        self.ilimit = RateLimiter(item.speed_limit_kb * 1024)
        self.on_done = on_done
        self.stop_event = threading.Event()
        self.lock = threading.Lock()
        self.fatal = None
        self.workers = []
        self.dl_url = item.url
        self.hls_status = {}
        self.wake = threading.Event()
        self.max_conn = 1
        self.resumable = False
        self.thread = threading.Thread(target=self._run, daemon=True, name=f"fetchly-{item.id}")

    # ---- control -------------------------------------------------------
    def start(self):
        self.thread.start()

    def stop(self):
        self.stop_event.set()

    def is_alive(self):
        return self.thread.is_alive()

    def join(self, timeout=None):
        self.thread.join(timeout)

    def set_item_limit(self, kb):
        self.item.speed_limit_kb = kb
        self.ilimit.set_rate(kb * 1024)

    def connections(self):
        """[(label, received_bytes, info)] for the progress window."""
        it = self.item
        if it.kind == "hls":
            return [(str(k + 1), v[0], v[1]) for k, v in sorted(self.hls_status.items())]
        out = []
        segs = sorted(list(it.segments), key=lambda s: s.start)
        for i, s in enumerate(segs):
            if s.active or (not s.finished and s.info):
                out.append((str(i + 1), s.received, s.info))
        return out

    # ---- main ----------------------------------------------------------
    def _run(self):
        it = self.item
        it.status = DOWNLOADING
        it.last_try = time.time()
        it.error = ""
        result = "paused"
        try:
            if it.kind == "hls":
                self._run_hls()
            else:
                self._run_http()
            it.status = COMPLETE
            it.completed_at = time.time()
            result = "complete"
        except StopRequested:
            it.status = PAUSED
        except Exception as e:  # noqa: BLE001 - surface any failure to the UI
            it.status = ERROR
            it.error = friendly_error(e)
            result = "error"
        finally:
            for s in list(it.segments):
                s.active = False
            self.on_done(self, result)

    def _check_stop(self):
        if self.stop_event.is_set():
            raise StopRequested()

    # ---- HTTP ----------------------------------------------------------
    def _run_http(self):
        it = self.item
        sess = item_session(it)
        info, first = open_probe(sess, it.url)
        try:
            self._check_stop()
            if info["hls"] and not it.segments:
                it.kind = "hls"
                if first is not None:
                    first.close()
                return self._run_hls()
            self.dl_url = info["final_url"]
            if not it.filename:
                it.filename = sanitize_filename(info["filename"])
            self._resolve_dir()

            can_resume = (bool(it.segments) and it.resumable and info["resumable"] and info["size"] == it.size
                          and it.part_path and os.path.exists(it.part_path))
            if not can_resume:
                it.size, it.resumable = info["size"], info["resumable"]
                os.makedirs(it.save_dir, exist_ok=True)
                if not it.part_path:
                    it.part_path = unique_path(os.path.join(it.save_dir, it.filename + ".fetchlypart"))
                with open(it.part_path, "wb") as f:
                    if it.size > 0 and it.resumable:
                        f.truncate(it.size)
                if it.resumable and it.size > 0:
                    n = max(1, min(it.max_connections, it.size // MIN_SPLIT))
                    step = it.size // n
                    it.segments = [Segment(i * step, (i + 1) * step - 1 if i < n - 1 else it.size - 1)
                                   for i in range(n)]
                else:
                    it.segments = [Segment(0, it.size - 1 if it.size > 0 else -1)]

            self.ilimit.set_rate(it.speed_limit_kb * 1024)
            self.max_conn = max(1, it.max_connections) if it.resumable else 1
            self.resumable = it.resumable

            # Connection 1 keeps receiving on the probe's response (like IDM) when it starts at byte 0.
            seg0 = next((sg for sg in it.segments if sg.start == 0 and sg.pos == 0 and not sg.finished), None)
            if first is not None and seg0 is not None and (it.resumable or info["status"] == 200):
                seg0.active = True
                self._spawn(seg0, sess, first)
                first = None
        finally:
            if first is not None:
                first.close()

        while not self.stop_event.is_set():
            with self.lock:
                if all(sg.finished for sg in it.segments) or self.fatal:
                    break
                self.workers = [t for t in self.workers if t.is_alive()]
                n_workers = len(self.workers)
            while n_workers < self.max_conn:
                seg = self._next_job()
                if not seg:
                    break
                self._spawn(seg)
                n_workers += 1
            self.wake.wait(0.1)
            self.wake.clear()

        if self.fatal:
            self.stop_event.set()
        for t in list(self.workers):
            t.join()
        if self.fatal:
            raise DownloadError(str(self.fatal))
        if self.stop_event.is_set():
            raise StopRequested()
        self._finalize_http()

    def _resolve_dir(self):
        it = self.item
        if it.auto_dir and it.filename and self.dir_for:
            from .utils import category_for
            it.category = category_for(it.filename)
            it.save_dir = self.dir_for(it.category)
        it.auto_dir = False

    def _next_job(self):
        """Give a free connection something to do: a waiting piece, or half of the largest remaining one."""
        it = self.item
        with self.lock:
            now = time.monotonic()
            for sg in it.segments:
                if not sg.finished and not sg.active and sg.retry_at <= now:
                    sg.active = True
                    return sg
            if not self.resumable:
                return None
            best, best_rem = None, 0
            for sg in it.segments:
                if sg.finished or sg.end < 0:
                    continue
                rem = sg.end - sg.pos + 1
                if rem > best_rem:
                    best, best_rem = sg, rem
            if not best or best_rem < 2 * MIN_SPLIT:
                return None
            mid = best.pos + best_rem // 2
            new = Segment(mid, best.end)
            best.end = mid - 1
            new.active = True
            it.segments.append(new)
            return new

    def _spawn(self, seg, sess=None, response=None):
        seg.active = True
        seg.info = "Connecting..." if response is None else "Receiving data..."
        t = threading.Thread(target=self._worker, args=(seg, sess, response), daemon=True)
        self.workers.append(t)
        t.start()

    def _worker(self, seg, sess=None, response=None):
        """One connection. Keeps its keep-alive connection open and takes the next piece when done."""
        sess = sess or item_session(self.item)
        try:
            while seg is not None and not self.stop_event.is_set() and not self.fatal:
                ok = self._download_segment(sess, seg, response)
                response = None
                seg.active = False
                if not ok:
                    return
                seg = self._next_job()
        finally:
            if seg is not None:
                seg.active = False
            self.wake.set()

    def _download_segment(self, sess, seg, response=None):
        it = self.item
        try:
            r = response
            if r is None:
                headers = {}
                if not it.resumable:
                    with self.lock:
                        seg.pos = seg.start  # cannot continue mid-file: start over
                elif seg.end >= 0:
                    headers["Range"] = f"bytes={seg.pos}-{seg.end}"
                seg.info = "Connecting..."
                r = sess.get(self.dl_url, headers=headers, stream=True, timeout=TIMEOUT)
            try:
                if r.status_code >= 400:
                    raise DownloadError(f"HTTP {r.status_code} {r.reason}", fatal=r.status_code in FATAL_HTTP)
                if it.resumable and r.status_code != 206 and seg.pos != 0:
                    raise DownloadError("Server stopped accepting resume requests")
                seg.info = "Receiving data..."
                with open(it.part_path, "r+b") as f:
                    for chunk in r.raw.stream(CHUNK, decode_content=False):
                        if self.stop_event.is_set():
                            break
                        if not chunk:
                            continue
                        self.glimit.consume(len(chunk), self.stop_event)
                        self.ilimit.consume(len(chunk), self.stop_event)
                        with self.lock:
                            n = len(chunk) if seg.end < 0 else min(len(chunk), seg.end - seg.pos + 1)
                            if n <= 0:
                                break
                            off = seg.pos
                            seg.pos += n
                        try:
                            f.seek(off)
                            f.write(chunk if n == len(chunk) else memoryview(chunk)[:n])
                        except OSError:
                            with self.lock:
                                seg.pos = off
                            raise
                        if seg.end >= 0 and seg.pos > seg.end:
                            break
            finally:
                # Fully read -> hand the keep-alive connection back for the next piece; otherwise drop it.
                if getattr(r.raw, "length_remaining", None) == 0 and not self.stop_event.is_set():
                    r.raw.release_conn()
                else:
                    r.close()
            if self.stop_event.is_set():
                seg.info = "Paused"
                return False
            if seg.end < 0:
                seg.done = True
            elif seg.pos <= seg.end:
                raise DownloadError("Connection closed by server")
            seg.info = ""
            seg.retries = 0
            return True
        except requests.RequestException as e:
            self._seg_failed(seg, DownloadError(friendly_error(e)))
        except DownloadError as e:
            self._seg_failed(seg, e)
        except OSError as e:  # disk errors are not worth retrying
            self.fatal = DownloadError(f"Disk error: {e}")
            seg.info = "Disk error"
        return False

    def _seg_failed(self, seg, err):
        seg.retries += 1
        seg.info = f"Error: {err}"
        if err.fatal or seg.retries > MAX_RETRIES:
            self.fatal = err
        else:
            seg.retry_at = time.monotonic() + min(2 ** seg.retries, 30)

    def _finalize_http(self):
        it = self.item
        total = sum(s.pos - s.start for s in it.segments)
        if it.size > 0 and total < it.size:
            raise DownloadError("Download incomplete")
        if it.size <= 0:
            with open(it.part_path, "r+b") as f:
                f.truncate(total)
            it.size = total
        target = os.path.join(it.save_dir, it.filename)
        if not it.overwrite:
            target = unique_path(target)
        os.replace(it.part_path, target)
        it.saved_path = target
        it.filename = os.path.basename(target)
        it.part_path = ""

    # ---- HLS -----------------------------------------------------------
    def _get_text(self, sess, url):
        r = sess.get(url, timeout=TIMEOUT)
        if r.status_code >= 400:
            raise DownloadError(f"HTTP {r.status_code} {r.reason}", fatal=r.status_code in FATAL_HTTP)
        return r.text, r.url

    def _run_hls(self):
        it = self.item
        sess = item_session(it)
        text, url = self._get_text(sess, it.url)
        if "#EXTM3U" not in text:
            raise DownloadError("Not a valid HLS playlist", fatal=True)
        if "#EXT-X-STREAM-INF" in text:
            variants = parse_master(text, url)
            if not variants:
                raise DownloadError("No playable variants in playlist", fatal=True)
            text, url = self._get_text(sess, max(variants)[1])  # best quality
        segs, init_url = parse_media(text, url)
        if not segs:
            raise DownloadError("Playlist has no segments", fatal=True)
        self._check_stop()

        stem = os.path.splitext(it.filename)[0] if it.filename else "video"
        it.filename = sanitize_filename(stem + (".mp4" if init_url else ".ts"))
        self._resolve_dir()
        os.makedirs(it.save_dir, exist_ok=True)
        if not it.part_path or not os.path.isdir(it.part_path):
            it.part_path = unique_path(os.path.join(it.save_dir, stem + ".fetchlyhls"))
            it.hls_done, it.hls_bytes = [], 0
            os.makedirs(it.part_path, exist_ok=True)
        if it.hls_total != len(segs):
            it.hls_done, it.hls_bytes = [], 0
        it.hls_total = len(segs)
        self.ilimit.set_rate(it.speed_limit_kb * 1024)

        keys = {}
        done = set(it.hls_done)
        pending = [i for i in range(len(segs)) if i not in done]
        plock = threading.Lock()

        def key_for(k):
            if k["uri"] not in keys:
                r = sess.get(k["uri"], timeout=TIMEOUT)
                r.raise_for_status()
                keys[k["uri"]] = r.content
            return keys[k["uri"]]

        def worker(wid):
            ws = item_session(it)
            while not self.stop_event.is_set() and not self.fatal:
                with plock:
                    if not pending:
                        self.hls_status.pop(wid, None)
                        return
                    i = pending.pop(0)
                seg = segs[i]
                for attempt in range(MAX_RETRIES):
                    try:
                        self.hls_status[wid] = (0, f"Segment {i + 1}/{len(segs)}")
                        data = self._fetch_bytes(ws, seg["url"], wid, i, len(segs))
                        if data is None:
                            return  # stopped
                        if seg["key"]:
                            iv = seg["key"]["iv"]
                            iv = bytes.fromhex(iv[2:].zfill(32)) if iv else seg["seq"].to_bytes(16, "big")
                            data = aes128_decrypt(data, key_for(seg["key"]), iv)
                        path = os.path.join(it.part_path, f"{i:06d}.seg")
                        with open(path + ".tmp", "wb") as f:
                            f.write(data)
                        os.replace(path + ".tmp", path)
                        with plock:
                            it.hls_done.append(i)
                            it.hls_bytes += len(data)
                        break
                    except DownloadError as e:
                        if e.fatal:
                            self.fatal = e
                            return
                        time.sleep(min(2 ** attempt, 15))
                    except requests.RequestException as e:
                        self.hls_status[wid] = (0, f"Error: {_short(e)}")
                        time.sleep(min(2 ** attempt, 15))
                else:
                    self.fatal = DownloadError(f"Segment {i + 1} failed repeatedly")
                    return

        threads = [threading.Thread(target=worker, args=(w,), daemon=True)
                   for w in range(min(max(1, it.max_connections), len(pending) or 1))]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        if self.stop_event.is_set():
            raise StopRequested()
        if self.fatal:
            raise DownloadError(str(self.fatal))

        # join pieces
        target = os.path.join(it.save_dir, it.filename)
        if not it.overwrite:
            target = unique_path(target)
        tmp = target + ".fetchlypart"
        with open(tmp, "wb") as out:
            if init_url:
                r = sess.get(init_url, timeout=TIMEOUT)
                r.raise_for_status()
                out.write(r.content)
            for i in range(len(segs)):
                with open(os.path.join(it.part_path, f"{i:06d}.seg"), "rb") as f:
                    shutil.copyfileobj(f, out)
        os.replace(tmp, target)
        shutil.rmtree(it.part_path, ignore_errors=True)
        it.part_path = ""
        # Remux MPEG-TS to MP4 if ffmpeg is available (lossless, fast)
        if target.lower().endswith(".ts") and shutil.which("ffmpeg"):
            mp4 = unique_path(os.path.splitext(target)[0] + ".mp4")
            flags = 0x08000000 if sys.platform == "win32" else 0  # CREATE_NO_WINDOW
            try:
                res = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", target, "-c", "copy", mp4],
                                     capture_output=True, timeout=3600, creationflags=flags)
                if res.returncode == 0 and os.path.exists(mp4):
                    os.remove(target)
                    target = mp4
            except (OSError, subprocess.SubprocessError):
                pass
        it.saved_path = target
        it.filename = os.path.basename(target)
        it.size = os.path.getsize(target)

    def _fetch_bytes(self, sess, url, wid, i, total):
        r = sess.get(url, stream=True, timeout=TIMEOUT)
        try:
            if r.status_code >= 400:
                raise DownloadError(f"HTTP {r.status_code}", fatal=r.status_code in (401, 403, 404, 410))
            buf = bytearray()
            for chunk in r.raw.stream(CHUNK, decode_content=True):
                if self.stop_event.is_set():
                    return None
                self.glimit.consume(len(chunk), self.stop_event)
                self.ilimit.consume(len(chunk), self.stop_event)
                buf += chunk
                self.hls_status[wid] = (len(buf), f"Segment {i + 1}/{total} - receiving data...")
            return bytes(buf)
        finally:
            r.close()


# ---- HLS helpers -------------------------------------------------------
def _attrs(s):
    return {m.group(1).upper(): m.group(2).strip('"')
            for m in re.finditer(r'([A-Za-z0-9-]+)=("[^"]*"|[^,]*)', s)}


def parse_master(text, base):
    lines = [l.strip() for l in text.splitlines()]
    out = []
    for i, line in enumerate(lines):
        if line.startswith("#EXT-X-STREAM-INF"):
            bw = int(_attrs(line.split(":", 1)[1]).get("BANDWIDTH", "0") or 0)
            for nxt in lines[i + 1:]:
                if nxt and not nxt.startswith("#"):
                    out.append((bw, urllib.parse.urljoin(base, nxt)))
                    break
    return out


def parse_media(text, base):
    segs, key, seq, init = [], None, 0, None
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("#EXT-X-MEDIA-SEQUENCE:"):
            seq = int(line.split(":", 1)[1])
        elif line.startswith("#EXT-X-BYTERANGE"):
            raise DownloadError("Byte-range HLS playlists are not supported", fatal=True)
        elif line.startswith("#EXT-X-KEY:"):
            a = _attrs(line.split(":", 1)[1])
            method = a.get("METHOD", "NONE").upper()
            if method == "NONE":
                key = None
            elif method == "AES-128":
                key = {"uri": urllib.parse.urljoin(base, a.get("URI", "")), "iv": a.get("IV")}
            else:
                raise DownloadError("This stream is DRM-protected and can't be downloaded", fatal=True)
        elif line.startswith("#EXT-X-MAP:"):
            init = urllib.parse.urljoin(base, _attrs(line.split(":", 1)[1]).get("URI", ""))
        elif not line.startswith("#"):
            segs.append({"url": urllib.parse.urljoin(base, line), "key": key, "seq": seq + len(segs)})
    return segs, init


def aes128_decrypt(data, key, iv):
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    except ImportError as e:
        raise DownloadError("Encrypted stream: install the 'cryptography' package", fatal=True) from e
    d = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
    out = d.update(data) + d.finalize()
    pad = out[-1] if out else 0
    return out[:-pad] if 1 <= pad <= 16 else out


def friendly_error(e):
    """Turn network exceptions into short sentences a person can act on."""
    import urllib.parse as up
    if isinstance(e, DownloadError):
        return str(e)
    if isinstance(e, requests.RequestException):
        host = ""
        try:
            host = up.urlsplit(e.request.url).hostname or ""
        except AttributeError:
            pass
        where = f" {host}" if host else " the server"
        if isinstance(e, requests.exceptions.SSLError):
            return f"Secure connection to{where} failed"
        if isinstance(e, requests.exceptions.ProxyError):
            return "Couldn't connect through the proxy"
        if isinstance(e, (requests.exceptions.ConnectTimeout, requests.exceptions.ReadTimeout)):
            return f"{where.strip().capitalize()} stopped responding"
        if isinstance(e, requests.exceptions.ConnectionError):
            return f"Couldn't reach{where}. Check your internet connection"
        if isinstance(e, requests.exceptions.TooManyRedirects):
            return "Too many redirects"
        return _short(e)
    if isinstance(e, OSError) and e.strerror:
        return f"Disk error: {e.strerror}"
    return str(e) or e.__class__.__name__


def _short(e):
    s = str(e)
    if "timed out" in s.lower():
        return "Timed out"
    if "connection" in s.lower() and ("refused" in s.lower() or "reset" in s.lower() or "aborted" in s.lower()):
        return "Connection lost"
    return (s[:80] + "...") if len(s) > 80 else s
