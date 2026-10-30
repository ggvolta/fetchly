"""Fetchly: a multi-connection download manager for Windows and Linux.

    Fetchly               start normally
    Fetchly --tray        start in the tray (used when starting at sign-in)
    Fetchly <url>         add a download (handed to the running copy of Fetchly if there is one)
"""
import os
import sys
import traceback

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

from fetchly.config import APP_TITLE, Settings, app_data_dir, sync_extension
from fetchly.manager import DownloadManager
from fetchly.server import ApiServer, notify_running_instance
from fetchly.ui import icons, theme
from fetchly.ui.dialogs import message_box
from fetchly.ui.main_window import MainWindow, add_to_app_menu, launch_command
from fetchly.utils import (APP_ID, IS_LINUX, autostart_enabled, looks_like_url, menu_entry_installed,
                           set_autostart)


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


def _linux_integration(win, settings):
    """Keep the extension folder, menu entry and sign-in entry pointing at this copy of Fetchly (an AppImage can
    be moved or replaced by a newer one), and offer once to add Fetchly to the applications menu."""
    sync_extension()
    try:
        if menu_entry_installed():
            add_to_app_menu()
        if settings.start_with_system:
            set_autostart(True, launch_command())
    except OSError:
        pass
    if settings.menu_entry_asked or menu_entry_installed():
        return None
    settings.menu_entry_asked = True
    settings.save()

    def ask():
        box = message_box(QMessageBox.Question, APP_TITLE, "Add Fetchly to your applications menu?",
                          parent=win if win.isVisible() else None)
        box.setInformativeText("You'll be able to open it like any other app. You can change this later in "
                               "Options.")
        add = box.addButton("Add to menu", QMessageBox.AcceptRole)
        box.addButton("Not now", QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() is add:
            try:
                add_to_app_menu()
            except OSError as e:
                QMessageBox.warning(None, APP_TITLE, f"Couldn't add Fetchly to the menu:\n{e}")
    return ask


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
    settings.start_with_system = autostart_enabled()
    app = QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    app.setOrganizationName("Fetchly")
    app.setDesktopFileName(APP_ID)       # Linux: matches the .desktop file, so the taskbar shows Fetchly's icon
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
    else:
        # No tray on this desktop after waiting a while: show the window minimized rather than staying invisible
        QTimer.singleShot(12_000, lambda: (not win.tray and not win.isVisible()) and win.showMinimized())
    first_steps = []      # one-time questions, shown one after another
    if IS_LINUX and getattr(sys, "frozen", False):
        ask = _linux_integration(win, settings)
        if ask:
            first_steps.append(ask)
    if url:
        manager.events.put(("catch", {"url": url}))
    if settings.first_run:
        settings.first_run = False
        settings.save()
        first_steps.append(win.browser_setup)
    if first_steps:
        QTimer.singleShot(600, lambda: [step() for step in first_steps])
    code = app.exec()
    if not win._quitting:
        manager.shutdown()
    return code


if __name__ == "__main__":
    sys.exit(main())
