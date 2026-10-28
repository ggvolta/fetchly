"""Download item and segment data structures."""
import time
import uuid

QUEUED = "queued"
DOWNLOADING = "downloading"
PAUSED = "paused"
COMPLETE = "complete"
ERROR = "error"


class Segment:
    """A byte range [start, end] downloaded by one connection. pos = next byte to write."""
    __slots__ = ("start", "end", "pos", "done", "active", "info", "retries", "retry_at")

    def __init__(self, start, end, pos=None, done=False):
        self.start = start
        self.end = end            # -1 = unknown (read until EOF)
        self.pos = start if pos is None else pos
        self.done = done
        self.active = False
        self.info = ""
        self.retries = 0
        self.retry_at = 0.0

    @property
    def finished(self):
        return self.done or (self.end >= 0 and self.pos > self.end)

    @property
    def received(self):
        return self.pos - self.start

    def to_dict(self):
        return {"start": self.start, "end": self.end, "pos": self.pos, "done": self.done}

    @classmethod
    def from_dict(cls, d):
        return cls(d["start"], d["end"], d.get("pos"), d.get("done", False))


class DownloadItem:
    SAVED = ("id", "url", "filename", "save_dir", "category", "size", "resumable", "status", "referrer",
             "cookies", "user_agent", "auth_user", "auth_pass", "description", "added", "last_try",
             "completed_at", "saved_path", "error", "in_queue", "max_connections", "speed_limit_kb",
             "kind", "part_path", "overwrite", "auto_dir", "hls_done", "hls_total", "hls_bytes", "queue_order")

    def __init__(self, url, filename="", save_dir="", category="General"):
        self.id = uuid.uuid4().hex[:12]
        self.url = url
        self.filename = filename
        self.save_dir = save_dir
        self.category = category
        self.size = -1
        self.resumable = None
        self.status = PAUSED
        self.segments = []
        self.referrer = ""
        self.cookies = ""
        self.user_agent = ""
        self.auth_user = ""
        self.auth_pass = ""
        self.description = ""
        self.added = time.time()
        self.last_try = 0.0
        self.completed_at = 0.0
        self.saved_path = ""
        self.error = ""
        self.in_queue = False
        self.max_connections = 8
        self.speed_limit_kb = 0
        self.kind = "http"          # "http" or "hls"
        self.part_path = ""
        self.overwrite = False
        self.auto_dir = False       # pick category/folder once the real filename is known
        self.hls_done = []
        self.hls_total = 0
        self.hls_bytes = 0
        self.queue_order = 0
        # runtime only
        self.speed = 0.0
        self.eta = -1
        self.open_when_done = False

    def downloaded(self):
        if self.kind == "hls":
            return self.hls_bytes
        if self.status == COMPLETE and self.size > 0:
            return self.size
        return sum(s.pos - s.start for s in list(self.segments))

    def progress(self):
        """0..1, or None when unknown."""
        if self.status == COMPLETE:
            return 1.0
        if self.kind == "hls":
            return (len(self.hls_done) / self.hls_total) if self.hls_total else None
        if self.size > 0:
            return min(1.0, self.downloaded() / self.size)
        return None

    @property
    def target_path(self):
        import os
        return self.saved_path or os.path.join(self.save_dir, self.filename)

    def to_dict(self):
        d = {k: getattr(self, k) for k in self.SAVED}
        d["segments"] = [s.to_dict() for s in list(self.segments)]
        return d

    @classmethod
    def from_dict(cls, d):
        it = cls(d.get("url", ""))
        for k in cls.SAVED:
            if k in d:
                setattr(it, k, d[k])
        it.segments = [Segment.from_dict(x) for x in d.get("segments", [])]
        if it.status == DOWNLOADING:
            it.status = PAUSED
        return it
