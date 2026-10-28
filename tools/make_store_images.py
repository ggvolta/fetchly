"""Builds the Chrome Web Store / Edge Add-ons images in store/images from docs/screenshots.
    python tools/make_store_images.py
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from PySide6.QtCore import QRectF, Qt  # noqa: E402
from PySide6.QtGui import QColor, QFont, QImage, QLinearGradient, QPainter, QPainterPath  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from fetchly.ui.icons import paint_logo  # noqa: E402

SHOTS = os.path.join(ROOT, "docs", "screenshots")
OUT = os.path.join(ROOT, "store", "images")


def bg(p, w, h):
    g = QLinearGradient(0, 0, w, h)
    g.setColorAt(0, QColor("#1D2058"))
    g.setColorAt(1, QColor("#101233"))
    p.fillRect(0, 0, w, h, g)


def font(px, bold=False):
    f = QFont("Bricolage Grotesque")
    f.setPixelSize(px)
    f.setBold(bold)
    return f


def slide(name, title, subtitle, shot, out):
    w, h = 1280, 800
    img = QImage(w, h, QImage.Format_RGB32)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    bg(p, w, h)
    paint_logo(p, 44, 60, 46)
    p.setPen(QColor("white"))
    p.setFont(font(26, True))
    p.drawText(QRectF(116, 50, 400, 40), Qt.AlignVCenter, "fetchly")
    p.setFont(font(44, True))
    p.drawText(QRectF(60, 118, w - 120, 60), Qt.AlignLeft | Qt.AlignVCenter, title)
    p.setPen(QColor(255, 255, 255, 215))
    p.setFont(font(22))
    p.drawText(QRectF(60, 180, w - 120, 40), Qt.AlignLeft | Qt.AlignVCenter, subtitle)
    s = QImage(os.path.join(SHOTS, shot))
    box = QRectF(60, 250, w - 120, h - 290)
    sc = min(box.width() / s.width(), box.height() / s.height(), 1.0)
    sw, sh = s.width() * sc, s.height() * sc
    r = QRectF(box.left() + (box.width() - sw) / 2, box.top(), sw, sh)
    for i in range(14, 0, -2):  # soft shadow
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 7))
        p.drawRoundedRect(r.adjusted(-i, -i + 6, i, i + 6), 12 + i, 12 + i)
    path = QPainterPath()
    path.addRoundedRect(r, 10, 10)
    p.setClipPath(path)
    p.drawImage(r, s)
    p.end()
    img.save(os.path.join(OUT, out))


def tile(w, h, out, tagline=True):
    img = QImage(w, h, QImage.Format_RGB32)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    bg(p, w, h)
    ls = int(h * 0.36)
    paint_logo(p, ls, (w - ls) / 2, h * 0.14)
    p.setPen(QColor("white"))
    p.setFont(font(int(h * 0.13), True))
    p.drawText(QRectF(0, h * 0.14 + ls + h * 0.04, w, h * 0.16), Qt.AlignCenter, "fetchly")
    if tagline:
        p.setPen(QColor(255, 255, 255, 215))
        p.setFont(font(int(h * 0.065)))
        p.drawText(QRectF(0, h * 0.14 + ls + h * 0.21, w, h * 0.1), Qt.AlignCenter,
                   "Faster, resumable downloads")
    p.end()
    img.save(os.path.join(OUT, out))


def main():
    QApplication([])
    from PySide6.QtGui import QFontDatabase
    for f in os.listdir(os.path.join(ROOT, "assets", "fonts")):
        if f.endswith(".ttf"):
            QFontDatabase.addApplicationFont(os.path.join(ROOT, "assets", "fonts", f))
    os.makedirs(OUT, exist_ok=True)
    slide("1", "Download up to 32× faster", "Every file is split across many connections that all stay busy.",
          "main-light.png", "1-main.png")
    slide("2", "Catches downloads from your browser", "Pick a folder and start — sign-in-protected downloads work too.",
          "download-info-light.png", "2-catch.png")
    slide("3", "Pause, resume, never start over", "See every connection at work, limit speed, open when done.",
          "progress-light.png", "3-progress.png")
    slide("4", "Light and dark themes", "Follows your Windows setting automatically.", "main-dark.png", "4-dark.png")
    tile(440, 280, "promo-small-440x280.png")
    tile(1400, 560, "promo-marquee-1400x560.png")
    import shutil
    shutil.copy(os.path.join(ROOT, "extension", "icons", "icon128.png"), os.path.join(OUT, "icon-128.png"))
    print("store images written")


if __name__ == "__main__":
    main()
