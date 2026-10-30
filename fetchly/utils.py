"""Small helpers: file naming, categories, formatting, opening files."""
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import urllib.parse

# Category -> file extensions (same grouping IDM uses, plus a few modern types)
CATEGORY_EXTS = {
    "Compressed": "zip rar 7z arj gz tgz bz2 xz z lzh ace cab sit sitx sea tar iso img zst r00 r01".split(),
    "Documents": "doc docx pdf ppt pptx pps ppsx xls xlsx odt ods odp rtf txt csv epub mobi djvu".split(),
    "Music": "mp3 wav wma aac m4a flac ogg oga opus aif aiff mpa ra ram mid midi".split(),
    "Programs": "exe msi msu apk dmg pkg deb rpm appimage jar".split(),
    "Video": "mp4 mkv avi mov wmv flv webm m4v mpg mpeg mpe 3gp asf rm rmvb ogv ts qt".split(),
}
CATEGORIES = ["General", "Compressed", "Documents", "Music", "Programs", "Video"]

# File types the browser extension hands over to Fetchly automatically
DEFAULT_INTERCEPT_TYPES = (
    "3GP 7Z AAC ACE AIF APK ARJ ASF AVI BIN BZ2 DEB DMG DOCX EXE FLAC FLV GZ GZIP IMG ISO "
    "LZH M4A M4V MKV MOV MP3 MP4 MPA MPE MPEG MPG MSI MSU OGG OGV OPUS PDF PKG PPS PPT PPTX "
    "QT R0* R1* RA RAR RM RMVB RPM SEA SIT SITX TAR TGZ TIF TIFF WAV WEBM WMA WMV XLSX XZ Z ZIP ZST"
).split()

_INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED = {"CON", "PRN", "AUX", "NUL"} | {f"COM{i}" for i in range(1, 10)} | {f"LPT{i}" for i in range(1, 10)}
_URL_RE = re.compile(r"^https?://\S+$", re.I)


def ext_of(name):
    return os.path.splitext(name or "")[1].lstrip(".").lower()


def category_for(name):
    e = ext_of(name)
    for cat, exts in CATEGORY_EXTS.items():
        if e in exts:
            return cat
    return "General"


def matches_types(name, types):
    """True if the file extension matches the list (supports trailing * like R0*)."""
    e = ext_of(name).upper()
    if not e:
        return False
    for t in types:
        t = t.strip().upper().lstrip(".")
        if not t:
            continue
        if t.endswith("*"):
            if e.startswith(t[:-1]):
                return True
        elif e == t:
            return True
    return False


def sanitize_filename(name, fallback="download"):
    name = _INVALID.sub("_", name or "").strip().rstrip(". ")
    if not name:
        name = fallback
    stem, ext = os.path.splitext(name)
    if stem.upper() in _RESERVED:
        name = "_" + name
    if len(name) > 180:
        stem, ext = os.path.splitext(name)
        name = stem[: 180 - len(ext)] + ext
    return name


def filename_from_url(url):
    try:
        path = urllib.parse.urlsplit(url).path
    except ValueError:
        return ""
    name = urllib.parse.unquote(os.path.basename(path.rstrip("/")))
    return sanitize_filename(name) if name else ""


def filename_from_cd(cd):
    """Parse a Content-Disposition header for the filename."""
    if not cd:
        return ""
    m = re.search(r"filename\*\s*=\s*([^']*)'[^']*'([^;]+)", cd, re.I)
    if m:
        enc = m.group(1) or "utf-8"
        try:
            return sanitize_filename(urllib.parse.unquote(m.group(2).strip().strip('"'), encoding=enc))
        except LookupError:
            pass
    m = re.search(r'filename\s*=\s*"([^"]*)"', cd, re.I) or re.search(r"filename\s*=\s*([^;]+)", cd, re.I)
    if m:
        raw = m.group(1).strip()
        try:
            raw = raw.encode("latin-1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
        return sanitize_filename(raw)
    return ""


_MIME_FIX = {"video/mp4": ".mp4", "audio/mpeg": ".mp3", "video/webm": ".webm", "audio/mp4": ".m4a",
             "application/zip": ".zip", "application/pdf": ".pdf", "video/x-matroska": ".mkv",
             "application/x-msdownload": ".exe", "application/vnd.android.package-archive": ".apk",
             "application/x-rar-compressed": ".rar", "application/x-7z-compressed": ".7z"}


def guess_ext(content_type):
    if not content_type:
        return ""
    ct = content_type.split(";")[0].strip().lower()
    if ct in _MIME_FIX:
        return _MIME_FIX[ct]
    if ct in ("application/octet-stream", "text/html", "text/plain"):
        return ""
    return mimetypes.guess_extension(ct) or ""


def is_hls_url(url, content_type=""):
    ct = (content_type or "").lower()
    if "mpegurl" in ct:
        return True
    try:
        return urllib.parse.urlsplit(url).path.lower().endswith(".m3u8")
    except ValueError:
        return False


def unique_path(path):
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    i = 2
    while os.path.exists(f"{base} ({i}){ext}"):
        i += 1
    return f"{base} ({i}){ext}"


def looks_like_url(text):
    return bool(text) and bool(_URL_RE.match(text.strip()))


def human_size(n):
    if n is None or n < 0:
        return ""
    n = float(n)
    for unit in ("Bytes", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{int(n)} {unit}" if unit == "Bytes" else f"{n:.2f} {unit}"
        n /= 1024


def human_speed(bps):
    return f"{human_size(bps)}/sec" if bps and bps > 0 else ""


def human_time(sec):
    if sec is None or sec < 0 or sec == float("inf"):
        return ""
    sec = max(1, int(sec + 0.5))
    d, sec = divmod(sec, 86400)
    h, sec = divmod(sec, 3600)
    m, s = divmod(sec, 60)
    if d:
        return f"{d} day {h} hr"
    if h:
        return f"{h} hr {m} min"
    if m:
        return f"{m} min {s} sec"
    return f"{s} sec"


IS_WINDOWS = sys.platform == "win32"
IS_LINUX = sys.platform.startswith("linux")
OS_NAME = "Windows" if IS_WINDOWS else ("macOS" if sys.platform == "darwin" else "Linux")
APP_ID = "io.github.ggvolta.Fetchly"


def child_env():
    """Environment for programs Fetchly starts (file manager, browser, ffmpeg).

    A packaged Linux build puts its own bundled libraries first on LD_LIBRARY_PATH; passing that on can make
    other programs load the wrong libraries and crash. Restore what the user's session had."""
    env = dict(os.environ)
    if IS_LINUX:
        for var in ("LD_LIBRARY_PATH", "QT_PLUGIN_PATH", "QML2_IMPORT_PATH", "PYTHONHOME", "PYTHONPATH"):
            orig = env.pop(var + "_ORIG", None)
            if orig is not None:
                env[var] = orig
            elif getattr(sys, "frozen", False):
                env.pop(var, None)
        for var in ("APPDIR", "APPIMAGE", "ARGV0", "OWD"):
            env.pop(var, None)
    return env


def _spawn(args, **kw):
    return subprocess.Popen(args, env=child_env(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            start_new_session=not IS_WINDOWS, **kw)


def open_path(path):
    if IS_WINDOWS:
        os.startfile(path)  # noqa
    elif sys.platform == "darwin":
        _spawn(["open", path])
    else:
        _spawn(["xdg-open", path])


def open_folder(path):
    """Open the folder containing path and select the file where the OS allows it."""
    if IS_WINDOWS:
        if os.path.exists(path):
            subprocess.Popen(f'explorer /select,"{os.path.normpath(path)}"')
        else:
            os.startfile(os.path.dirname(path))  # noqa
    elif sys.platform == "darwin":
        _spawn(["open", "-R", path] if os.path.exists(path) else ["open", os.path.dirname(path)])
    else:
        # Most Linux file managers (Files, Dolphin, Nemo, Caja, Thunar) can highlight the file via D-Bus
        if os.path.exists(path) and shutil.which("dbus-send"):
            uri = "file://" + urllib.parse.quote(os.path.abspath(path))
            r = subprocess.run(["dbus-send", "--session", "--print-reply", "--dest=org.freedesktop.FileManager1",
                                "--type=method_call", "/org/freedesktop/FileManager1",
                                "org.freedesktop.FileManager1.ShowItems", f"array:string:{uri}", "string:"],
                               env=child_env(), capture_output=True, timeout=5)
            if r.returncode == 0:
                return
        _spawn(["xdg-open", os.path.dirname(path) or "."])


def open_with(path):
    if IS_WINDOWS:
        subprocess.Popen(["rundll32.exe", "shell32.dll,OpenAs_RunDLL", os.path.normpath(path)])
    else:
        open_path(path)


# ---------------------------------------------------------------- start with the computer
_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def _xdg(var, default):
    return os.environ.get(var) or os.path.expanduser(default)


def _autostart_file():
    return os.path.join(_xdg("XDG_CONFIG_HOME", "~/.config"), "autostart", APP_ID + ".desktop")


def autostart_enabled():
    if IS_WINDOWS:
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as k:
                winreg.QueryValueEx(k, "Fetchly")
                return True
        except OSError:
            return False
    if IS_LINUX:
        return os.path.exists(_autostart_file())
    return False


def set_autostart(enabled, command):
    """Start Fetchly in the tray when the user signs in (Windows Run key / XDG autostart entry)."""
    if IS_WINDOWS:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE)
        try:
            if enabled:
                winreg.SetValueEx(key, "Fetchly", 0, winreg.REG_SZ, command)
            else:
                try:
                    winreg.DeleteValue(key, "Fetchly")
                except FileNotFoundError:
                    pass
        finally:
            winreg.CloseKey(key)
        return True
    if IS_LINUX:
        path = _autostart_file()
        if enabled:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(desktop_entry(command, autostart=True))
        elif os.path.exists(path):
            os.remove(path)
        return True
    return False


# ---------------------------------------------------------------- Linux applications menu
def desktop_entry(exec_cmd, autostart=False):
    lines = ["[Desktop Entry]", "Type=Application", "Name=Fetchly", "GenericName=Download Manager",
             "Comment=Faster downloads with many connections at once, and resume when they break",
             f"Exec={exec_cmd}", f"Icon={APP_ID}", "Terminal=false",
             "Categories=Network;FileTransfer;", "Keywords=download;downloader;accelerator;manager;",
             f"StartupWMClass={APP_ID}"]
    if autostart:
        lines += ["X-GNOME-Autostart-enabled=true"]
    return "\n".join(lines) + "\n"


def _menu_files():
    data = _xdg("XDG_DATA_HOME", "~/.local/share")
    return (os.path.join(data, "applications", APP_ID + ".desktop"),
            os.path.join(data, "icons", "hicolor", "256x256", "apps", APP_ID + ".png"))


def menu_entry_installed():
    return IS_LINUX and os.path.exists(_menu_files()[0])


def install_menu_entry(exec_cmd, icon_png):
    """Add Fetchly to the desktop's applications menu (current user only)."""
    entry, icon = _menu_files()
    os.makedirs(os.path.dirname(entry), exist_ok=True)
    os.makedirs(os.path.dirname(icon), exist_ok=True)
    if icon_png and os.path.exists(icon_png):
        shutil.copyfile(icon_png, icon)
    with open(entry, "w", encoding="utf-8") as f:
        f.write(desktop_entry(exec_cmd + " %U"))
    if shutil.which("update-desktop-database"):
        subprocess.run(["update-desktop-database", os.path.dirname(entry)], env=child_env(), capture_output=True)


def remove_menu_entry():
    for p in _menu_files():
        if os.path.exists(p):
            os.remove(p)
