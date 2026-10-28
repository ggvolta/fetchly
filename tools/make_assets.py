"""Renders every icon/bitmap from the single logo definition in fetchly/ui/icons.py:
assets/fetchly.ico, assets/fetchly.png, extension/icons/*.png and the installer artwork.

    python tools/make_assets.py
"""
import io
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from PIL import Image  # noqa: E402
from PySide6.QtCore import QBuffer, QIODevice, QRectF, Qt  # noqa: E402
from PySide6.QtGui import QColor, QFont, QImage, QLinearGradient, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from fetchly.ui.icons import paint_logo  # noqa: E402


def to_pil(img):
    buf = QBuffer()
    buf.open(QIODevice.WriteOnly)
    img.save(buf, "PNG")
    return Image.open(io.BytesIO(bytes(buf.data()))).convert("RGBA")


def logo(size):
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    paint_logo(p, size)
    p.end()
    return to_pil(img)


def _brand_font(px, weight):
    f = QFont("Bricolage Grotesque")
    f.setPixelSize(px)
    f.setWeight(QFont.Weight(weight))
    return f


def banner(w, h, with_text):
    """Installer side panel (164x314): indigo, logo, wordmark, and the connection lanes."""
    img = QImage(w, h, QImage.Format_RGB32)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    g = QLinearGradient(0, 0, 0, h)
    g.setColorAt(0, QColor("#1D2058"))
    g.setColorAt(1, QColor("#101233"))
    p.fillRect(0, 0, w, h, g)
    # lanes along the bottom
    for i, prog in enumerate((0.82, 0.55, 0.7, 0.4)):
        y = h - 92 + i * 17
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#2A2D6B"))
        p.drawRoundedRect(QRectF(22, y, w - 22, 9), 4.5, 4.5)
        p.setBrush(QColor("#FFB33A"))
        p.drawRoundedRect(QRectF(22, y, (w - 22) * prog, 9), 4.5, 4.5)
    if with_text:
        s = 64
        paint_logo(p, s, 22, 42)
        p.setPen(QColor("white"))
        p.setFont(_brand_font(34, 800))
        p.drawText(QRectF(22, 118, w - 30, 44), Qt.AlignLeft | Qt.AlignVCenter, "fetchly")
        p.setPen(QColor("#B9BCEB"))
        p.setFont(_brand_font(12, 500))
        p.drawText(QRectF(22, 160, w - 30, 64), Qt.AlignLeft | Qt.TextWordWrap, "Faster, resumable downloads for Windows")
    p.end()
    return to_pil(img).convert("RGB")


def header_bmp(w, h):
    img = QImage(w, h, QImage.Format_RGB32)
    img.fill(QColor("white"))
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    s = h - 14
    paint_logo(p, s, w - s - 8, 7)
    p.end()
    return to_pil(img).convert("RGB")


def main():
    QApplication([])
    from PySide6.QtGui import QFontDatabase
    fdir = os.path.join(ROOT, "assets", "fonts")
    for f in os.listdir(fdir):
        if f.endswith(".ttf"):
            QFontDatabase.addApplicationFont(os.path.join(fdir, f))
    os.makedirs(os.path.join(ROOT, "assets"), exist_ok=True)
    big = logo(256)
    big.save(os.path.join(ROOT, "assets", "fetchly.png"))
    sizes = [16, 20, 24, 32, 40, 48, 64, 128, 256]
    frames = [logo(s) for s in sizes]
    frames[-1].save(os.path.join(ROOT, "assets", "fetchly.ico"), format="ICO", sizes=[(s, s) for s in sizes],
                    append_images=frames[:-1])
    for s in (16, 32, 48, 128):
        logo(s).save(os.path.join(ROOT, "extension", "icons", f"icon{s}.png"))
    banner(164, 314, True).save(os.path.join(ROOT, "packaging", "wizard.bmp"))
    header_bmp(150, 57).save(os.path.join(ROOT, "packaging", "header.bmp"))
    print("assets written")


if __name__ == "__main__":
    main()
