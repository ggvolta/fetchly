"""Icons: Fluent UI SVG icons (tinted), the Fetchly logo, and per-file-type icons."""
import os
import sys
from pathlib import Path

from PySide6.QtCore import QByteArray, QFileInfo, QPointF, QRectF, QSize, Qt
from PySide6.QtGui import (QBrush, QColor, QFont, QIcon, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap,
                           QRadialGradient)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QFileIconProvider

from ..utils import category_for, ext_of
from . import theme

ASSETS = Path(__file__).resolve().parent / "assets" / "icons"
_SIZES = (16, 20, 24, 28, 32, 40, 48, 64)
_cache = {}


def _svg_bytes(name, variant):
    p = ASSETS / f"{name}_{variant}.svg"
    if not p.exists():
        p = ASSETS / f"{name}_regular.svg"
    return p.read_bytes() if p.exists() else b""


def svg(name, color=None, variant="filled"):
    """A Fluent icon tinted with `color` (defaults to the theme's text colour)."""
    color = color or theme.colors()["text"]
    key = ("svg", name, color, variant)
    if key in _cache:
        return _cache[key]
    data = _svg_bytes(name, variant)
    ic = QIcon()
    if data:
        data = data.replace(b"<svg ", f'<svg fill="{color}" '.encode(), 1)
        r = QSvgRenderer(QByteArray(data))
        for s in _SIZES:
            for dpr in (1, 2):
                pm = QPixmap(s * dpr, s * dpr)
                pm.fill(Qt.transparent)
                p = QPainter(pm)
                p.setRenderHint(QPainter.Antialiasing)
                r.render(p, QRectF(0, 0, s * dpr, s * dpr))
                p.end()
                pm.setDevicePixelRatio(dpr)
                ic.addPixmap(pm)
        # disabled state: faded
        faint = theme.colors()["faint"]
        dd = data.replace(f'fill="{color}"'.encode(), f'fill="{faint}"'.encode(), 1)
        rd = QSvgRenderer(QByteArray(dd))
        for s in _SIZES:
            pm = QPixmap(s * 2, s * 2)
            pm.fill(Qt.transparent)
            p = QPainter(pm)
            p.setRenderHint(QPainter.Antialiasing)
            rd.render(p, QRectF(0, 0, s * 2, s * 2))
            p.end()
            pm.setDevicePixelRatio(2)
            ic.addPixmap(pm, QIcon.Disabled)
    _cache[key] = ic
    return ic


ACTION_ICONS = {
    "add": "add_circle", "resume": "play_circle", "stop": "pause_circle", "stopall": "record_stop",
    "delete": "delete", "clean": "broom", "options": "settings", "scheduler": "calendar_clock",
    "qstart": "drawer_play", "qstop": "drawer_dismiss", "batch": "document_queue_add",
}


def action(name):
    col = QColor(theme.ACTION_COLORS[name])
    if theme.is_dark():
        col = col.lighter(165)
    return svg(ACTION_ICONS[name], col.name(), "filled")


CATEGORY_ICONS = {
    "all": "arrow_download", "General": "folder", "Compressed": "folder_zip", "Documents": "document",
    "Music": "music_note_2", "Programs": "apps", "Video": "video", "unfinished": "clock_arrow_download",
    "finished": "checkmark_circle", "queues": "text_bullet_list_square", "queue": "document_queue",
}


def category(name):
    return svg(CATEGORY_ICONS.get(name, "folder"), theme.CATEGORY_COLORS.get(name, "#64748b"), "filled")


def menu(name):
    """Small monochrome icon for menus."""
    return svg(name, theme.colors()["muted"], "regular")


# ----------------------------------------------------------------- logo
BRAND_INDIGO_TOP = "#30349A"
BRAND_INDIGO_BOTTOM = "#161845"
BRAND_AMBER_TOP = "#FFD36E"
BRAND_AMBER_BOTTOM = "#FF9A1F"
BRAND_AMBER = "#FFB33A"


def squircle_path(x, y, size, n=5.0, steps=240):
    """Superellipse tile (smoother than a rounded rectangle)."""
    import math
    path = QPainterPath()
    cx, cy, r = x + size / 2, y + size / 2, size / 2
    for i in range(steps + 1):
        t = 2 * math.pi * i / steps
        c, sn = math.cos(t), math.sin(t)
        px = cx + r * math.copysign(abs(c) ** (2 / n), c)
        py = cy + r * math.copysign(abs(sn) ** (2 / n), sn)
        if i == 0:
            path.moveTo(px, py)
        else:
            path.lineTo(px, py)
    path.closeSubpath()
    return path


def paint_mark(p, size, x=0.0, y=0.0, optical=None, color=None):
    """The Fetchly mark on its own: a lowercase f whose stem ends in a download arrow."""
    optical = optical or size
    u = size / 100.0
    small = optical <= 24
    w = (13.5 if small else 10.5) * u
    p.save()
    p.translate(x, y)
    p.setRenderHint(QPainter.Antialiasing)
    if color or small:
        brush = QBrush(QColor(color or BRAND_AMBER))
    else:
        g = QLinearGradient(0, 22 * u, 0, 76 * u)
        g.setColorAt(0, QColor(BRAND_AMBER_TOP))
        g.setColorAt(1, QColor(BRAND_AMBER_BOTTOM))
        brush = QBrush(g)
    sx = 47 * u
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(brush, w, Qt.SolidLine, Qt.FlatCap, Qt.RoundJoin))
    hook = QPainterPath(QPointF(sx, 70 * u))
    hook.lineTo(sx, 41 * u)
    hook.cubicTo(sx, 30.5 * u, sx + 6.5 * u, 25.5 * u, sx + 20 * u, 25.5 * u)
    p.drawPath(hook)
    p.drawLine(QPointF(sx - 12.5 * u, 45 * u), QPointF(sx + 12.5 * u, 45 * u))
    p.setPen(QPen(brush, w, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    arrow = QPainterPath(QPointF(sx - 14.5 * u, 59.5 * u))
    arrow.lineTo(sx, 74 * u)
    arrow.lineTo(sx + 14.5 * u, 59.5 * u)
    p.drawPath(arrow)
    p.restore()


def paint_logo(p, size, x=0.0, y=0.0, optical=None):
    """App icon: indigo squircle tile with the amber mark. `optical` = displayed size (picks the
    heavier small-size drawing at 24 px and below)."""
    optical = optical or size
    u = size / 100.0
    p.save()
    p.translate(x, y)
    p.setRenderHint(QPainter.Antialiasing)
    g = QLinearGradient(0, 0, 0, size)
    g.setColorAt(0, QColor(BRAND_INDIGO_TOP))
    g.setColorAt(1, QColor(BRAND_INDIGO_BOTTOM))
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(g))
    p.drawPath(squircle_path(2 * u, 2 * u, 96 * u))
    if optical >= 48:
        hl = QLinearGradient(0, 0, 0, size)
        hl.setColorAt(0, QColor(255, 255, 255, 70))
        hl.setColorAt(0.5, QColor(255, 255, 255, 0))
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QBrush(hl), max(1.0, size / 256)))
        p.drawPath(squircle_path(2.6 * u, 2.6 * u, 94.8 * u))
    p.restore()
    paint_mark(p, size, x, y, optical)


def logo_pixmap(size, dpr=2):
    pm = QPixmap(int(size * dpr), int(size * dpr))
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    paint_logo(p, size * dpr, optical=size)
    p.end()
    pm.setDevicePixelRatio(dpr)
    return pm


def app_icon():
    if "app" not in _cache:
        ic = QIcon()
        for s in (16, 20, 24, 32, 40, 48, 64, 128, 256):
            ic.addPixmap(logo_pixmap(s, 1))
        _cache["app"] = ic
    return _cache["app"]


def tray_icon(active=False):
    key = ("tray", active)
    if key not in _cache:
        ic = QIcon()
        for s in (16, 20, 24, 32, 48):
            pm = logo_pixmap(s, 1)
            if active:
                p = QPainter(pm)
                p.setRenderHint(QPainter.Antialiasing)
                p.setPen(QPen(QColor("white"), max(1.0, s / 16)))
                p.setBrush(QColor("#2ECC71"))
                r = s * 0.40
                p.drawEllipse(QRectF(s - r - 0.5, s - r - 0.5, r, r))
                p.end()
            ic.addPixmap(pm)
        _cache[key] = ic
    return _cache[key]


# ----------------------------------------------------------------- file-type icons
_TYPE_COLORS = {"Compressed": "#b45309", "Documents": "#2563eb", "Music": "#c026d3", "Programs": "#16a34a",
                "Video": "#dc2626", "General": "#64748b"}


def _drawn_file_icon(ext, s=32):
    cat = category_for("x." + ext) if ext else "General"
    col = QColor(_TYPE_COLORS.get(cat, "#64748b"))
    pm = QPixmap(s * 2, s * 2)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.scale(2, 2)
    u = s / 32.0
    body = QPainterPath()
    body.moveTo(7 * u, 3 * u)
    body.lineTo(20 * u, 3 * u)
    body.lineTo(26 * u, 9 * u)
    body.lineTo(26 * u, 29 * u)
    body.lineTo(7 * u, 29 * u)
    body.closeSubpath()
    p.setPen(QPen(QColor("#c4cbd6"), 1 * u))
    p.setBrush(QColor("#ffffff"))
    p.drawPath(body)
    fold = QPainterPath(QPointF(20 * u, 3 * u))
    fold.lineTo(20 * u, 9 * u)
    fold.lineTo(26 * u, 9 * u)
    p.setBrush(QColor("#e8ecf2"))
    p.drawPath(fold)
    p.setPen(Qt.NoPen)
    p.setBrush(col)
    p.drawRoundedRect(QRectF(3 * u, 16 * u, 20 * u, 10 * u), 2 * u, 2 * u)
    if ext:
        f = QFont()
        f.setBold(True)
        f.setPixelSize(int(6.4 * u) if len(ext) <= 3 else int(5.2 * u))
        p.setFont(f)
        p.setPen(QColor("white"))
        p.drawText(QRectF(3 * u, 16 * u, 20 * u, 10 * u), Qt.AlignCenter, ext.upper()[:4])
    p.end()
    pm.setDevicePixelRatio(2)
    return QIcon(pm)


class FileIcons:
    """Real Windows shell icons per file type (like Explorer/IDM); drawn icons elsewhere."""

    def __init__(self, cache_dir):
        self.cache = {}
        self.dir = os.path.join(cache_dir, "typeicons")
        self.provider = QFileIconProvider() if sys.platform == "win32" else None

    def for_item(self, filename, path=""):
        ext = ext_of(filename)
        if self.provider and path and ext in ("exe", "msi", "lnk", "ico", "appx") and os.path.isfile(path):
            key = ("path", path)
            if key not in self.cache:
                self.cache[key] = self.provider.icon(QFileInfo(path))
            return self.cache[key]
        key = ("ext", ext)
        if key in self.cache:
            return self.cache[key]
        ic = None
        if self.provider and ext and ext.isalnum():
            try:
                os.makedirs(self.dir, exist_ok=True)
                dummy = os.path.join(self.dir, "file." + ext)
                if not os.path.exists(dummy):
                    open(dummy, "wb").close()
                ic = self.provider.icon(QFileInfo(dummy))
                if ic.isNull():
                    ic = None
            except OSError:
                ic = None
        self.cache[key] = ic or _drawn_file_icon(ext)
        return self.cache[key]


def clear_cache():
    _cache.clear()
