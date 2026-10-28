"""Engine tests against a local test server. Run:  python -m tests.test_engine"""
import hashlib
import os
import re
import shutil
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["FETCHLY_DATA_DIR"] = tempfile.mkdtemp(prefix="fetchly-data-")

from fetchly.config import Settings  # noqa: E402
from fetchly.manager import DownloadManager  # noqa: E402
from fetchly.models import COMPLETE, ERROR, PAUSED  # noqa: E402

DATA = os.urandom(9 * 1024 * 1024 + 12345)
SEGS = [os.urandom(200_000 + i * 1000) for i in range(12)]
KEY = os.urandom(16)
STATS = {"range_requests": 0, "max_parallel": 0, "parallel": 0}
LOCK = threading.Lock()
THROTTLE = {"delay": 0.0}


def _encrypt(data, seq):
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    pad = 16 - len(data) % 16
    e = Cipher(algorithms.AES(KEY), modes.CBC(seq.to_bytes(16, "big"))).encryptor()
    return e.update(data + bytes([pad]) * pad) + e.finalize()


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def _send(self, code, body, headers=None):
        self.send_response(code)
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self._write(body)

    def _write(self, body):
        with LOCK:
            STATS["parallel"] += 1
            STATS["max_parallel"] = max(STATS["max_parallel"], STATS["parallel"])
        try:
            for i in range(0, len(body), 32768):
                self.wfile.write(body[i:i + 32768])
                if THROTTLE["delay"]:
                    time.sleep(THROTTLE["delay"] * (4 if getattr(self, "_slow", False) else 1))
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            with LOCK:
                STATS["parallel"] -= 1

    def do_GET(self):
        p = self.path
        if p.startswith("/file.bin"):
            rng = self.headers.get("Range")
            hdr = {"Accept-Ranges": "bytes", "Content-Type": "application/octet-stream",
                   "Content-Disposition": 'attachment; filename="Big File.bin"'}
            if rng:
                m = re.match(r"bytes=(\d+)-(\d*)", rng)
                a = int(m.group(1))
                b = int(m.group(2)) if m.group(2) else len(DATA) - 1
                with LOCK:
                    STATS["range_requests"] += 1
                hdr["Content-Range"] = f"bytes {a}-{b}/{len(DATA)}"
                self._slow = a > len(DATA) // 2   # second half is slower -> forces re-splitting
                return self._send(206, DATA[a:b + 1], hdr)
            return self._send(200, DATA, hdr)
        if p.startswith("/norange.zip"):
            return self._send(200, DATA[:3_000_000], {"Content-Type": "application/zip"})
        if p.startswith("/chunked.dat"):
            self.send_response(200)
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()
            body = DATA[:1_500_000]
            for i in range(0, len(body), 100_000):
                c = body[i:i + 100_000]
                self.wfile.write(f"{len(c):x}\r\n".encode() + c + b"\r\n")
            self.wfile.write(b"0\r\n\r\n")
            return
        if p == "/redirect":
            self.send_response(302)
            self.send_header("Location", "/file.bin?token=abc")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if p == "/missing.zip":
            return self._send(404, b"nope")
        if p == "/hls/master.m3u8":
            body = ("#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=500000\nlow.m3u8\n"
                    "#EXT-X-STREAM-INF:BANDWIDTH=2000000\nhigh.m3u8\n").encode()
            return self._send(200, body, {"Content-Type": "application/vnd.apple.mpegurl"})
        if p == "/hls/high.m3u8":
            lines = ["#EXTM3U", "#EXT-X-MEDIA-SEQUENCE:0", '#EXT-X-KEY:METHOD=AES-128,URI="key.bin"']
            for i in range(len(SEGS)):
                lines += ["#EXTINF:4.0,", f"seg{i}.ts"]
            lines.append("#EXT-X-ENDLIST")
            return self._send(200, "\n".join(lines).encode(), {"Content-Type": "application/vnd.apple.mpegurl"})
        if p == "/hls/key.bin":
            return self._send(200, KEY)
        m = re.match(r"/hls/seg(\d+)\.ts", p)
        if m:
            i = int(m.group(1))
            return self._send(200, _encrypt(SEGS[i], i), {"Content-Type": "video/mp2t"})
        self._send(404, b"")


def wait(mgr, item_id, timeout=60, until=(COMPLETE, ERROR)):
    t0 = time.time()
    while time.time() - t0 < timeout:
        mgr.tick()
        it = mgr.items[item_id]
        if it.status in until and item_id not in mgr.downloaders:
            return it
        time.sleep(0.1)
    raise TimeoutError(f"{item_id} still {mgr.items[item_id].status}")


def sha(b):
    return hashlib.sha256(b).hexdigest()


def main():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    out = tempfile.mkdtemp(prefix="fetchly-out-")
    s = Settings()
    s.download_root = out
    mgr = DownloadManager(s)
    ok = True

    def check(name, cond, extra=""):
        nonlocal ok
        ok &= bool(cond)
        print(("PASS " if cond else "FAIL ") + name + (f"  ({extra})" if extra else ""))

    # 1. multi-connection download with dynamic segmentation
    THROTTLE["delay"] = 0.002
    s.max_connections = 4
    it = mgr.add(base + "/file.bin", start=True)
    it = wait(mgr, it.id)
    data = open(it.saved_path, "rb").read() if it.status == COMPLETE else b""
    check("segmented download completes with correct data", it.status == COMPLETE and sha(data) == sha(DATA),
          it.error)
    check("filename taken from Content-Disposition", it.filename == "Big File.bin", it.filename)
    check("multiple parallel connections used", STATS["max_parallel"] >= 4, f"max {STATS['max_parallel']}")
    check("dynamic re-splitting happened", len(it.segments) > 4, f"{len(it.segments)} segments")
    s.max_connections = 8

    # 2. pause + resume (also across a new manager instance = app restart)
    THROTTLE["delay"] = 0.08
    it = mgr.add(base + "/file.bin", filename="resume.bin", start=True)
    time.sleep(1.0)
    mgr.stop(it.id)
    wait(mgr, it.id, until=(PAUSED,))
    got = it.downloaded()
    check("pause keeps partial progress", 0 < got < len(DATA), f"{got} bytes")
    mgr.save()
    mgr2 = DownloadManager(s)
    it2 = mgr2.items[it.id]
    check("progress persisted to disk", it2.downloaded() == got)
    before = STATS["range_requests"]
    THROTTLE["delay"] = 0.0
    mgr2.start(it2.id)
    it2 = wait(mgr2, it2.id)
    check("resume completes with correct data",
          it2.status == COMPLETE and sha(open(it2.saved_path, "rb").read()) == sha(DATA), it2.error)
    check("resume used range requests", STATS["range_requests"] > before)
    mgr = mgr2

    # 3. speed limiter
    s.speed_limit_enabled, s.speed_limit_kb = True, 1024
    mgr.apply_speed_limit()
    it = mgr.add(base + "/file.bin", filename="limited.bin", start=True)
    time.sleep(3)
    mgr.tick()
    rate = it.downloaded() / 3 / 1024
    mgr.stop(it.id)
    wait(mgr, it.id, until=(PAUSED,))
    check("global speed limit respected (~1024 KB/s)", 600 < rate < 1500, f"{rate:.0f} KB/s")
    s.speed_limit_enabled = False
    mgr.apply_speed_limit()

    # 4. server without range support, chunked, redirects, 404
    it = wait(mgr, mgr.add(base + "/norange.zip").id)
    check("non-resumable server works", it.status == COMPLETE and it.resumable is False
          and sha(open(it.saved_path, "rb").read()) == sha(DATA[:3_000_000]), it.error)
    check("category auto-detected (Compressed)", it.category == "Compressed" and "Compressed" in it.saved_path)
    it = wait(mgr, mgr.add(base + "/chunked.dat").id)
    check("unknown-size (chunked) download works", it.status == COMPLETE
          and sha(open(it.saved_path, "rb").read()) == sha(DATA[:1_500_000]), it.error)
    it = wait(mgr, mgr.add(base + "/redirect", filename="redir.bin").id)
    check("redirected download works", it.status == COMPLETE and os.path.getsize(it.saved_path) == len(DATA))
    it = wait(mgr, mgr.add(base + "/missing.zip").id)
    check("404 reported as error", it.status == ERROR and "404" in it.error, it.error)

    # 5. HLS master -> best variant, AES-128 decrypt, join
    it = wait(mgr, mgr.add(base + "/hls/master.m3u8", filename="My Video.ts").id)
    expect = b"".join(SEGS)
    got = open(it.saved_path, "rb").read() if it.status == COMPLETE else b""
    check("HLS (encrypted, master playlist) downloads and joins",
          it.status == COMPLETE and (got == expect or it.saved_path.endswith(".mp4")), it.error)

    # 6. queue with max simultaneous
    s.max_simultaneous = 2
    THROTTLE["delay"] = 0.003
    ids = [mgr.add(base + "/file.bin", filename=f"q{i}.bin", start=False, in_queue=True).id for i in range(4)]
    mgr.start_queue()
    peak = 0
    t0 = time.time()
    while time.time() - t0 < 120 and any(mgr.items[i].status != COMPLETE for i in ids):
        mgr.tick()
        peak = max(peak, sum(1 for i in ids if i in mgr.downloaders))
        time.sleep(0.1)
    mgr.tick()
    check("queue runs all items", all(mgr.items[i].status == COMPLETE for i in ids))
    check("queue respects max simultaneous (2)", peak == 2, f"peak {peak}")
    check("queue reports done", not mgr.queue_running)

    mgr.shutdown()
    srv.shutdown()
    shutil.rmtree(out, ignore_errors=True)
    print("\nALL TESTS PASSED" if ok else "\nSOME TESTS FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
