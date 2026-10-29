"""Persistent settings."""
import json
import os
import sys
from dataclasses import asdict, dataclass, field, fields

from . import __version__
from .utils import DEFAULT_INTERCEPT_TYPES

APP_NAME = "Fetchly"
APP_TITLE = "Fetchly"
VERSION = __version__
DEFAULT_PORT = 7614


def app_data_dir():
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    path = os.environ.get("FETCHLY_DATA_DIR") or os.path.join(base, APP_NAME)
    os.makedirs(path, exist_ok=True)
    return path


def base_dir():
    """Folder holding the program (the exe when frozen, the project root otherwise)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def extension_dir():
    return os.path.join(base_dir(), "extension")


def default_download_root():
    return os.path.join(os.path.expanduser("~"), "Downloads")


def default_scheduler():
    return {"enabled": False, "start_time": "02:00", "days": [0, 1, 2, 3, 4, 5, 6], "once": False,
            "stop_enabled": False, "stop_time": "07:00", "on_done": "none"}


@dataclass
class Settings:
    download_root: str = field(default_factory=default_download_root)
    category_dirs: dict = field(default_factory=dict)
    max_connections: int = 8
    max_simultaneous: int = 3
    speed_limit_enabled: bool = False
    speed_limit_kb: int = 512
    port: int = DEFAULT_PORT
    browser_integration: bool = True
    intercept_types: list = field(default_factory=lambda: list(DEFAULT_INTERCEPT_TYPES))
    min_intercept_kb: int = 0
    monitor_clipboard: bool = True
    show_catch_dialog: bool = True
    show_progress_dialog: bool = True
    show_complete_dialog: bool = True
    minimize_to_tray: bool = True
    start_with_system: bool = False
    scheduler: dict = field(default_factory=default_scheduler)
    window_geometry: str = ""
    splitter_state: str = ""
    header_state: str = ""
    tray_hint_shown: bool = False
    theme: str = "system"          # system / light / dark
    proxy: str = ""                # "" = use the Windows/system proxy; or http://host:port, socks5://host:port
    first_run: bool = True
    hidden_columns: list = field(default_factory=list)
    stream_format: str = "mkv"     # container for streaming (HLS) videos: mkv / mp4 / ts
    auto_get_ffmpeg: bool = True   # download ffmpeg once if it isn't installed (Windows)

    def dir_for(self, category):
        custom = self.category_dirs.get(category)
        if custom:
            return custom
        if category == "General":
            return self.download_root
        return os.path.join(self.download_root, category)

    @staticmethod
    def path():
        return os.path.join(app_data_dir(), "settings.json")

    @classmethod
    def load(cls):
        s = cls()
        try:
            with open(cls.path(), "r", encoding="utf-8") as f:
                data = json.load(f)
            names = {f.name for f in fields(cls)}
            for k, v in data.items():
                if k in names:
                    setattr(s, k, v)
            sch = default_scheduler()
            sch.update(s.scheduler or {})
            s.scheduler = sch
        except (OSError, ValueError):
            pass
        return s

    def save(self):
        tmp = self.path() + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2)
        os.replace(tmp, self.path())
