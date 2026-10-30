"""ffmpeg discovery, one-time download, and stream remuxing.

HLS streams arrive as many small MPEG-TS pieces. Joined together they form a raw
.ts file with no index, which players seek poorly and VLC often stutters on.
Remuxing (copying the streams, no re-encoding) into MKV or MP4 fixes that in a
few seconds without touching quality.
"""
import glob
import os
import shutil
import subprocess
import sys
import platform
import tarfile
import threading
import zipfile

from .config import app_data_dir
from .utils import child_env

NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0  # CREATE_NO_WINDOW
EXE = ".exe" if sys.platform == "win32" else ""
_FFMPEG_BASE = "https://github.com/yt-dlp/FFmpeg-Builds/releases/download/latest/"
FFMPEG_ZIP_URL = _FFMPEG_BASE + "ffmpeg-master-latest-win64-gpl.zip"


def _ffmpeg_download_url():
    """Static ffmpeg build for this system, or None if there isn't one."""
    machine = platform.machine().lower()
    if sys.platform == "win32" and machine in ("amd64", "x86_64"):
        return FFMPEG_ZIP_URL
    if sys.platform.startswith("linux"):
        if machine in ("x86_64", "amd64"):
            return _FFMPEG_BASE + "ffmpeg-master-latest-linux64-gpl.tar.xz"
        if machine in ("aarch64", "arm64"):
            return _FFMPEG_BASE + "ffmpeg-master-latest-linuxarm64-gpl.tar.xz"
    return None
STREAM_FORMATS = ("mkv", "mp4", "ts")

_cache = {"path": None, "checked": False}
_cache_lock = threading.Lock()
_download_lock = threading.Lock()


def own_ffmpeg_dir():
    return os.path.join(app_data_dir(), "ffmpeg")


def _candidates():
    """Places ffmpeg is commonly found, most specific first."""
    env = os.environ
    out = [env.get("FETCHLY_FFMPEG", "")]
    base = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else ""
    if base:
        out += [os.path.join(base, "ffmpeg" + EXE), os.path.join(base, "ffmpeg", "bin", "ffmpeg" + EXE),
                os.path.join(base, "ffmpeg", "ffmpeg" + EXE)]
    out.append(os.path.join(own_ffmpeg_dir(), "ffmpeg" + EXE))
    out.append(shutil.which("ffmpeg") or "")
    if sys.platform == "win32":
        local = env.get("LOCALAPPDATA", "")
        home = os.path.expanduser("~")
        pf = env.get("ProgramFiles", r"C:\Program Files")
        out += [
            os.path.join(local, "VidSnag", "bin", "ffmpeg.exe"),          # VidSnag helper's copy
            os.path.join(local, "Microsoft", "WinGet", "Links", "ffmpeg.exe"),
            os.path.join(home, "scoop", "shims", "ffmpeg.exe"),
            os.path.join(env.get("ProgramData", r"C:\ProgramData"), "chocolatey", "bin", "ffmpeg.exe"),
            os.path.join(pf, "ffmpeg", "bin", "ffmpeg.exe"),
            r"C:\ffmpeg\bin\ffmpeg.exe",
        ]
        out += sorted(glob.glob(os.path.join(local, "Microsoft", "WinGet", "Packages", "*FFmpeg*", "*", "bin",
                                             "ffmpeg.exe")), reverse=True)
    elif sys.platform == "darwin":
        out += ["/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg"]
    return [p for p in out if p]


def _works(path):
    try:
        r = subprocess.run([path, "-hide_banner", "-version"], capture_output=True, timeout=20,
                           creationflags=NO_WINDOW, env=child_env())
        return r.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def find_ffmpeg(refresh=False):
    """Path to a working ffmpeg, or None."""
    with _cache_lock:
        if _cache["checked"] and not refresh and (_cache["path"] is None or os.path.exists(_cache["path"])):
            return _cache["path"]
        found = None
        seen = set()
        for p in _candidates():
            key = os.path.normcase(os.path.abspath(p))
            if key in seen or not os.path.isfile(p):
                continue
            seen.add(key)
            if _works(p):
                found = p
                break
        _cache.update(path=found, checked=True)
        return found


def can_download_ffmpeg():
    return _ffmpeg_download_url() is not None


def download_ffmpeg(session, progress=None, should_stop=None):
    """Fetch a static ffmpeg build into Fetchly's data folder. Returns its path or raises."""
    with _download_lock:
        existing = find_ffmpeg(refresh=True)
        if existing:
            return existing
        url = _ffmpeg_download_url()
        if not url:
            raise RuntimeError("Install ffmpeg with your package manager")
        dest_dir = own_ffmpeg_dir()
        os.makedirs(dest_dir, exist_ok=True)
        archive = os.path.join(dest_dir, "ffmpeg-download" + (".zip" if url.endswith(".zip") else ".tar.xz"))
        target = os.path.join(dest_dir, "ffmpeg" + EXE)
        tmp = target + ".tmp"
        try:
            with session.get(url, stream=True, timeout=60) as r:
                r.raise_for_status()
                total = int(r.headers.get("Content-Length") or 0)
                done = 0
                with open(archive, "wb") as f:
                    for chunk in r.iter_content(256 * 1024):
                        if should_stop and should_stop():
                            raise InterruptedError()
                        f.write(chunk)
                        done += len(chunk)
                        if progress:
                            progress(done, total)
            if archive.endswith(".zip"):
                with zipfile.ZipFile(archive) as z:
                    member = next((n for n in z.namelist() if n.replace("\\", "/").endswith("/bin/ffmpeg.exe")), None)
                    if not member:
                        raise RuntimeError("ffmpeg.exe not found in the download")
                    with z.open(member) as src, open(tmp, "wb") as out:
                        shutil.copyfileobj(src, out, 1024 * 1024)
            else:
                with tarfile.open(archive, "r:xz") as t:
                    member = next((m for m in t.getmembers() if m.isfile() and m.name.endswith("/bin/ffmpeg")), None)
                    if not member:
                        raise RuntimeError("ffmpeg not found in the download")
                    with t.extractfile(member) as src, open(tmp, "wb") as out:
                        shutil.copyfileobj(src, out, 1024 * 1024)
                os.chmod(tmp, 0o755)
            os.replace(tmp, target)
        finally:
            for leftover in (archive, tmp):
                try:
                    os.remove(leftover)
                except OSError:
                    pass
        path = find_ffmpeg(refresh=True)
        if not path:
            raise RuntimeError("Downloaded ffmpeg doesn't run")
        return path


def remux(ffmpeg, src, dst, fmt):
    """Copy the audio/video streams from src into a new mkv/mp4 container. Raises on failure."""
    args = [ffmpeg, "-hide_banner", "-nostdin", "-y", "-loglevel", "error",
            # rebuild timestamps across segment joins; skip damaged packets instead of stopping
            "-fflags", "+genpts+discardcorrupt", "-i", src,
            "-map", "0:v?", "-map", "0:a?"]
    if fmt == "mkv":
        args += ["-map", "0:s?"]           # MKV holds subtitle tracks safely
    args += ["-dn", "-ignore_unknown", "-c", "copy", "-avoid_negative_ts", "make_zero"]
    if fmt == "mp4":
        args += ["-movflags", "+faststart"]
    tmp = dst + ".fetchlypart"
    args += ["-f", "matroska" if fmt == "mkv" else "mp4", tmp]
    try:
        res = subprocess.run(args, capture_output=True, timeout=3 * 3600, creationflags=NO_WINDOW, env=child_env())
        if res.returncode != 0:
            msg = (res.stderr or b"").decode("utf-8", "replace").strip().splitlines()
            raise RuntimeError(msg[-1] if msg else f"ffmpeg exited with {res.returncode}")
        src_size = os.path.getsize(src)
        out_size = os.path.getsize(tmp) if os.path.exists(tmp) else 0
        # A copy-remux keeps nearly every byte; much smaller output means streams were lost
        if out_size < max(1024, src_size * 0.5):
            raise RuntimeError("conversion produced an incomplete file")
        os.replace(tmp, dst)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
