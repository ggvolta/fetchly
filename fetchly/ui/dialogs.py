"""Dialogs: Add URL, Download File Info (catch), batch downloads, progress, complete, properties, options,
scheduler, browser setup and About."""
import os
import re
import subprocess
import sys
import threading
import time

from PySide6.QtCore import QTime, QTimer, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QFontMetrics, QGuiApplication
from PySide6.QtWidgets import (QAbstractItemView, QButtonGroup, QCheckBox, QComboBox, QDialog, QFileDialog,
                               QFormLayout, QFrame, QGridLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel,
                               QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPlainTextEdit, QProgressBar,
                               QPushButton, QRadioButton, QSpinBox, QTableWidget, QTableWidgetItem, QTabWidget,
                               QTimeEdit, QToolButton, QVBoxLayout, QWidget)

from ..config import APP_TITLE, VERSION, extension_dir
from ..engine import make_session, probe
from ..models import COMPLETE, ERROR
from ..utils import (CATEGORIES, DEFAULT_INTERCEPT_TYPES, category_for, filename_from_url, human_size, human_speed,
                     human_time, is_hls_url, looks_like_url, matches_types, open_folder, open_path, open_with,
                     sanitize_filename)
from . import icons, theme
from .widgets import SegmentBar, header, separator


def _elide(widget, text, width=420):
    return QFontMetrics(widget.font()).elidedText(text, Qt.ElideMiddle, width)


def _button(text, primary=False, slot=None, name=None):
    b = QPushButton(text)
    if primary:
        b.setObjectName("primary")
        b.setDefault(True)
    elif name:
        b.setObjectName(name)
    else:
        b.setAutoDefault(False)
    if slot:
        b.clicked.connect(slot)
    return b


def _button_row(*buttons, left=()):
    row = QHBoxLayout()
    row.setSpacing(8)
    for b in left:
        row.addWidget(b)
    row.addStretch(1)
    for b in buttons:
        row.addWidget(b)
    return row


def _browse_row(edit, parent, title, save_file=False):
    row = QHBoxLayout()
    row.setSpacing(6)
    row.addWidget(edit, 1)
    b = QToolButton()
    b.setIcon(icons.svg("folder_open", theme.colors()["muted"], "regular"))
    b.setToolTip("Browse")

    def pick():
        if save_file:
            path, _ = QFileDialog.getSaveFileName(parent, title, edit.text())
        else:
            path = QFileDialog.getExistingDirectory(parent, title, edit.text())
        if path:
            edit.setText(os.path.normpath(path))
            edit.textEdited.emit(edit.text())

    b.clicked.connect(pick)
    row.addWidget(b)
    return row


class Dialog(QDialog):
    def __init__(self, parent=None, title="", on_top=False):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowIcon(icons.app_icon())
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        if on_top:
            self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(22, 18, 22, 18)
        self.body.setSpacing(12)


def _form():
    f = QFormLayout()
    f.setHorizontalSpacing(14)
    f.setVerticalSpacing(10)
    f.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
    return f


# =========================================================================== Add URL
class AddUrlDialog(Dialog):
    def __init__(self, parent=None, url=""):
        super().__init__(parent, "Add URL")
        self.setMinimumWidth(600)
        self.body.addWidget(header("Add a new download", "Paste the address of the file you want to download.",
                                   icon_name="add_circle", icon_color=theme.ACTION_COLORS["add"]))
        f = _form()
        self.url = QLineEdit(url)
        self.url.setPlaceholderText("https://")
        if not url:
            clip = QGuiApplication.clipboard().text().strip()
            if looks_like_url(clip):
                self.url.setText(clip)
        self.url.selectAll()
        f.addRow("Address", self.url)
        self.body.addLayout(f)
        self.use_auth = QCheckBox("This server needs a user name and password")
        self.body.addWidget(self.use_auth)
        self.auth = QWidget()
        af = _form()
        af.setContentsMargins(0, 0, 0, 0)
        self.auth.setLayout(af)
        self.login, self.password = QLineEdit(), QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        af.addRow("User name", self.login)
        af.addRow("Password", self.password)
        self.auth.setVisible(False)
        self.use_auth.toggled.connect(lambda b: (self.auth.setVisible(b), self.adjustSize()))
        self.body.addWidget(self.auth)
        self.body.addLayout(_button_row(_button("Cancel", slot=self.reject), _button("OK", True, self._ok)))

    def _ok(self):
        if not looks_like_url(self.url.text()):
            QMessageBox.warning(self, APP_TITLE, "Please enter a valid http:// or https:// address.")
            return
        self.accept()

    def payload(self):
        p = {"url": self.url.text().strip()}
        if self.use_auth.isChecked() and self.login.text():
            p["auth"] = [self.login.text(), self.password.text()]
        return p


# =========================================================================== Download File Info
class DownloadInfoDialog(Dialog):
    """Shown when a download is caught from the browser, the clipboard or Add URL."""

    def __init__(self, parent, manager, settings, payload):
        super().__init__(parent, "Download File Info", on_top=True)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setMinimumWidth(660)
        self.m, self.s, self.p = manager, settings, payload
        url = payload["url"]
        self.kind = payload.get("kind") or ("hls" if is_hls_url(url, payload.get("mime", "")) else "http")
        self._user_named = bool(payload.get("filename"))
        name = sanitize_filename(payload.get("filename") or "") if self._user_named else filename_from_url(url)
        if self.kind == "hls":
            title = sanitize_filename(payload.get("title") or "") or os.path.splitext(name)[0] or "video"
            name = os.path.splitext(name)[0] + ".ts" if self._user_named else title + ".ts"
        name = name or "download"
        self._path_edited = self._cat_edited = False
        self._probe_result = self._probe_error = None

        self.file_icon = QLabel()
        self.file_icon.setFixedSize(40, 40)
        self.title = QLabel()
        self.title.setObjectName("title")
        self.title.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.size_label = QLabel()
        self.size_label.setObjectName("subtitle")
        top = QHBoxLayout()
        top.setSpacing(14)
        top.addWidget(self.file_icon, 0, Qt.AlignTop)
        col = QVBoxLayout()
        col.setSpacing(2)
        col.addWidget(self.title)
        col.addWidget(self.size_label)
        top.addLayout(col, 1)
        self.body.addLayout(top)
        self.body.addWidget(separator())

        f = _form()
        self.url = QLineEdit(url)
        f.addRow("URL", self.url)
        self.category = QComboBox()
        for c in CATEGORIES:
            self.category.addItem(icons.category(c), c)
        cat = category_for(name)
        self.category.setCurrentText(cat)
        self.category.activated.connect(self._category_changed)
        f.addRow("Category", self.category)
        self.path = QLineEdit(os.path.join(settings.dir_for(cat), name))
        self.path.textEdited.connect(self._path_changed)
        f.addRow("Save As", _browse_row(self.path, self, "Save As", save_file=True))
        self.remember = QCheckBox()
        f.addRow("", self.remember)
        self.desc = QLineEdit()
        self.desc.setPlaceholderText("Optional")
        f.addRow("Description", self.desc)
        self.body.addLayout(f)

        size = payload.get("fileSize") or -1
        if self.kind == "hls":
            self.size_label.setText("Streaming video (HLS) · size is known after download")
        else:
            self.size_label.setText(human_size(size) if size and size > 0 else "Checking file size…")
        self._refresh_header()

        self.body.addSpacing(4)
        self.body.addLayout(_button_row(
            _button("Cancel", slot=self.reject),
            _button("Download Later", slot=lambda: self._go(later=True)),
            _button("Start Download", True, lambda: self._go(later=False))))

        if self.kind != "hls":
            threading.Thread(target=self._probe, daemon=True).start()
            self._timer = QTimer(self)
            self._timer.timeout.connect(self._poll_probe)
            self._timer.start(150)

    def _refresh_header(self):
        name = os.path.basename(self.path.text()) or "download"
        self.title.setText(_elide(self.title, name, 520))
        self.file_icon.setPixmap(self.m.file_icons.for_item(name).pixmap(40, 40) if hasattr(self.m, "file_icons")
                                 else icons.svg("document", theme.colors()["muted"]).pixmap(40, 40))
        cat = self.category.currentText()
        self.remember.setText(f"Remember this folder for {cat}")

    def _path_changed(self, _):
        self._path_edited = True
        self._refresh_header()

    def _probe(self):
        p = self.p
        try:
            sess = make_session(p["url"], p.get("referrer", ""), p.get("cookies", ""), p.get("userAgent", ""),
                                p.get("auth"))
            self._probe_result = probe(sess, p["url"])
        except Exception as e:  # noqa: BLE001
            from ..engine import friendly_error
            self._probe_error = friendly_error(e)

    def _poll_probe(self):
        if self._probe_error:
            self._timer.stop()
            self.size_label.setText("Size unknown — " + self._probe_error[:70])
            return
        r = self._probe_result
        if not r:
            return
        self._timer.stop()
        if r.get("hls"):
            self.kind = "hls"
            self.size_label.setText("Streaming video (HLS) · size is known after download")
        else:
            txt = human_size(r["size"]) if r["size"] > 0 else "Size unknown"
            txt += "  ·  Resume supported" if r["resumable"] else "  ·  Resume not supported"
            self.size_label.setText(txt)
        if not self._user_named and not self._path_edited:
            name = r["filename"]
            if self.kind == "hls":
                name = (sanitize_filename(self.p.get("title") or "") or os.path.splitext(name)[0]) + ".ts"
            folder = os.path.dirname(self.path.text())
            if not self._cat_edited:
                cat = category_for(name)
                self.category.setCurrentText(cat)
                folder = self.s.dir_for(cat)
            self.path.setText(os.path.join(folder, name))
        self._refresh_header()

    def _category_changed(self, _):
        self._cat_edited = True
        cat = self.category.currentText()
        self.path.setText(os.path.join(self.s.dir_for(cat), os.path.basename(self.path.text())))
        self._refresh_header()

    def _go(self, later):
        url = self.url.text().strip()
        if not looks_like_url(url):
            QMessageBox.warning(self, APP_TITLE, "Please enter a valid http:// or https:// address.")
            return
        folder, name = os.path.split(self.path.text().strip())
        name = sanitize_filename(name)
        if not folder:
            QMessageBox.warning(self, APP_TITLE, "Please choose where to save the file.")
            return
        existing = self.m.find_by_url(url)
        if existing and existing.status != COMPLETE:
            box = QMessageBox(QMessageBox.Question, "Duplicate download link",
                              "This address is already in the download list:", parent=self)
            box.setInformativeText(f"{existing.filename or url}\n\nDo you want to add it again?")
            add = box.addButton("Add again", QMessageBox.AcceptRole)
            box.addButton("Cancel", QMessageBox.RejectRole)
            box.exec()
            if box.clickedButton() is not add:
                return
        overwrite = False
        if os.path.exists(os.path.join(folder, name)):
            box = QMessageBox(QMessageBox.Question, "File already exists",
                              f"\"{name}\" already exists in this folder.", parent=self)
            box.setInformativeText("What would you like to do?")
            rn = box.addButton("Keep both (add number)", QMessageBox.AcceptRole)
            ow = box.addButton("Replace", QMessageBox.DestructiveRole)
            box.addButton("Cancel", QMessageBox.RejectRole)
            box.exec()
            if box.clickedButton() not in (rn, ow):
                return
            overwrite = box.clickedButton() is ow
        cat = self.category.currentText()
        if self.remember.isChecked():
            self.s.category_dirs[cat] = folder
            self.s.save()
        r = self._probe_result or {}
        p = self.p
        self.m.add(url, name, folder, cat, p.get("referrer", ""), p.get("cookies", ""), p.get("userAgent", ""),
                   self.desc.text(), p.get("auth"), self.kind, start=not later, in_queue=later, overwrite=overwrite,
                   size=r.get("size", -1), resumable=r.get("resumable"))
        self.accept()


# =========================================================================== Links from a page / file
class LinksDialog(Dialog):
    """'Download all links' from the browser, or links imported from a text file."""

    def __init__(self, parent, manager, settings, payload):
        super().__init__(parent, "Download all links", on_top=True)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.resize(820, 560)
        self.m, self.s, self.p = manager, settings, payload
        seen, self.links = set(), []
        for l in payload.get("links", []):
            u = l.get("url", "")
            if u and u not in seen:
                seen.add(u)
                self.links.append(l)
        src = payload.get("pageUrl", "")
        self.body.addWidget(header("Download all links", f"{len(self.links)} links found" +
                                   (f" on {_elide(self, src, 480)}" if src else ""),
                                   icon_name="link", icon_color=theme.ACTION_COLORS["batch"]))
        top = QHBoxLayout()
        self.only_types = QCheckBox("Only file types Fetchly downloads automatically")
        self.only_types.setChecked(True)
        self.only_types.toggled.connect(self._fill)
        self.filter = QLineEdit()
        self.filter.setPlaceholderText("Filter by name or address")
        self.filter.textChanged.connect(self._fill)
        top.addWidget(self.only_types)
        top.addStretch(1)
        top.addWidget(self.filter)
        self.body.addLayout(top)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["File name", "Type", "Address"])
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.setColumnWidth(0, 260)
        self.table.setColumnWidth(1, 70)
        self.table.verticalHeader().hide()
        self.table.setShowGrid(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.body.addWidget(self.table, 1)
        self.count = QLabel()
        self.count.setObjectName("subtitle")
        f = _form()
        self.folder = QLineEdit("")
        self.folder.setPlaceholderText("Sort into category folders automatically")
        f.addRow("Save to", _browse_row(self.folder, self, "Save to"))
        self.body.addLayout(f)
        self.start_queue = QCheckBox("Start downloading now")
        self.start_queue.setChecked(True)
        self.body.addLayout(_button_row(
            _button("Cancel", slot=self.reject), _button("Add to Queue", True, self._ok),
            left=(_button("Check all", slot=lambda: self._check_all(True)),
                  _button("Uncheck all", slot=lambda: self._check_all(False)), self.count, self.start_queue)))
        self._fill()

    def _fill(self):
        rows = self.links
        if self.only_types.isChecked():
            rows = [l for l in rows if matches_types(filename_from_url(l["url"]), self.s.intercept_types)]
        q = self.filter.text().strip().lower()
        if q:
            rows = [l for l in rows if q in l["url"].lower() or q in l.get("text", "").lower()]
        self.table.setRowCount(len(rows))
        for i, l in enumerate(rows):
            name = filename_from_url(l["url"]) or l.get("text", "")[:60] or "(no name)"
            a = QTableWidgetItem(self.m.file_icons.for_item(name), name)
            a.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            a.setCheckState(Qt.Checked if self.only_types.isChecked() else Qt.Unchecked)
            a.setData(Qt.UserRole, l["url"])
            self.table.setItem(i, 0, a)
            ext = os.path.splitext(name)[1].lstrip(".").upper()
            self.table.setItem(i, 1, QTableWidgetItem(ext))
            self.table.setItem(i, 2, QTableWidgetItem(l["url"]))
        self.count.setText(f"{len(rows)} shown")

    def _check_all(self, v):
        for i in range(self.table.rowCount()):
            self.table.item(i, 0).setCheckState(Qt.Checked if v else Qt.Unchecked)

    def _ok(self):
        urls = [self.table.item(i, 0).data(Qt.UserRole) for i in range(self.table.rowCount())
                if self.table.item(i, 0).checkState() == Qt.Checked]
        if not urls:
            QMessageBox.information(self, APP_TITLE, "No links are checked.")
            return
        folder = self.folder.text().strip() or None
        for u in urls:
            self.m.add(u, "", folder, None, self.p.get("pageUrl", ""), self.p.get("cookies", ""),
                       self.p.get("userAgent", ""), start=False, in_queue=True)
        if self.start_queue.isChecked():
            self.m.start_queue()
        self.accept()


# =========================================================================== Batch download (wildcard)
class BatchDownloadDialog(Dialog):
    """IDM's 'Add batch download': http://site/img*.jpg with * replaced by a range."""

    def __init__(self, parent, manager, settings):
        super().__init__(parent, "Add batch download")
        self.setMinimumWidth(640)
        self.m, self.s = manager, settings
        self.body.addWidget(header("Add batch download",
                                   "Use * in the address where a number or letter changes, e.g. "
                                   "https://example.com/photos/img*.jpg",
                                   icon_name="document_queue_add", icon_color=theme.ACTION_COLORS["batch"]))
        f = _form()
        self.url = QLineEdit()
        self.url.setPlaceholderText("https://example.com/files/part*.zip")
        f.addRow("Address", self.url)
        self.body.addLayout(f)
        g = QGroupBox("Replace * with")
        gl = QGridLayout(g)
        self.mode_num = QRadioButton("Numbers")
        self.mode_let = QRadioButton("Letters")
        self.mode_num.setChecked(True)
        grp = QButtonGroup(self)
        grp.addButton(self.mode_num)
        grp.addButton(self.mode_let)
        self.n_from, self.n_to, self.width = QSpinBox(), QSpinBox(), QSpinBox()
        for sp in (self.n_from, self.n_to):
            sp.setRange(0, 999999)
        self.n_from.setValue(1)
        self.n_to.setValue(10)
        self.width.setRange(0, 8)
        self.width.setSpecialValueText("Auto")
        self.l_from, self.l_to = QLineEdit("a"), QLineEdit("z")
        for e in (self.l_from, self.l_to):
            e.setMaxLength(1)
            e.setFixedWidth(50)
        gl.addWidget(self.mode_num, 0, 0)
        gl.addWidget(QLabel("From"), 0, 1)
        gl.addWidget(self.n_from, 0, 2)
        gl.addWidget(QLabel("To"), 0, 3)
        gl.addWidget(self.n_to, 0, 4)
        gl.addWidget(QLabel("Wildcard size"), 0, 5)
        gl.addWidget(self.width, 0, 6)
        gl.addWidget(self.mode_let, 1, 0)
        gl.addWidget(QLabel("From"), 1, 1)
        gl.addWidget(self.l_from, 1, 2)
        gl.addWidget(QLabel("To"), 1, 3)
        gl.addWidget(self.l_to, 1, 4)
        gl.setColumnStretch(7, 1)
        self.body.addWidget(g)
        self.preview = QLabel()
        self.preview.setObjectName("subtitle")
        self.preview.setWordWrap(True)
        self.body.addWidget(self.preview)
        f2 = _form()
        self.folder = QLineEdit("")
        self.folder.setPlaceholderText("Sort into category folders automatically")
        f2.addRow("Save to", _browse_row(self.folder, self, "Save to"))
        self.body.addLayout(f2)
        self.start_now = QCheckBox("Start downloading now")
        self.start_now.setChecked(True)
        self.body.addLayout(_button_row(_button("Cancel", slot=self.reject),
                                        _button("Add to Queue", True, self._ok), left=(self.start_now,)))
        for w in (self.url, self.l_from, self.l_to):
            w.textChanged.connect(self._update)
        for w in (self.n_from, self.n_to, self.width):
            w.valueChanged.connect(self._update)
        self.mode_num.toggled.connect(self._update)
        self._update()

    def urls(self):
        u = self.url.text().strip()
        if "*" not in u or not looks_like_url(u.replace("*", "1")):
            return []
        if self.mode_num.isChecked():
            a, b = self.n_from.value(), self.n_to.value()
            w = self.width.value()
            step = 1 if b >= a else -1
            vals = [str(i).zfill(w) for i in range(a, b + step, step)]
        else:
            a, b = (self.l_from.text() or "a"), (self.l_to.text() or "z")
            step = 1 if ord(b) >= ord(a) else -1
            vals = [chr(c) for c in range(ord(a), ord(b) + step, step)]
        return [u.replace("*", v) for v in vals[:10000]]

    def _update(self):
        urls = self.urls()
        if not urls:
            self.preview.setText("Enter an address that contains *.")
        else:
            self.preview.setText(f"{len(urls)} files:  {_elide(self.preview, urls[0], 260)}  …  "
                                 f"{_elide(self.preview, urls[-1], 260)}")

    def _ok(self):
        urls = self.urls()
        if not urls:
            QMessageBox.warning(self, APP_TITLE, "Enter an address that contains * where the number changes.")
            return
        folder = self.folder.text().strip() or None
        for u in urls:
            self.m.add(u, "", folder, None, start=False, in_queue=True)
        if self.start_now.isChecked():
            self.m.start_queue()
        self.accept()


# =========================================================================== Progress
class ProgressDialog(Dialog):
    """Per-download window: status, connection map, per-download speed limit, completion options."""

    def __init__(self, parent, manager, settings, item_id):
        super().__init__(parent)
        self.m, self.s, self.item_id = manager, settings, item_id
        self.setMinimumWidth(600)
        self.body.setSpacing(10)

        self.title = QLabel()
        self.title.setObjectName("title")
        self.icon = QLabel()
        self.icon.setFixedSize(36, 36)
        top = QHBoxLayout()
        top.setSpacing(12)
        top.addWidget(self.icon, 0, Qt.AlignTop)
        col = QVBoxLayout()
        col.setSpacing(2)
        col.addWidget(self.title)
        self.url_label = QLabel()
        self.url_label.setObjectName("subtitle")
        col.addWidget(self.url_label)
        top.addLayout(col, 1)
        self.big_pct = QLabel()
        self.big_pct.setStyleSheet("font-size: 20pt; font-weight: 600;")
        top.addWidget(self.big_pct, 0, Qt.AlignTop)
        self.body.addLayout(top)
        self.bar = QProgressBar()
        self.bar.setRange(0, 1000)
        self.bar.setTextVisible(False)
        self.body.addWidget(self.bar)

        tabs = QTabWidget()
        st = QWidget()
        g = QGridLayout(st)
        g.setContentsMargins(14, 12, 14, 12)
        g.setHorizontalSpacing(18)
        g.setVerticalSpacing(8)
        self.labels = {}
        keys = ("Status", "File size", "Downloaded", "Transfer rate", "Time left", "Resume capability")
        for i, key in enumerate(keys):
            r, c = divmod(i, 2)
            k = QLabel(key)
            k.setObjectName("subtitle")
            v = QLabel()
            v.setTextInteractionFlags(Qt.TextSelectableByMouse)
            g.addWidget(k, r, c * 2)
            g.addWidget(v, r, c * 2 + 1)
            self.labels[key] = v
        g.setColumnStretch(1, 1)
        g.setColumnStretch(3, 1)
        tabs.addTab(st, "Download status")

        sl = QWidget()
        f = _form()
        sl.setLayout(f)
        f.setContentsMargins(14, 12, 14, 12)
        self.use_limit = QCheckBox("Limit the speed of this download")
        self.limit = QSpinBox()
        self.limit.setRange(1, 1_000_000)
        self.limit.setSuffix(" KB/s")
        self.limit.setValue(512)
        f.addRow(self.use_limit)
        f.addRow("Maximum speed", self.limit)
        self.use_limit.toggled.connect(self._apply_limit)
        self.limit.editingFinished.connect(self._apply_limit)
        tabs.addTab(sl, "Speed Limiter")

        oc = QWidget()
        v = QVBoxLayout(oc)
        v.setContentsMargins(14, 12, 14, 12)
        self.show_complete = QCheckBox("Show the download complete dialog")
        self.show_complete.setChecked(settings.show_complete_dialog)
        self.show_complete.toggled.connect(lambda b: setattr(self.s, "show_complete_dialog", b))
        self.open_when_done = QCheckBox("Open the file when the download finishes")
        self.open_when_done.toggled.connect(self._set_open)
        v.addWidget(self.show_complete)
        v.addWidget(self.open_when_done)
        v.addStretch(1)
        tabs.addTab(oc, "Options on completion")
        self.body.addWidget(tabs)

        self.details = QFrame()
        dl = QVBoxLayout(self.details)
        dl.setContentsMargins(0, 4, 0, 0)
        dl.setSpacing(8)
        lbl = QLabel("Start positions and download progress by connections")
        lbl.setObjectName("sectionTitle")
        dl.addWidget(lbl)
        self.segbar = SegmentBar()
        dl.addWidget(self.segbar)
        self.conns = QTableWidget(0, 3)
        self.conns.setHorizontalHeaderLabels(["N.", "Downloaded", "Info"])
        self.conns.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.conns.verticalHeader().hide()
        self.conns.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.conns.setColumnWidth(0, 44)
        self.conns.setColumnWidth(1, 120)
        self.conns.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.conns.setSelectionMode(QAbstractItemView.NoSelection)
        self.conns.setShowGrid(False)
        self.conns.setFocusPolicy(Qt.NoFocus)
        self.conns.verticalHeader().setDefaultSectionSize(26)
        self.conns.setMinimumHeight(150)
        dl.addWidget(self.conns)
        self.body.addWidget(self.details)

        self.toggle = _button("Hide details", name="flat", slot=self._toggle_details)
        self.pause_btn = _button("Pause", True, self._pause_resume)
        self.cancel_btn = _button("Cancel", slot=self._cancel)
        self.body.addLayout(_button_row(self.cancel_btn, self.pause_btn, left=(self.toggle,)))

        it = manager.items.get(item_id)
        if it and it.speed_limit_kb:
            self.use_limit.setChecked(True)
            self.limit.setValue(it.speed_limit_kb)
        if it:
            self.open_when_done.setChecked(it.open_when_done)
        self.refresh()

    def _apply_limit(self):
        self.m.set_item_speed_limit(self.item_id, self.limit.value() if self.use_limit.isChecked() else 0)

    def _set_open(self, b):
        it = self.m.items.get(self.item_id)
        if it:
            it.open_when_done = b

    def _toggle_details(self):
        vis = not self.details.isVisible()
        self.details.setVisible(vis)
        self.toggle.setText("Hide details" if vis else "Show details")
        QTimer.singleShot(0, self.adjustSize)

    def _pause_resume(self):
        if self.item_id in self.m.downloaders:
            self.m.stop(self.item_id)
        else:
            self.m.start(self.item_id)

    def _cancel(self):
        self.m.stop(self.item_id)
        self.close()

    def refresh(self):
        it = self.m.items.get(self.item_id)
        if not it:
            self.close()
            return
        c = theme.colors()
        prog = it.progress()
        running = self.item_id in self.m.downloaders and it.status != COMPLETE
        name = it.filename or filename_from_url(it.url) or "Download"
        self.setWindowTitle((f"{prog * 100:.0f}% " if prog is not None else "") + name)
        self.title.setText(_elide(self.title, name, 430))
        self.url_label.setText(_elide(self.url_label, it.url, 430))
        self.url_label.setToolTip(it.url)
        self.icon.setPixmap(self.m.file_icons.for_item(name, it.saved_path).pixmap(36, 36))
        self.big_pct.setText(f"{prog * 100:.0f}%" if prog is not None else "")
        L = self.labels
        if it.status == ERROR:
            L["Status"].setText(f"<span style='color:{c['danger']}'>Error: {it.error}</span>")
        elif running:
            L["Status"].setText("Receiving data…" if it.speed > 0 else "Connecting…")
        elif it.status == COMPLETE:
            L["Status"].setText(f"<span style='color:{c['success']}'>Complete</span>")
        else:
            L["Status"].setText("Paused" if it.downloaded() else "Stopped")
        L["File size"].setText(human_size(it.size) if it.size > 0 else
                               (f"{len(it.hls_done)} of {it.hls_total} parts" if it.kind == "hls" and it.hls_total
                                else "Unknown"))
        dl = human_size(it.downloaded()) or "0 Bytes"
        L["Downloaded"].setText(f"{dl}  ({prog * 100:.2f}%)" if prog is not None else dl)
        L["Transfer rate"].setText(human_speed(it.speed) if running else "—")
        L["Time left"].setText(human_time(it.eta) if running and it.eta > 0 else "—")
        L["Resume capability"].setText("Yes" if (it.resumable or it.kind == "hls") else
                                       ("No" if it.resumable is False else "Unknown"))
        self.bar.setValue(int((prog or 0) * 1000))
        self.pause_btn.setText("Pause" if running else "Resume")
        self.pause_btn.setEnabled(it.status != COMPLETE)
        if it.status == COMPLETE:
            self.segbar.set_complete()
        elif it.kind == "hls":
            self.segbar.set_blocks(list(it.hls_done), it.hls_total)
        else:
            self.segbar.set_http(it.segments, it.size)
        d = self.m.downloaders.get(self.item_id)
        rows = d.connections() if d else []
        self.conns.setRowCount(len(rows))
        for r, (n, got, info) in enumerate(rows):
            for col, val in enumerate((n, human_size(got) or "0 Bytes", info)):
                cell = self.conns.item(r, col)
                if cell is None:
                    self.conns.setItem(r, col, QTableWidgetItem(val))
                elif cell.text() != val:
                    cell.setText(val)


# =========================================================================== Complete
class CompleteDialog(Dialog):
    def __init__(self, parent, manager, settings, item):
        super().__init__(parent, "Download complete", on_top=True)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.s = settings
        self.path = item.saved_path
        self.setMinimumWidth(580)
        top = QHBoxLayout()
        top.setSpacing(14)
        ic = QLabel()
        ic.setPixmap(manager.file_icons.for_item(item.filename, item.saved_path).pixmap(44, 44))
        top.addWidget(ic, 0, Qt.AlignTop)
        col = QVBoxLayout()
        col.setSpacing(2)
        badge = QLabel(f"<span style='color:{theme.colors()['success']}; font-weight:600'>✓ Download complete</span>")
        col.addWidget(badge)
        t = QLabel(_elide(self, item.filename, 440))
        t.setObjectName("title")
        col.addWidget(t)
        sub = QLabel(human_size(item.size))
        sub.setObjectName("subtitle")
        col.addWidget(sub)
        top.addLayout(col, 1)
        self.body.addLayout(top)
        f = _form()
        addr = QLabel(_elide(self, item.url, 440))
        addr.setToolTip(item.url)
        addr.setObjectName("subtitle")
        f.addRow("Address", addr)
        saved = QLineEdit(item.saved_path)
        saved.setReadOnly(True)
        f.addRow("Saved as", saved)
        self.body.addLayout(f)
        self.dont = QCheckBox("Don't show this dialog again")
        self.dont.toggled.connect(self._dont)
        self.body.addWidget(self.dont)
        self.body.addLayout(_button_row(
            _button("Close", slot=self.close),
            _button("Open", True, lambda: self._do(open_path)),
            left=(_button("Open folder", slot=lambda: self._do(open_folder)),
                  _button("Open with…", slot=lambda: self._do(open_with)))))

    def _do(self, fn):
        try:
            fn(self.path)
        except OSError as e:
            QMessageBox.warning(self, APP_TITLE, str(e))
        self.close()

    def _dont(self, b):
        self.s.show_complete_dialog = not b
        self.s.save()


# =========================================================================== Properties
class PropertiesDialog(Dialog):
    def __init__(self, parent, manager, item):
        super().__init__(parent, "Properties")
        self.m, self.it = manager, item
        self.setMinimumWidth(640)
        self.body.addWidget(header(_elide(self, item.filename or filename_from_url(item.url), 440),
                                   f"{item.category} · {human_size(item.size) or 'size unknown'}",
                                   pixmap=manager.file_icons.for_item(item.filename, item.saved_path).pixmap(36, 36)))
        f = _form()

        def ro(text):
            e = QLineEdit(text)
            e.setReadOnly(True)
            return e
        status = item.status.capitalize() + (f" — {item.error}" if item.error else "")
        f.addRow("Status", ro(status))
        f.addRow("Saved to", ro(item.target_path))
        self.url = QLineEdit(item.url)
        self.url.setToolTip("If the link has expired, paste a fresh address here and resume the download.")
        f.addRow("Address", self.url)
        hint = QLabel("Link expired? Paste a fresh address above, then resume.")
        hint.setObjectName("subtitle")
        f.addRow("", hint)
        f.addRow("Referrer", ro(item.referrer or "—"))
        self.desc = QLineEdit(item.description)
        f.addRow("Description", self.desc)
        self.body.addLayout(f)
        self.body.addLayout(_button_row(_button("Cancel", slot=self.reject), _button("Save", True, self._ok)))

    def _ok(self):
        url = self.url.text().strip()
        if url != self.it.url:
            if not looks_like_url(url):
                QMessageBox.warning(self, APP_TITLE, "That isn't a valid address.")
                return
            self.m.update_address(self.it.id, url)
        self.it.description = self.desc.text()
        self.m.mark_dirty()
        self.accept()


# =========================================================================== Options
class OptionsDialog(Dialog):
    def __init__(self, parent, settings):
        super().__init__(parent, "Options")
        self.s = settings
        self.resize(680, 520)
        tabs = QTabWidget()
        self.body.addWidget(tabs, 1)

        def page():
            w = QWidget()
            v = QVBoxLayout(w)
            v.setContentsMargins(18, 16, 18, 16)
            v.setSpacing(10)
            return w, v

        # General
        g, v = page()
        self.chk = {}
        for key, txt in (("monitor_clipboard", "Watch the clipboard for download links"),
                         ("show_catch_dialog", "Ask where to save before each download (Download File Info)"),
                         ("show_progress_dialog", "Show the progress window when a download starts"),
                         ("show_complete_dialog", "Show the Download complete dialog"),
                         ("minimize_to_tray", "Keep Fetchly running in the notification area when closed")):
            c = QCheckBox(txt)
            c.setChecked(getattr(settings, key))
            self.chk[key] = c
            v.addWidget(c)
        self.autostart = QCheckBox("Start Fetchly when I sign in to Windows")
        self.autostart.setChecked(settings.start_with_system)
        self.autostart.setEnabled(sys.platform == "win32")
        v.addWidget(self.autostart)
        v.addWidget(separator())
        f = _form()
        self.theme = QComboBox()
        for label, val in (("Use Windows setting", "system"), ("Light", "light"), ("Dark", "dark")):
            self.theme.addItem(label, val)
        self.theme.setCurrentIndex(max(0, self.theme.findData(settings.theme)))
        f.addRow("Appearance", self.theme)
        v.addLayout(f)
        v.addStretch(1)
        tabs.addTab(g, "General")

        # File types / browser
        b, v = page()
        self.integration = QCheckBox("Take over downloads from the browser")
        self.integration.setChecked(settings.browser_integration)
        v.addWidget(self.integration)
        lab = QLabel("Automatically download these file types with Fetchly:")
        lab.setObjectName("sectionTitle")
        v.addWidget(lab)
        self.types = QPlainTextEdit(" ".join(settings.intercept_types))
        self.types.setFixedHeight(110)
        v.addWidget(self.types)
        dflt = _button("Restore defaults", slot=lambda: self.types.setPlainText(" ".join(DEFAULT_INTERCEPT_TYPES)))
        v.addLayout(_button_row(left=(dflt,)))
        f = _form()
        self.min_kb = QSpinBox()
        self.min_kb.setRange(0, 10_000_000)
        self.min_kb.setSuffix(" KB")
        self.min_kb.setSpecialValueText("No minimum")
        self.min_kb.setValue(settings.min_intercept_kb)
        f.addRow("Ignore files smaller than", self.min_kb)
        self.port = QSpinBox()
        self.port.setRange(1024, 65535)
        self.port.setValue(settings.port)
        f.addRow("Extension port", self.port)
        v.addLayout(f)
        hint = QLabel("Changing the port takes effect after Fetchly restarts. Set the same port in the "
                      "extension's popup.")
        hint.setObjectName("subtitle")
        hint.setWordWrap(True)
        v.addWidget(hint)
        v.addStretch(1)
        tabs.addTab(b, "File Types")

        # Connection
        c, v = page()
        f = _form()
        self.conns = QComboBox()
        for n in (1, 2, 4, 8, 16, 24, 32):
            self.conns.addItem(f"{n}", n)
        self.conns.setCurrentIndex(max(0, self.conns.findData(settings.max_connections)))
        f.addRow("Connections per download", self.conns)
        self.simul = QSpinBox()
        self.simul.setRange(1, 20)
        self.simul.setValue(settings.max_simultaneous)
        f.addRow("Queue: files at the same time", self.simul)
        v.addLayout(f)
        v.addWidget(separator())
        self.limit_on = QCheckBox("Limit total download speed (Speed Limiter)")
        self.limit_on.setChecked(settings.speed_limit_enabled)
        v.addWidget(self.limit_on)
        f = _form()
        self.limit = QSpinBox()
        self.limit.setRange(1, 10_000_000)
        self.limit.setSuffix(" KB/s")
        self.limit.setValue(settings.speed_limit_kb)
        f.addRow("Maximum speed", self.limit)
        v.addLayout(f)
        v.addWidget(separator())
        f = _form()
        self.proxy = QLineEdit(settings.proxy)
        self.proxy.setPlaceholderText("Use Windows proxy settings")
        f.addRow("Proxy", self.proxy)
        v.addLayout(f)
        hint = QLabel("Leave empty to use the system proxy, or enter e.g. http://127.0.0.1:8080 "
                      "or socks5://127.0.0.1:1080")
        hint.setObjectName("subtitle")
        hint.setWordWrap(True)
        v.addWidget(hint)
        v.addStretch(1)
        tabs.addTab(c, "Connection")

        # Save to
        sv, v = page()
        f = _form()
        self.root = QLineEdit(settings.download_root)
        f.addRow("Download folder", _browse_row(self.root, self, "Download folder"))
        self.cat_dirs = {}
        for cat in CATEGORIES:
            e = QLineEdit(settings.category_dirs.get(cat, ""))
            e.setPlaceholderText(settings.dir_for(cat) if not settings.category_dirs.get(cat) else "")
            self.cat_dirs[cat] = e
            f.addRow(cat, _browse_row(e, self, f"Folder for {cat}"))
        v.addLayout(f)
        hint = QLabel("Leave a category empty to use a subfolder of the download folder.")
        hint.setObjectName("subtitle")
        v.addWidget(hint)
        v.addStretch(1)
        tabs.addTab(sv, "Save To")

        self.body.addLayout(_button_row(_button("Cancel", slot=self.reject), _button("OK", True, self._ok)))

    def _ok(self):
        s = self.s
        proxy = self.proxy.text().strip()
        if proxy and not re.match(r"^(https?|socks5h?|socks4)://[^\s/]+:\d+/?$", proxy, re.I):
            QMessageBox.warning(self, APP_TITLE, "The proxy should look like http://host:port or socks5://host:port.")
            return
        for k, c in self.chk.items():
            setattr(s, k, c.isChecked())
        s.start_with_system = self.autostart.isChecked()
        s.theme = self.theme.currentData()
        s.browser_integration = self.integration.isChecked()
        s.intercept_types = [t.upper().lstrip(".") for t in self.types.toPlainText().replace(",", " ").split() if t]
        s.min_intercept_kb = self.min_kb.value()
        s.port = self.port.value()
        s.max_connections = self.conns.currentData()
        s.max_simultaneous = self.simul.value()
        s.speed_limit_enabled = self.limit_on.isChecked()
        s.speed_limit_kb = self.limit.value()
        s.proxy = proxy
        s.download_root = self.root.text().strip() or s.download_root
        s.category_dirs = {k: e.text().strip() for k, e in self.cat_dirs.items() if e.text().strip()}
        s.save()
        self.accept()


# =========================================================================== Scheduler
class SchedulerDialog(Dialog):
    DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    def __init__(self, parent, manager, settings):
        super().__init__(parent, "Scheduler")
        self.m, self.s = manager, settings
        sch = settings.scheduler
        self.resize(860, 470)
        self.body.addWidget(header("Main download queue", "Start and stop the queue automatically.",
                                   icon_name="calendar_clock", icon_color=theme.ACTION_COLORS["scheduler"]))
        cols = QHBoxLayout()
        cols.setSpacing(16)
        left = QVBoxLayout()
        g = QGroupBox("Schedule")
        f = QGridLayout(g)
        f.setVerticalSpacing(10)
        self.start_on = QCheckBox("Start download at")
        self.start_on.setChecked(sch["enabled"])
        self.start_time = QTimeEdit(QTime.fromString(sch["start_time"], "HH:mm"))
        self.start_time.setDisplayFormat("HH:mm")
        f.addWidget(self.start_on, 0, 0)
        f.addWidget(self.start_time, 0, 1)
        self.once = QRadioButton("Once")
        self.daily = QRadioButton("Daily on")
        (self.once if sch.get("once") else self.daily).setChecked(True)
        f.addWidget(self.once, 1, 0)
        f.addWidget(self.daily, 2, 0)
        days = QGridLayout()
        days.setContentsMargins(24, 0, 0, 0)
        self.day_boxes = []
        for i, d in enumerate(self.DAYS):
            c = QCheckBox(d)
            c.setChecked(i in sch.get("days", []))
            self.day_boxes.append(c)
            days.addWidget(c, i // 4, i % 4)
        f.addLayout(days, 3, 0, 1, 2)
        self.stop_on = QCheckBox("Stop download at")
        self.stop_on.setChecked(sch["stop_enabled"])
        self.stop_time = QTimeEdit(QTime.fromString(sch["stop_time"], "HH:mm"))
        self.stop_time.setDisplayFormat("HH:mm")
        f.addWidget(self.stop_on, 4, 0)
        f.addWidget(self.stop_time, 4, 1)
        left.addWidget(g)
        g2 = QGroupBox("When the queue is done")
        f2 = _form()
        g2.setLayout(f2)
        self.on_done = QComboBox()
        for label, val in (("Do nothing", "none"), ("Exit Fetchly", "exit"), ("Turn off computer", "shutdown")):
            self.on_done.addItem(label, val)
        self.on_done.setCurrentIndex(max(0, self.on_done.findData(sch.get("on_done", "none"))))
        f2.addRow("Then", self.on_done)
        self.simul = QSpinBox()
        self.simul.setRange(1, 20)
        self.simul.setValue(settings.max_simultaneous)
        f2.addRow("Files at the same time", self.simul)
        left.addWidget(g2)
        left.addStretch(1)
        cols.addLayout(left, 5)

        right = QVBoxLayout()
        lab = QLabel("Files in the queue")
        lab.setObjectName("sectionTitle")
        right.addWidget(lab)
        self.list = QListWidget()
        right.addWidget(self.list, 1)
        mv = QHBoxLayout()
        for name, tip, fn in (("arrow_up", "Move up", lambda: self._move(-1)),
                              ("arrow_down", "Move down", lambda: self._move(1)),
                              ("dismiss", "Remove from queue", self._remove)):
            b = QToolButton()
            b.setIcon(icons.svg(name, theme.colors()["muted"], "regular"))
            b.setToolTip(tip)
            b.clicked.connect(fn)
            mv.addWidget(b)
        mv.addStretch(1)
        right.addLayout(mv)
        cols.addLayout(right, 4)
        self.body.addLayout(cols, 1)
        self.body.addLayout(_button_row(
            _button("Close", slot=self._close), _button("Apply", slot=self._apply),
            _button("Start Now", True, self._start_now), left=(_button("Stop Queue", slot=self._stop),)))
        self._fill()

    def _fill(self, select=None):
        self.list.clear()
        for it in self.m.queue_items():
            name = it.filename or filename_from_url(it.url) or it.url
            li = QListWidgetItem(self.m.file_icons.for_item(name), f"{name}   ·   {it.status}")
            li.setData(Qt.UserRole, it.id)
            self.list.addItem(li)
            if it.id == select:
                self.list.setCurrentItem(li)

    def _current(self):
        li = self.list.currentItem()
        return li.data(Qt.UserRole) if li else None

    def _move(self, d):
        i = self._current()
        if i:
            self.m.move_in_queue(i, d)
            self._fill(i)

    def _remove(self):
        i = self._current()
        if i:
            self.m.set_in_queue([i], False)
            self._fill()

    def _apply(self):
        sch = self.s.scheduler
        sch["enabled"] = self.start_on.isChecked()
        sch["start_time"] = self.start_time.time().toString("HH:mm")
        sch["once"] = self.once.isChecked()
        sch["days"] = list(range(7)) if self.once.isChecked() else \
            [i for i, c in enumerate(self.day_boxes) if c.isChecked()]
        sch["stop_enabled"] = self.stop_on.isChecked()
        sch["stop_time"] = self.stop_time.time().toString("HH:mm")
        sch["on_done"] = self.on_done.currentData()
        self.s.max_simultaneous = self.simul.value()
        self.s.save()

    def _start_now(self):
        self._apply()
        self.m.start_queue()
        self._fill()

    def _stop(self):
        self.m.stop_queue()
        self._fill()

    def _close(self):
        self._apply()
        self.accept()


# =========================================================================== Browser setup
def find_browsers():
    """Installed Chromium browsers on Windows: [(name, exe, extensions_url)]."""
    found = []
    if sys.platform != "win32":
        return found
    import winreg
    cands = (("Google Chrome", "chrome.exe", "chrome://extensions/"),
             ("Microsoft Edge", "msedge.exe", "edge://extensions/"),
             ("Brave", "brave.exe", "brave://extensions/"),
             ("Opera", "opera.exe", "opera://extensions"),
             ("Vivaldi", "vivaldi.exe", "vivaldi://extensions/"))
    for name, exe, page in cands:
        path = None
        for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            try:
                with winreg.OpenKey(hive, rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{exe}") as k:
                    path = winreg.QueryValue(k, None)
                    break
            except OSError:
                continue
        if path and os.path.exists(path):
            found.append((name, path, page))
    return found


class BrowserSetupDialog(Dialog):
    """Guides the user through adding the Fetchly extension, and shows when it's connected."""

    def __init__(self, parent, manager):
        super().__init__(parent, "Browser integration")
        self.m = manager
        self.setMinimumWidth(640)
        self.body.addWidget(header("Connect Fetchly to your browser",
                                   "With the Fetchly extension, browser downloads, links and videos go straight "
                                   "to Fetchly automatically.",
                                   pixmap=icons.logo_pixmap(40)))
        self.status = QLabel()
        self.status.setObjectName("card")
        self.status.setStyleSheet("padding: 10px 12px;")
        self.body.addWidget(self.status)
        path = extension_dir()
        steps = QLabel(
            "<ol style='margin-left:-18px; line-height:150%'>"
            "<li>Open your browser's extensions page (buttons below).</li>"
            "<li>Turn on <b>Developer mode</b> (top-right in Chrome, left side in Edge).</li>"
            "<li>Click <b>Load unpacked</b> and select the Fetchly extension folder:<br>"
            f"<code>{path}</code></li>"
            "<li>Pin the Fetchly icon. This window confirms as soon as it connects.</li></ol>")
        steps.setWordWrap(True)
        steps.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.body.addWidget(steps)
        row = QHBoxLayout()
        row.setSpacing(8)
        browsers = find_browsers()
        for name, exe, page in browsers:
            b = _button(f"Open {name}", slot=lambda _=False, e=exe, pg=page: self._open_browser(e, pg))
            row.addWidget(b)
        if not browsers:
            note = QLabel("Open chrome://extensions or edge://extensions in your browser.")
            note.setObjectName("subtitle")
            row.addWidget(note)
        row.addStretch(1)
        self.body.addLayout(row)
        self.body.addWidget(separator())
        self.body.addLayout(_button_row(
            _button("Close", True, self.accept),
            left=(_button("Show extension folder", slot=lambda: self._open_folder(path)),
                  _button("Copy folder path", slot=lambda: self._copy(path)))))
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(1000)
        self._refresh()

    def _open_browser(self, exe, page):
        try:
            subprocess.Popen([exe, page])
        except OSError as e:
            QMessageBox.warning(self, APP_TITLE, str(e))
        self._copy(extension_dir(), quiet=True)

    def _open_folder(self, path):
        if os.path.isdir(path):
            open_path(path)

    def _copy(self, path, quiet=False):
        QGuiApplication.clipboard().setText(path)
        if not quiet:
            self.status.setText(self.status.text().split("<br>")[0] + "<br><small>Folder path copied.</small>")

    def _refresh(self):
        c = theme.colors()
        seen = self.m.extension_seen
        if seen and time.time() - seen < 75:
            br = self.m.extension_browser or "browser"
            self.status.setText(f"<span style='color:{c['success']}; font-weight:600'>● Connected</span>"
                                f" &nbsp;The Fetchly extension in {br} is talking to Fetchly.")
        else:
            self.status.setText(f"<span style='color:{c['warning']}; font-weight:600'>● Not connected yet</span>"
                                " &nbsp;Follow the steps below.")


# =========================================================================== About
class AboutDialog(Dialog):
    def __init__(self, parent):
        super().__init__(parent, f"About {APP_TITLE}")
        self.setFixedWidth(460)
        logo = QLabel()
        logo.setPixmap(icons.logo_pixmap(72))
        logo.setAlignment(Qt.AlignCenter)
        self.body.addWidget(logo)
        t = QLabel(APP_TITLE)
        t.setObjectName("title")
        t.setAlignment(Qt.AlignCenter)
        self.body.addWidget(t)
        v = QLabel(f"Version {VERSION} (64-bit)")
        v.setObjectName("subtitle")
        v.setAlignment(Qt.AlignCenter)
        self.body.addWidget(v)
        d = QLabel("Accelerates downloads by up to 32 connections with dynamic file segmentation, resumes broken "
                   "downloads, and catches downloads and videos from your browser.")
        d.setWordWrap(True)
        d.setAlignment(Qt.AlignCenter)
        self.body.addWidget(d)
        self.body.addWidget(separator())
        cr = QLabel("Built with Qt for Python (PySide6, LGPLv3) and Fluent UI System Icons (MIT).")
        cr.setObjectName("subtitle")
        cr.setWordWrap(True)
        cr.setAlignment(Qt.AlignCenter)
        self.body.addWidget(cr)
        self.body.addLayout(_button_row(_button("OK", True, self.accept)))
