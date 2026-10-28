"""Fetchly — a multi-connection download manager for Windows.

    Fetchly.exe            start normally
    Fetchly.exe --tray     start in the notification area (used when starting with Windows)
    Fetchly.exe <url>      add a download (handed to the running copy of Fetchly if there is one)
"""
import os
import sys
import traceback

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

from fetchly.config import APP_TITLE, Settings, app_data_dir
from fetchly.manager import DownloadManager
from fetchly.server import ApiServer, notify_running_instance
from fetchly.ui import icons, theme
from fetchly.ui.main_window import MainWindow
from fetchly.utils import autostart_enabled, looks_like_url


def _install_crash_log():
    log = os.path.join(app_data_dir(), "error.log")

    def hook(exc_type, exc, tb):
        text = "".join(traceback.format_exception(exc_type, exc, tb))
        try:
            with open(log, "a", encoding="utf-8") as f:
                f.write(text + "\n")
        except OSError:
            pass
        if QApplication.instance():
            QMessageBox.critical(None, APP_TITLE, f"Something went wrong:\n\n{exc}\n\nDetails were saved to:\n{log}")

    sys.excepthook = hook


def main():
    args = sys.argv[1:]
    url = next((a for a in args if looks_like_url(a)), None)
    start_hidden = "--tray" in args
    _install_crash_log()

    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Fetchly.App.1")
        except (AttributeError, OSError):
            pass

    settings = Settings.load()
    settings.start_with_system = autostart_enabled() or (settings.start_with_system and sys.platform != "win32")
    app = QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    app.setOrganizationName("Fetchly")
    app.setQuitOnLastWindowClosed(False)
    theme.apply(app, settings.theme)
    app.setWindowIcon(icons.app_icon())
    title_filter = theme.TitleBarFilter(app)
    app.installEventFilter(title_filter)

    manager = DownloadManager(settings)
    server = ApiServer(manager, settings.port)
    try:
        server.start()
    except OSError:
        # Port busy: Fetchly is most likely already running -> hand over and quit.
        if notify_running_instance(settings.port, {"url": url} if url else None):
            return 0
        QMessageBox.warning(None, APP_TITLE,
                            f"Port {settings.port} is used by another program, so the browser extension can't "
                            "reach Fetchly. Choose another port in Options › File Types (and in the extension popup).")
        server = None

    win = MainWindow(manager, settings, server)
    if not start_hidden:
        win.show()
    if url:
        manager.events.put(("catch", {"url": url}))
    if settings.first_run:
        settings.first_run = False
        settings.save()
        QTimer.singleShot(600, win.browser_setup)
    code = app.exec()
    if not win._quitting:
        manager.shutdown()
    return code


if __name__ == "__main__":
    sys.exit(main())
