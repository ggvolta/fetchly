"""Download benchmark: Fetchly engine vs a single connection (what a browser does) and vs aria2c
(a native C++ multi-connection downloader, used as a stand-in for IDM).

    python tools/benchmark.py URL [--conns 1,8,16] [--aria2] [--runs 1] [--out results.json]
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("FETCHLY_DATA_DIR", tempfile.mkdtemp(prefix="fetchly-bench-"))

from fetchly.config import Settings  # noqa: E402
from fetchly.manager import DownloadManager  # noqa: E402
from fetchly.models import COMPLETE, ERROR  # noqa: E402


def cpu():
    t = os.times()
    return t.user + t.system


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def run_fdm(url, conns):
    out = tempfile.mkdtemp(prefix="fetchly-out-")
    s = Settings()
    s.download_root, s.max_connections = out, conns
    m = DownloadManager(s, db_path=os.path.join(out, "db.json"))
    c0, t0 = cpu(), time.perf_counter()
    first_byte = None
    it = m.add(url, filename="bench.bin", save_dir=out)
    while True:
        m.tick()
        if first_byte is None and it.downloaded() > 0:
            first_byte = time.perf_counter() - t0
        if it.status in (COMPLETE, ERROR) and it.id not in m.downloaders:
            break
        time.sleep(0.02)
    t = time.perf_counter() - t0
    c = cpu() - c0
    res = {"tool": "Fetchly", "conns": conns, "ok": it.status == COMPLETE, "seconds": t, "bytes": it.size,
           "cpu_seconds": c, "first_byte": first_byte, "segments": len(it.segments), "error": it.error}
    if res["ok"]:
        res["sha256"] = sha(it.saved_path)
    shutil.rmtree(out, ignore_errors=True)
    return res


def run_aria2(url, conns):
    out = tempfile.mkdtemp(prefix="aria-out-")
    t0 = time.perf_counter()
    p = subprocess.run(["aria2c", "-q", "-x", str(min(conns, 16)), "-s", str(conns), "-k", "1M",
                        "--file-allocation=none", "--allow-overwrite=true", "-d", out, "-o", "bench.bin", url],
                       capture_output=True)
    t = time.perf_counter() - t0
    path = os.path.join(out, "bench.bin")
    ok = p.returncode == 0 and os.path.exists(path)
    ru = __import__("resource").getrusage(__import__("resource").RUSAGE_CHILDREN)
    res = {"tool": "aria2c", "conns": conns, "ok": ok, "seconds": t, "bytes": os.path.getsize(path) if ok else 0,
           "cpu_seconds_total_children": ru.ru_utime + ru.ru_stime}
    if ok:
        res["sha256"] = sha(path)
    shutil.rmtree(out, ignore_errors=True)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--conns", default="1,8")
    ap.add_argument("--aria2", action="store_true")
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--label", default="")
    ap.add_argument("--out")
    a = ap.parse_args()
    results = []
    for n in [int(x) for x in a.conns.split(",")]:
        for _ in range(a.runs):
            r = run_fdm(a.url, n)
            r["label"] = a.label
            results.append(r)
            print(f"Fetchly    {n:>2} conn  {r['seconds']:7.2f}s  {r['bytes'] / r['seconds'] / 1e6:8.1f} MB/s  "
                  f"cpu {r['cpu_seconds']:.1f}s  first byte {r['first_byte'] or 0:.2f}s  ok={r['ok']}", flush=True)
            if a.aria2:
                r = run_aria2(a.url, n)
                r["label"] = a.label
                results.append(r)
                print(f"aria2c {n:>2} conn  {r['seconds']:7.2f}s  {r['bytes'] / r['seconds'] / 1e6:8.1f} MB/s  "
                      f"ok={r['ok']}", flush=True)
    if a.out:
        old = json.load(open(a.out)) if os.path.exists(a.out) else []
        json.dump(old + results, open(a.out, "w"), indent=1)


if __name__ == "__main__":
    main()
