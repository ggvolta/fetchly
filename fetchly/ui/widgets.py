"""Custom widgets and item delegates."""
from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QAction, QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QLineEdit, QSizePolicy, QStyle, QStyledItemDelegate,
                               QStyleOptionViewItem, QVBoxLayout, QWidget)

from . import icons, theme


class SegmentBar(QWidget):
    """Which parts of the file each connection has downloaded (IDM's connection map)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(16)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._done, self._active, self._indeterminate = [], [], False

    def sizeHint(self):
        return QSize(400, 16)

    def set_http(self, segments, size):
        if size and size > 0:
            segs = list(segments)
            self._done = [(s.start / size, s.pos / size) for s in segs if s.pos > s.start]
            self._active = [s.pos / size for s in segs if s.active]
            self._indeterminate = False
        else:
            self._done, self._active, self._indeterminate = [], [], True
        self.update()

    def set_blocks(self, done_indexes, total):
        self._done = [(i / total, (i + 1) / total) for i in done_indexes] if total else []
        self._active, self._indeterminate = [], not total
        self.update()

    def set_complete(self):
        self._done, self._active, self._indeterminate = [(0.0, 1.0)], [], False
        self.update()

    def paintEvent(self, _):
        c = theme.colors()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setPen(QPen(QColor(c["border"])))
        p.setBrush(QColor(c["track"]))
        p.drawRoundedRect(r, 4, 4)
        p.setClipRect(r.adjusted(1, 1, -1, -1))
        w = r.width()
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(c["progress"]))
        for a, b in self._done:
            p.drawRect(QRectF(r.left() + a * w, r.top(), max(1.0, (b - a) * w), r.height()))
        p.setBrush(QColor(c["progress"]).darker(160))
        for x in self._active:
            p.drawRect(QRectF(r.left() + x * w - 1, r.top(), 2, r.height()))
        p.setClipping(False)
        if self._indeterminate:
            p.setPen(QColor(c["muted"]))
            f = p.font()
            f.setPointSizeF(8)
            p.setFont(f)
            p.drawText(r, Qt.AlignCenter, "Size unknown")
        p.end()


ROLE_STATUS = Qt.UserRole + 1


class StatusDelegate(QStyledItemDelegate):
    """Status column: percentage + slim progress bar, or a coloured state label."""

    def paint(self, painter, option, index):
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        opt.text = ""
        style = opt.widget.style() if opt.widget else None
        if style:
            style.drawControl(QStyle.CE_ItemViewItem, opt, painter, opt.widget)
        data = index.data(ROLE_STATUS)
        if not data:
            return
        state, prog, text = data
        c = theme.colors()
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        r = option.rect.adjusted(10, 0, -10, 0)
        if state in ("downloading", "paused", "queued") and prog is not None:
            tw = 54
            painter.setPen(QColor(c["text"] if state == "downloading" else c["muted"]))
            painter.drawText(QRectF(r.left(), r.top(), tw, r.height()), Qt.AlignVCenter | Qt.AlignLeft, text)
            bar = QRectF(r.left() + tw + 4, r.center().y() - 3, max(10, r.width() - tw - 4), 6)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(c["track"]))
            painter.drawRoundedRect(bar, 3, 3)
            if prog > 0:
                fill = QRectF(bar.left(), bar.top(), max(6, bar.width() * prog), bar.height())
                col = {"downloading": c["progress"], "queued": c["accent"]}.get(state, c["paused"])
                painter.setBrush(QColor(col))
                painter.drawRoundedRect(fill, 3, 3)
        else:
            col = {"complete": c["success"], "error": c["danger"], "queued": c["warning"],
                   "downloading": c["accent"]}.get(state, c["muted"])
            ic = {"complete": "checkmark_circle", "error": "error_circle", "queued": "clock",
                  "downloading": "arrow_download"}.get(state)
            x = r.left()
            if ic:
                icons.svg(ic, col, "filled").paint(painter, int(x), int(r.center().y() - 8), 16, 16)
                x += 22
            painter.setPen(QColor(col if state != "paused" else c["muted"]))
            painter.drawText(QRectF(x, r.top(), r.right() - x, r.height()), Qt.AlignVCenter | Qt.AlignLeft, text)
        painter.restore()


ROLE_COUNT = Qt.UserRole + 2


class SidebarDelegate(QStyledItemDelegate):
    """Draws the item count as a small pill on the right of each category."""

    def sizeHint(self, option, index):
        s = super().sizeHint(option, index)
        return QSize(s.width(), 30)

    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        n = index.data(ROLE_COUNT)
        if n:  # leave room for the count pill
            room = option.rect.width() - option.decorationSize.width() - 52
            option.text = option.fontMetrics.elidedText(option.text, Qt.ElideRight, max(20, room))

    def paint(self, painter, option, index):
        super().paint(painter, option, index)
        n = index.data(ROLE_COUNT)
        if not n:
            return
        c = theme.colors()
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        f = QFont(option.font)
        f.setPointSizeF(max(7.0, f.pointSizeF() - 1.5))
        painter.setFont(f)
        txt = str(n)
        w = max(20, painter.fontMetrics().horizontalAdvance(txt) + 12)
        r = QRectF(option.rect.right() - w - 6, option.rect.center().y() - 9, w, 18)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(c["track"]))
        painter.drawRoundedRect(r, 9, 9)
        painter.setPen(QColor(c["muted"]))
        painter.drawText(r, Qt.AlignCenter, txt)
        painter.restore()


class SearchBox(QFrame):
    """Rounded search field with a magnifier icon."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("search")
        self.setFixedHeight(34)
        self.setMaximumWidth(320)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 0, 4, 0)
        lay.setSpacing(4)
        self.icon = QLabel()
        lay.addWidget(self.icon)
        self.edit = QLineEdit()
        self.edit.setPlaceholderText("Search downloads")
        self.edit.setClearButtonEnabled(True)
        self.edit.installEventFilter(self)
        lay.addWidget(self.edit, 1)
        self.textChanged = self.edit.textChanged
        self.refresh_icon()

    def refresh_icon(self):
        self.icon.setPixmap(icons.svg("search", theme.colors()["faint"], "regular").pixmap(16, 16))

    def eventFilter(self, obj, ev):
        from PySide6.QtCore import QEvent
        if ev.type() in (QEvent.FocusIn, QEvent.FocusOut):
            self.setProperty("focused", ev.type() == QEvent.FocusIn)
            self.style().unpolish(self)
            self.style().polish(self)
        return False

    def setFocus(self):
        self.edit.setFocus()

    def selectAll(self):
        self.edit.selectAll()


def header(title, subtitle="", pixmap=None, icon_name=None, icon_color=None):
    """Dialog header: icon, title, subtitle."""
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 6)
    lay.setSpacing(14)
    pic = QLabel()
    if pixmap is not None:
        pic.setPixmap(pixmap)
    elif icon_name:
        pic.setPixmap(icons.svg(icon_name, icon_color or theme.colors()["accent"]).pixmap(36, 36))
    lay.addWidget(pic, 0, Qt.AlignTop)
    col = QVBoxLayout()
    col.setSpacing(2)
    t = QLabel(title)
    t.setObjectName("title")
    col.addWidget(t)
    if subtitle:
        s = QLabel(subtitle)
        s.setObjectName("subtitle")
        s.setWordWrap(True)
        col.addWidget(s)
    lay.addLayout(col, 1)
    return w


def separator():
    f = QFrame()
    f.setObjectName("separator")
    f.setFrameShape(QFrame.NoFrame)
    return f
