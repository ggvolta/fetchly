"""Main window: toolbar, categories, download list, status bar, tray icon."""
import datetime
import os
import re
import shutil
import subprocess
import sys
import time

from PySide6.QtCore import QAbstractTableModel, QByteArray, QEvent, QItemSelectionModel, QModelIndex, QSize, Qt, QTimer
from PySide6.QtGui import QAction, QColor, QGuiApplication, QKeySequence, QPainter
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QCheckBox, QFileDialog, QHBoxLayout, QHeaderView,
                               QLabel, QMainWindow, QMenu, QMessageBox, QSizePolicy, QSplitter, QSystemTrayIcon,
                               QTableView, QToolBar, QTreeWidget, QTreeWidgetItem, QWidget)

from ..config import APP_TITLE, app_data_dir
from ..models import COMPLETE, ERROR, QUEUED
from ..utils import (CATEGORIES, filename_from_url, human_size, human_speed, human_time, looks_like_url,
                     matches_types, open_folder, open_path, open_with, set_autostart)
from . import dialogs as D
from . import icons, theme
from .widgets import ROLE_COUNT, ROLE_STATUS, SearchBox, SidebarDelegate, StatusDelegate

COLS = ["File Name", "Size", "Status", "Time Left", "Transfer Rate", "Last Try Date", "Description"]


def item_state(it, running):
    if it.status == COMPLETE:
        return "complete"
    if it.status == ERROR:
        return "error"
    if running:
        return "downloading"
    if it.status == QUEUED:
        return "queued"
    return "paused"


def status_text(it, state):
    p = it.progress()
    if state == "complete":
        return "Complete"
    if state == "error":
        return "Error"
    if state == "downloading":
        return f"{p * 100:.1f}%" if p is not None else (human_size(it.downloaded()) or "Connecting…")
    if state == "queued":
        return f"{p * 100:.1f}%" if p else "Queued"
    return f"{p * 100:.1f}%" if p else "Stopped"


class DownloadModel(QAbstractTableModel):
    def __init__(self, manager):
        super().__init__()
        self.m = manager
        self.ids = []
        self.filter = ("all", None)
        self.search = ""
        self.sort_col, self.sort_order = -1, Qt.AscendingOrder

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.ids)

    def columnCount(self, parent=QModelIndex()):
        return len(COLS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal:
            if role == Qt.DisplayRole:
                return COLS[section]
            if role == Qt.TextAlignmentRole:
                return int(Qt.AlignLeft | Qt.AlignVCenter)
        return None

    def item_at(self, row):
        return self.m.items.get(self.ids[row]) if 0 <= row < len(self.ids) else None

    def data(self, index, role=Qt.DisplayRole):
        it = self.item_at(index.row())
        if not it:
            return None
        col = index.column()
        running = it.id in self.m.downloaders and it.status != COMPLETE
        if role == Qt.DisplayRole:
            if col == 0:
                return it.filename or filename_from_url(it.url) or it.url
            if col == 1:
                return human_size(it.size) if it.size > 0 else ""
            if col == 3:
                return human_time(it.eta) if running and it.eta > 0 else ""
            if col == 4:
                return human_speed(it.speed) if running else ""
            if col == 5:
                return datetime.datetime.fromtimestamp(it.last_try).strftime("%b %d %Y %H:%M") if it.last_try else ""
            if col == 6:
                return it.description or (it.error if it.status == ERROR else "")
        elif role == ROLE_STATUS and col == 2:
            st = item_state(it, running)
            return (st, it.progress(), status_text(it, st))
        elif role == Qt.DecorationRole and col == 0:
            return self.m.file_icons.for_item(it.filename or filename_from_url(it.url), it.saved_path)
        elif role == Qt.ForegroundRole:
            if it.status == ERROR and col == 6:
                return QColor(theme.colors()["danger"])
            if col in (1, 3, 4, 5):
                return QColor(theme.colors()["muted"])
        elif role == Qt.ToolTipRole:
            tip = f"{it.filename}\n{it.url}"
            if it.status == ERROR:
                tip += f"\n\nError: {it.error}"
            return tip
        return None

    def _matches(self, it):
        kind, val = self.filter
        ok = True
        if kind == "category":
            ok = it.category == val
        elif kind == "finished":
            ok = it.status == COMPLETE
        elif kind == "unfinished":
            ok = it.status != COMPLETE
        elif kind == "queue":
            ok = it.in_queue
        if ok and self.search:
            q = self.search
            ok = q in (it.filename or "").lower() or q in it.url.lower() or q in (it.description or "").lower()
        return ok

    def _sort_key(self, col):
        return [lambda it: (it.filename or "").lower(), lambda it: it.size, lambda it: (it.progress() or 0),
                lambda it: it.eta, lambda it: it.speed, lambda it: it.last_try or it.added,
                lambda it: (it.description or "").lower()][col]

    def refresh(self, force=False):
        items = [it for it in self.m.items.values() if self._matches(it)]
        if self.filter[0] == "queue":
            items.sort(key=lambda x: x.queue_order)
        if self.sort_col >= 0:
            items.sort(key=self._sort_key(self.sort_col), reverse=self.sort_order == Qt.DescendingOrder)
        ids = [it.id for it in items]
        if ids != self.ids or force:
            self.beginResetModel()
            self.ids = ids
            self.endResetModel()
            return True
        if ids:
            self.dataChanged.emit(self.index(0, 0), self.index(len(ids) - 1, len(COLS) - 1))
        return False

    def sort(self, column, order=Qt.AscendingOrder):
        self.sort_col, self.sort_order = column, order
        self.refresh(force=True)


class DownloadTable(QTableView):
    """Download list with an empty-state message."""

    def __init__(self):
        super().__init__()
        self.setObjectName("downloads")
        self.empty_text = "No downloads yet"
        self.empty_hint = "Click Add URL, paste a link, or download something in your browser."

    def paintEvent(self, e):
        super().paintEvent(e)
        if self.model() and self.model().rowCount() == 0:
            c = theme.colors()
            p = QPainter(self.viewport())
            p.setRenderHint(QPainter.Antialiasing)
            r = self.viewport().rect()
            cy = r.center().y() - 40
            icons.svg("arrow_download", c["border_strong"], "regular").paint(p, r.center().x() - 24, cy - 30, 48, 48)
            f = p.font()
            base = f.pointSizeF()
            f.setPointSizeF(base + 2.5)
            f.setBold(True)
            p.setFont(f)
            p.setPen(QColor(c["muted"]))
            p.drawText(r.adjusted(0, cy - r.top() + 30, 0, 0), Qt.AlignHCenter | Qt.AlignTop, self.empty_text)
            f.setBold(False)
            f.setPointSizeF(base)
            p.setFont(f)
            p.setPen(QColor(c["faint"]))
            p.drawText(r.adjusted(0, cy - r.top() + 60, 0, 0), Qt.AlignHCenter | Qt.AlignTop, self.empty_hint)
            p.end()


class ClickLabel(QLabel):
    def __init__(self, slot=None):
        super().__init__()
        self._slot = slot
        if slot:
            self.setCursor(Qt.PointingHandCursor)

    def mouseReleaseEvent(self, e):
        if self._slot and e.button() == Qt.LeftButton:
            self._slot()
        super().mouseReleaseEvent(e)


def alive(widget):
    try:
        widget.isVisible()
        return True
    except RuntimeError:
        return False


class MainWindow(QMainWindow):
    def __init__(self, manager, settings, server):
        super().__init__()
        self.m, self.s, self.server = manager, settings, server
        self.m.file_icons = icons.FileIcons(app_data_dir())
        self.setWindowTitle(APP_TITLE)
        self.setWindowIcon(icons.app_icon())
        self.resize(1180, 680)
        self.setMinimumSize(820, 480)
        self.progress = {}
        self._dialogs = []
        self._quitting = False
        self._last_clip = QGuiApplication.clipboard().text().strip()
        self._tray_active = None

        self._build_actions()
        self._build_menu()
        self._build_toolbar()
        self._build_body()
        self._build_statusbar()
        self._build_tray()
        self.apply_icons()
        self.setAcceptDrops(True)

        if settings.window_geometry:
            self.restoreGeometry(QByteArray.fromBase64(settings.window_geometry.encode()))
        if settings.splitter_state:
            self.splitter.restoreState(QByteArray.fromBase64(settings.splitter_state.encode()))
        if settings.header_state:
            self.table.horizontalHeader().restoreState(QByteArray.fromBase64(settings.header_state.encode()))

        QApplication.clipboard().dataChanged.connect(self._clipboard_changed)
        try:
            QGuiApplication.styleHints().colorSchemeChanged.connect(self._system_theme_changed)
        except AttributeError:
            pass
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(500)
        self.model.refresh(force=True)
        self._update_actions()
        self._update_counts()
        self._update_status()

    # ================================================================== building
    def _act(self, text, slot=None, shortcut=None, tip=None):
        a = QAction(text, self)
        if slot:
            a.triggered.connect(slot)
        if shortcut:
            a.setShortcut(QKeySequence(shortcut))
        a.setToolTip(tip or text)
        return a

    def _build_actions(self):
        A = self._act
        m = self.m
        self.a_add = A("Add URL", self.add_url, "Ctrl+N", "Add a new download (Ctrl+N)")
        self.a_batch = A("Add batch download…", self.batch_download, "Ctrl+B")
        self.a_resume = A("Resume", self.resume_selected, "Ctrl+R", "Resume the selected downloads")
        self.a_stop = A("Stop", self.stop_selected, "Ctrl+S", "Stop the selected downloads")
        self.a_stopall = A("Stop All", m.stop_all, None, "Stop all downloads")
        self.a_delete = A("Delete", self.delete_selected, "Del", "Delete the selected downloads")
        self.a_clean = A("Delete Completed", self.delete_completed, None, "Remove completed downloads from the list")
        self.a_options = A("Options", self.options, "Ctrl+,", "Settings")
        self.a_sched = A("Scheduler", self.scheduler, None, "Schedule the download queue")
        self.a_qstart = A("Start Queue", m.start_queue, None, "Start the main download queue")
        self.a_qstop = A("Stop Queue", m.stop_queue, None, "Stop the main download queue")
        self.a_open = A("Open", self.open_selected)
        self.a_open_with = A("Open with…", lambda: self._with_sel(lambda it: open_with(it.saved_path)))
        self.a_folder = A("Open folder", lambda: self._with_sel(lambda it: open_folder(it.target_path)))
        self.a_move = A("Move / Rename…", self.move_rename)
        self.a_redl = A("Redownload", self.redownload_selected)
        self.a_props = A("Properties", self.properties, "Alt+Return")
        self.a_progress = A("Show progress", lambda: self._with_sel(lambda it: self.show_progress(it.id)))
        self.a_q_add = A("Add to queue", lambda: self.m.set_in_queue(self.selected_ids(), True))
        self.a_q_del = A("Remove from queue", lambda: self.m.set_in_queue(self.selected_ids(), False))
        self.a_copy = A("Copy address", lambda: QApplication.clipboard().setText(
            "\n".join(self.m.items[i].url for i in self.selected_ids())), "Ctrl+C")
        self.a_selall = A("Select all", lambda: self.table.selectAll(), "Ctrl+A")
        self.a_limiter = A("Speed Limiter", self.toggle_limiter, None, "Turn the speed limiter on or off")
        self.a_limiter.setCheckable(True)
        self.a_import = A("Import links from file…", self.import_links)
        self.a_export = A("Export download list…", self.export_links)
        self.a_browser = A("Browser integration…", self.browser_setup)
        self.a_about = A(f"About {APP_TITLE}", lambda: D.AboutDialog(self).exec())
        self.a_exit = A("Exit", lambda: self.quit_app(), "Ctrl+Q")
        for a in (self.a_copy, self.a_selall, self.a_delete, self.a_props):
            a.setShortcutContext(Qt.WidgetWithChildrenShortcut)

    def apply_icons(self):
        """(Re)assign every icon — at start-up and whenever the theme changes."""
        for a, n in ((self.a_add, "add"), (self.a_resume, "resume"), (self.a_stop, "stop"),
                     (self.a_stopall, "stopall"), (self.a_delete, "delete"), (self.a_clean, "clean"),
                     (self.a_options, "options"), (self.a_sched, "scheduler"), (self.a_qstart, "qstart"),
                     (self.a_qstop, "qstop"), (self.a_batch, "batch")):
            a.setIcon(icons.action(n))
        for a, n in ((self.a_open, "open"), (self.a_open_with, "window_new"), (self.a_folder, "folder_open"),
                     (self.a_move, "rename"), (self.a_redl, "arrow_clockwise"), (self.a_props, "info"),
                     (self.a_progress, "gauge"), (self.a_q_add, "document_queue_add"),
                     (self.a_q_del, "dismiss"), (self.a_copy, "copy"), (self.a_limiter, "top_speed"),
                     (self.a_import, "arrow_import"), (self.a_export, "arrow_export"),
                     (self.a_browser, "puzzle_piece"), (self.a_about, "question_circle"), (self.a_exit, "power")):
            a.setIcon(icons.menu(n))
        stack = [self.tree.topLevelItem(i) for i in range(self.tree.topLevelItemCount())]
        while stack:
            x = stack.pop()
            key = x.data(0, Qt.UserRole + 5)
            if key:
                x.setIcon(0, icons.category(key))
            stack.extend(x.child(i) for i in range(x.childCount()))
        self.search.refresh_icon()
        self._tray_active = None
        self.setWindowIcon(icons.app_icon())

    def _build_menu(self):
        mb = self.menuBar()
        t = mb.addMenu("&Tasks")
        t.addActions([self.a_add, self.a_batch])
        t.addSeparator()
        t.addActions([self.a_import, self.a_export])
        t.addSeparator()
        t.addAction(self.a_exit)
        f = mb.addMenu("&File")
        f.addActions([self.a_resume, self.a_stop, self.a_redl])
        f.addSeparator()
        f.addActions([self.a_open, self.a_open_with, self.a_folder, self.a_move])
        f.addSeparator()
        f.addActions([self.a_delete, self.a_props])
        d = mb.addMenu("&Downloads")
        d.addActions([self.a_stopall, self.a_clean])
        d.addSeparator()
        d.addActions([self.a_qstart, self.a_qstop, self.a_sched])
        d.addSeparator()
        d.addActions([self.a_limiter, self.a_options])
        v = mb.addMenu("&View")
        self.col_menu = v.addMenu("Columns")
        self.col_menu.aboutToShow.connect(lambda: self._fill_column_menu(self.col_menu))
        h = mb.addMenu("&Help")
        h.addAction(self.a_browser)
        h.addSeparator()
        h.addAction(self.a_about)

    def _build_toolbar(self):
        tb = QToolBar("Main")
        tb.setObjectName("mainToolbar")
        tb.setMovable(False)
        tb.setFloatable(False)
        tb.setIconSize(QSize(30, 30))
        tb.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        tb.setContextMenuPolicy(Qt.PreventContextMenu)
        for a in (self.a_add, self.a_resume, self.a_stop, self.a_stopall, self.a_delete, self.a_clean, None,
                  self.a_options, self.a_sched, self.a_qstart, self.a_qstop):
            tb.addSeparator() if a is None else tb.addAction(a)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        tb.addWidget(spacer)
        self.search = SearchBox()
        self.search.textChanged.connect(self._search_changed)
        box = QWidget()
        bl = QHBoxLayout(box)
        bl.setContentsMargins(8, 0, 6, 0)
        bl.addWidget(self.search)
        tb.addWidget(box)
        self.addToolBar(tb)
        find = QAction(self)
        find.setShortcut(QKeySequence.Find)
        find.triggered.connect(lambda: (self.search.setFocus(), self.search.selectAll()))
        self.addAction(find)

    def _build_body(self):
        self.splitter = QSplitter()
        self.splitter.setHandleWidth(1)
        self.splitter.setChildrenCollapsible(False)
        self.tree = QTreeWidget()
        self.tree.setObjectName("sidebar")
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(16)
        self.tree.setRootIsDecorated(False)
        self.tree.setItemsExpandable(False)
        self.tree.setIconSize(QSize(18, 18))
        self.tree.setItemDelegate(SidebarDelegate(self.tree))
        self.tree.setFocusPolicy(Qt.NoFocus)
        self.tree_items = {}

        def node(label, key, filt, parent=None):
            x = QTreeWidgetItem([label])
            x.setData(0, Qt.UserRole, filt)
            x.setData(0, Qt.UserRole + 5, key)
            if parent:
                parent.addChild(x)
            else:
                self.tree.addTopLevelItem(x)
            self.tree_items[filt] = x
            return x

        root = node("All Downloads", "all", ("all", None))
        for cat in CATEGORIES[1:] + ["General"]:
            node(cat, cat, ("category", cat), root)
        node("Unfinished", "unfinished", ("unfinished", None))
        node("Finished", "finished", ("finished", None))
        q = node("Queues", "queues", ("queues", None))
        node("Main download queue", "queue", ("queue", "main"), q)
        self.tree.expandAll()
        self.tree.setCurrentItem(root)
        self.tree.currentItemChanged.connect(self._filter_changed)
        self.splitter.addWidget(self.tree)

        self.model = DownloadModel(self.m)
        self.table = DownloadTable()
        self.table.setModel(self.model)
        self.table.setItemDelegateForColumn(2, StatusDelegate(self.table))
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setSortIndicator(-1, Qt.AscendingOrder)
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(32)
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        self.table.setIconSize(QSize(20, 20))
        self.table.setTextElideMode(Qt.ElideMiddle)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.Interactive)
        hh.setStretchLastSection(True)
        hh.setHighlightSections(False)
        hh.setMinimumSectionSize(50)
        hh.setContextMenuPolicy(Qt.CustomContextMenu)
        hh.customContextMenuRequested.connect(self._header_menu)
        for i, w in enumerate((340, 90, 170, 95, 110, 140, 160)):
            self.table.setColumnWidth(i, w)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._context_menu)
        self.table.doubleClicked.connect(self._double_click)
        self.table.selectionModel().selectionChanged.connect(lambda *_: self._update_actions())
        for a in (self.a_copy, self.a_selall, self.a_delete, self.a_props):
            self.table.addAction(a)
        self.splitter.addWidget(self.table)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([230, 950])
        self.setCentralWidget(self.splitter)

    def _build_statusbar(self):
        sb = self.statusBar()
        self.st_count = QLabel()
        self.st_browser = ClickLabel(self.browser_setup)
        self.st_browser.setToolTip("Fetchly browser extension status. Click to set it up.")
        self.st_limit = ClickLabel(self.toggle_limiter)
        self.st_limit.setToolTip("Click to turn the speed limiter on or off")
        self.st_speed = QLabel()
        sb.addWidget(self.st_count, 1)
        sb.addPermanentWidget(self.st_browser)
        sb.addPermanentWidget(self.st_limit)
        sb.addPermanentWidget(self.st_speed)

    def _build_tray(self):
        self.tray = None
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.tray = QSystemTrayIcon(icons.tray_icon(False), self)
        menu = QMenu()
        show = menu.addAction("Open Fetchly")
        show.triggered.connect(self.bring_to_front)
        f = show.font()
        f.setBold(True)
        show.setFont(f)
        menu.addSeparator()
        menu.addActions([self.a_add, self.a_limiter])
        menu.addSeparator()
        menu.addActions([self.a_qstart, self.a_stopall])
        menu.addSeparator()
        menu.addAction(self.a_exit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(
            lambda r: self.bring_to_front() if r in (QSystemTrayIcon.DoubleClick, QSystemTrayIcon.Trigger) else None)
        self.tray.setToolTip(APP_TITLE)
        self.tray.show()

    # ================================================================== periodic
    def _tick(self):
        self.m.tick()
        self._drain_events()
        sel = self.selected_ids()
        if self.model.refresh():
            self._select_ids(sel)
        for dlg in list(self.progress.values()):
            if alive(dlg) and dlg.isVisible():
                dlg.refresh()
        self._update_status()
        self._update_actions()
        self._update_counts()

    def _update_status(self):
        c = theme.colors()
        n = self.m.active_count()
        spd = self.m.total_speed()
        total = len(self.m.items)
        txt = f"{total} download{'s' if total != 1 else ''}"
        if n:
            txt += f"   ·   {n} active"
        if self.m.queue_running:
            txt += "   ·   Queue running"
        self.st_count.setText(txt)
        connected = bool(self.m.extension_seen) and time.time() - self.m.extension_seen < 75
        self.st_browser.setText(f"<span style='color:{c['success'] if connected else c['faint']}'>●</span> "
                                + ("Browser connected" if connected else "Browser not connected"))
        lim = self.s.speed_limit_enabled
        self.st_limit.setText(f"<span style='color:{c['warning']}'>Limit {self.s.speed_limit_kb} KB/s</span>"
                              if lim else "No speed limit")
        self.st_speed.setText(f"↓ {human_speed(spd)}" if spd else "")
        self.a_limiter.setChecked(lim)
        if self.tray:
            active = n > 0
            if active != self._tray_active:
                self.tray.setIcon(icons.tray_icon(active))
                self._tray_active = active
            self.tray.setToolTip(f"{APP_TITLE}\n{n} active download{'s' if n != 1 else ''}" +
                                 (f" · {human_speed(spd)}" if spd else ""))

    def _update_counts(self):
        counts = {("all", None): 0, ("unfinished", None): 0, ("finished", None): 0, ("queue", "main"): 0}
        for it in self.m.items.values():
            counts[("all", None)] += 1
            counts[("category", it.category)] = counts.get(("category", it.category), 0) + 1
            counts[("finished" if it.status == COMPLETE else "unfinished", None)] += 1
            if it.in_queue:
                counts[("queue", "main")] += 1
        for filt, x in self.tree_items.items():
            n = counts.get(filt, 0)
            if x.data(0, ROLE_COUNT) != n:
                x.setData(0, ROLE_COUNT, n)

    def _drain_events(self):
        while not self.m.events.empty():
            ev = self.m.events.get_nowait()
            kind = ev[0]
            if kind == "catch":
                self.catch(ev[1])
            elif kind == "catch_batch":
                self._show_dialog(D.LinksDialog(None, self.m, self.s, ev[1]))
            elif kind == "show":
                self.bring_to_front()
            elif kind == "started":
                if self.s.show_progress_dialog:
                    self.show_progress(ev[1])
            elif kind == "complete":
                self._on_complete(ev[1])
            elif kind == "error":
                it = self.m.items.get(ev[1])
                dlg = self.progress.get(ev[1])
                if it and self.tray and not (dlg and alive(dlg) and dlg.isVisible()):
                    self.tray.showMessage("Download failed", f"{it.filename}\n{it.error}", QSystemTrayIcon.Warning)
            elif kind == "removed":
                dlg = self.progress.pop(ev[1], None)
                if dlg and alive(dlg):
                    dlg.close()
            elif kind == "queue_done":
                self._queue_done(ev[1])

    def _on_complete(self, item_id):
        it = self.m.items.get(item_id)
        dlg = self.progress.pop(item_id, None)
        if dlg and alive(dlg):
            dlg.close()
            dlg.deleteLater()
        if not it:
            return
        if it.open_when_done and it.saved_path:
            try:
                open_path(it.saved_path)
            except OSError:
                pass
        if self.s.show_complete_dialog:
            self._show_dialog(D.CompleteDialog(None, self.m, self.s, it))
        elif self.tray:
            self.tray.showMessage("Download complete", it.filename, QSystemTrayIcon.Information)

    def _queue_done(self, action):
        if self.tray:
            self.tray.showMessage(APP_TITLE, "The main download queue has finished.", QSystemTrayIcon.Information)
        if action == "exit":
            self.quit_app(force=True)
        elif action == "shutdown":
            if sys.platform == "win32":
                subprocess.Popen(["shutdown", "/s", "/t", "60", "/c",
                                  "Fetchly finished downloading. Windows will shut down in 1 minute."],
                                 creationflags=0x08000000)
                box = QMessageBox(QMessageBox.Information, APP_TITLE,
                                  "Downloads finished. The computer will shut down in 1 minute.",
                                  parent=self._owner())
                cancel = box.addButton("Cancel shutdown", QMessageBox.RejectRole)
                box.addButton(QMessageBox.Ok)
                box.exec()
                if box.clickedButton() is cancel:
                    subprocess.Popen(["shutdown", "/a"], creationflags=0x08000000)
            else:
                subprocess.Popen(["shutdown", "-h", "+1"])

    def _show_dialog(self, dlg):
        self._dialogs = [d for d in self._dialogs if alive(d)]
        self._dialogs.append(dlg)
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

    # ================================================================== catching downloads
    def catch(self, payload):
        if not self.s.show_catch_dialog:
            self.m.add(payload["url"], payload.get("filename", ""), None, None, payload.get("referrer", ""),
                       payload.get("cookies", ""), payload.get("userAgent", ""), auth=payload.get("auth"),
                       kind=payload.get("kind") or None)
            return
        self._show_dialog(D.DownloadInfoDialog(None, self.m, self.s, payload))

    def _clipboard_changed(self):
        if not self.s.monitor_clipboard:
            return
        text = QApplication.clipboard().text().strip()
        if not text or text == self._last_clip:
            return
        self._last_clip = text
        if looks_like_url(text) and matches_types(filename_from_url(text), self.s.intercept_types):
            self.catch({"url": text})

    def dragEnterEvent(self, e):
        md = e.mimeData()
        if md.hasUrls() or (md.hasText() and looks_like_url(md.text())):
            e.acceptProposedAction()

    def dropEvent(self, e):
        md = e.mimeData()
        urls = [u.toString() for u in md.urls()] if md.hasUrls() else [md.text()]
        for u in urls:
            if looks_like_url(u):
                self.catch({"url": u.strip()})

    # ================================================================== selection
    def selected_ids(self):
        rows = sorted({i.row() for i in self.table.selectionModel().selectedRows()})
        return [self.model.ids[r] for r in rows if r < len(self.model.ids)]

    def _select_ids(self, ids):
        sm = self.table.selectionModel()
        sm.clearSelection()
        for i in ids:
            if i in self.model.ids:
                r = self.model.ids.index(i)
                sm.select(self.model.index(r, 0), QItemSelectionModel.Select | QItemSelectionModel.Rows)

    def _with_sel(self, fn):
        ids = self.selected_ids()
        if ids and ids[0] in self.m.items:
            try:
                fn(self.m.items[ids[0]])
            except OSError as e:
                QMessageBox.warning(self, APP_TITLE, str(e))

    def _update_actions(self):
        ids = self.selected_ids()
        items = [self.m.items[i] for i in ids if i in self.m.items]
        running = [i for i in ids if i in self.m.downloaders]
        self.a_resume.setEnabled(any(it.status != COMPLETE and it.id not in self.m.downloaders for it in items))
        self.a_stop.setEnabled(bool(running) or any(it.status == QUEUED for it in items))
        self.a_delete.setEnabled(bool(items))
        self.a_stopall.setEnabled(bool(self.m.downloaders))
        self.a_clean.setEnabled(any(it.status == COMPLETE for it in self.m.items.values()))
        done = len(items) == 1 and items[0].status == COMPLETE
        for a in (self.a_open, self.a_open_with, self.a_move):
            a.setEnabled(done)
        for a in (self.a_folder, self.a_props, self.a_redl, self.a_copy, self.a_q_add, self.a_q_del, self.a_progress):
            a.setEnabled(bool(items))
        self.a_qstart.setEnabled(not self.m.queue_running)
        self.a_qstop.setEnabled(self.m.queue_running)

    # ================================================================== actions
    def add_url(self):
        dlg = D.AddUrlDialog(self._owner())
        if dlg.exec():
            self.catch(dlg.payload())

    def batch_download(self):
        D.BatchDownloadDialog(self._owner(), self.m, self.s).exec()

    def resume_selected(self):
        for i in self.selected_ids():
            self.m.start(i)

    def stop_selected(self):
        for i in self.selected_ids():
            self.m.stop(i)

    def delete_selected(self):
        ids = self.selected_ids()
        if not ids:
            return
        box = QMessageBox(QMessageBox.Question, "Delete downloads",
                          f"Delete {len(ids)} download{'s' if len(ids) > 1 else ''} from the list?", parent=self)
        chk = QCheckBox("Also delete the downloaded files from disk")
        box.setCheckBox(chk)
        ok = box.addButton("Delete", QMessageBox.AcceptRole)
        box.addButton("Cancel", QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() is ok:
            self.m.remove(ids, delete_files=chk.isChecked())

    def delete_completed(self):
        n = sum(1 for it in self.m.items.values() if it.status == COMPLETE)
        if not n:
            return
        box = QMessageBox(QMessageBox.Question, "Delete completed",
                          f"Remove {n} completed download{'s' if n > 1 else ''} from the list?", parent=self)
        box.setInformativeText("The files stay on your computer.")
        ok = box.addButton("Remove", QMessageBox.AcceptRole)
        box.addButton("Cancel", QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() is ok:
            self.m.remove_completed()

    def redownload_selected(self):
        for i in self.selected_ids():
            if i not in self.m.downloaders:
                self.m.redownload(i)

    def open_selected(self):
        self._with_sel(lambda it: open_path(it.saved_path) if it.status == COMPLETE else None)

    def move_rename(self):
        ids = self.selected_ids()
        if not ids:
            return
        it = self.m.items[ids[0]]
        if it.status != COMPLETE or not os.path.exists(it.saved_path):
            return
        path, _ = QFileDialog.getSaveFileName(self, "Move / Rename", it.saved_path)
        if not path or os.path.normpath(path) == os.path.normpath(it.saved_path):
            return
        try:
            shutil.move(it.saved_path, path)
        except OSError as e:
            QMessageBox.warning(self, APP_TITLE, f"Couldn't move the file:\n{e}")
            return
        it.saved_path = path
        it.filename = os.path.basename(path)
        it.save_dir = os.path.dirname(path)
        self.m.mark_dirty()

    def properties(self):
        self._with_sel(lambda it: D.PropertiesDialog(self, self.m, it).exec())

    def show_progress(self, item_id):
        dlg = self.progress.get(item_id)
        if dlg is None or not alive(dlg):
            dlg = D.ProgressDialog(None, self.m, self.s, item_id)
            self.progress[item_id] = dlg
        dlg.show()
        dlg.raise_()

    def options(self):
        old_auto, old_theme = self.s.start_with_system, self.s.theme
        if D.OptionsDialog(self, self.s).exec():
            self.m.apply_speed_limit()
            if self.s.start_with_system != old_auto:
                try:
                    set_autostart(self.s.start_with_system, launch_command())
                except OSError as e:
                    QMessageBox.warning(self, APP_TITLE, f"Couldn't change the startup setting:\n{e}")
            if self.s.theme != old_theme:
                self.retheme()

    def retheme(self):
        theme.apply(QApplication.instance(), self.s.theme)
        icons.clear_cache()
        self.apply_icons()
        self.table.viewport().update()
        self.tree.viewport().update()

    def _system_theme_changed(self, *_):
        if self.s.theme == "system":
            self.retheme()

    def scheduler(self):
        D.SchedulerDialog(self, self.m, self.s).exec()

    def browser_setup(self):
        D.BrowserSetupDialog(self, self.m).exec()

    def toggle_limiter(self):
        self.s.speed_limit_enabled = not self.s.speed_limit_enabled
        self.m.apply_speed_limit()
        self.s.save()
        self._update_status()

    def import_links(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import links", "", "Text files (*.txt);;All files (*)")
        if not path:
            return
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            urls = re.findall(r"https?://[^\s\"'<>]+", f.read())
        if not urls:
            QMessageBox.information(self, APP_TITLE, "No download links were found in that file.")
            return
        self._show_dialog(D.LinksDialog(None, self.m, self.s, {"links": [{"url": u} for u in urls],
                                                               "pageUrl": path}))

    def export_links(self):
        ids = self.selected_ids() or list(self.model.ids)
        if not ids:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export download list", "downloads.txt", "Text files (*.txt)")
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(self.m.items[i].url for i in ids if i in self.m.items) + "\n")

    def _double_click(self, idx):
        it = self.model.item_at(idx.row())
        if not it:
            return
        if it.status == COMPLETE:
            try:
                open_path(it.saved_path)
            except OSError as e:
                QMessageBox.warning(self, APP_TITLE, str(e))
        else:
            self.show_progress(it.id)

    def _context_menu(self, pos):
        if not self.selected_ids():
            return
        menu = QMenu(self)
        menu.addActions([self.a_open, self.a_open_with, self.a_folder, self.a_move])
        menu.addSeparator()
        menu.addActions([self.a_resume, self.a_stop, self.a_redl, self.a_progress])
        menu.addSeparator()
        menu.addActions([self.a_q_add, self.a_q_del])
        menu.addSeparator()
        menu.addActions([self.a_copy, self.a_delete, self.a_props])
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _fill_column_menu(self, menu):
        menu.clear()
        hh = self.table.horizontalHeader()
        for i, name in enumerate(COLS):
            a = menu.addAction(name)
            a.setCheckable(True)
            a.setChecked(not hh.isSectionHidden(i))
            a.setEnabled(i != 0)
            a.toggled.connect(lambda on, col=i: hh.setSectionHidden(col, not on))

    def _header_menu(self, pos):
        menu = QMenu(self)
        self._fill_column_menu(menu)
        menu.exec(self.table.horizontalHeader().mapToGlobal(pos))

    def _filter_changed(self, cur, _prev):
        if cur:
            filt = cur.data(0, Qt.UserRole) or ("all", None)
            if filt[0] == "queues":
                filt = ("queue", "main")
            self.model.filter = filt
            self.model.refresh(force=True)

    def _search_changed(self, text):
        self.model.search = text.strip().lower()
        self.table.empty_text = "No matching downloads" if self.model.search else "No downloads yet"
        self.model.refresh(force=True)

    # ================================================================== window
    def bring_to_front(self):
        self.show()
        self.setWindowState((self.windowState() & ~Qt.WindowMinimized) | Qt.WindowActive)
        self.raise_()
        self.activateWindow()

    def _owner(self):
        """Parent for dialogs opened from the menus: the main window when it's on screen, otherwise none, so a
        dialog opened from the tray icon gets its own taskbar button instead of hiding behind other windows."""
        return self if self.isVisible() and not self.isMinimized() else None

    def send_to_tray(self):
        self.hide()
        # forget the minimized state so the window comes back normal when opened from the tray
        self.setWindowState(self.windowState() & ~Qt.WindowMinimized)
        if self.tray and not self.s.tray_hint_shown:
            self.tray.showMessage(APP_TITLE, "Fetchly keeps running here and catches your downloads. "
                                  "Click this icon to open it.", QSystemTrayIcon.Information)
            self.s.tray_hint_shown = True
        self._save_layout()

    def changeEvent(self, e):
        # Minimizing goes to the tray (like IDM), not the taskbar; download windows stay where they are.
        if (e.type() == QEvent.WindowStateChange and self.isMinimized() and not self._quitting
                and self.s.minimize_to_tray and self.tray):
            QTimer.singleShot(0, self.send_to_tray)
        super().changeEvent(e)

    def closeEvent(self, e):
        if not self._quitting and self.s.minimize_to_tray and self.tray:
            e.ignore()
            self.send_to_tray()
            return
        if not self._quitting:
            e.ignore()
            self.quit_app()
            return
        e.accept()

    def _save_layout(self):
        self.s.window_geometry = bytes(self.saveGeometry().toBase64()).decode()
        self.s.splitter_state = bytes(self.splitter.saveState().toBase64()).decode()
        self.s.header_state = bytes(self.table.horizontalHeader().saveState().toBase64()).decode()
        try:
            self.s.save()
        except OSError:
            pass

    def quit_app(self, force=False):
        if not force and self.m.active_count():
            box = QMessageBox(QMessageBox.Question, "Exit Fetchly", "Downloads are in progress.",
                              parent=self if self.isVisible() else None)
            box.setInformativeText("They will be paused and you can resume them later.")
            ok = box.addButton("Exit", QMessageBox.AcceptRole)
            box.addButton("Cancel", QMessageBox.RejectRole)
            box.exec()
            if box.clickedButton() is not ok:
                return
        self._quitting = True
        self._save_layout()
        self.timer.stop()
        self.m.shutdown()
        if self.server:
            self.server.stop()
        if self.tray:
            self.tray.hide()
        QApplication.quit()


def launch_command():
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --tray'
    exe = sys.executable.replace("python.exe", "pythonw.exe")
    main = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "main.py")
    return f'"{exe}" "{main}" --tray'
