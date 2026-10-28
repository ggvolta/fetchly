"""Renders the README artwork into docs/art (light and dark versions):
banner, download button, the "why it's faster" diagram and framed screenshots.

    python tools/make_readme_art.py
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from PySide6.QtCore import QPointF, QRectF, Qt  # noqa: E402
from PySide6.QtGui import (QColor, QFont, QFontDatabase, QImage, QLinearGradient, QPainter,  # noqa: E402
                           QPainterPath, QPen)
from PySide6.QtWidgets import QApplication  # noqa: E402

from fetchly.ui.icons import paint_logo, paint_mark  # noqa: E402

OUT = os.path.join(ROOT, "docs", "art")
SHOTS = os.path.join(ROOT, "docs", "screenshots")
FAMILY = "Bricolage Grotesque"

THEMES = {
    "dark": {"bg_top": "#191B4D", "bg_bottom": "#101233", "ink": "#FFFFFF", "sub": "#B9BCEB", "track": "#2A2D6B",
             "fill": "#FFB33A", "fill_dim": "#C77B12", "caption": "#9EA2D8", "card": "#1B1D52", "line": "#2E3170"},
    "light": {"bg_top": "#F5F6FD", "bg_bottom": "#ECEEFB", "ink": "#161845", "sub": "#4B4F86", "track": "#DADCF4",
              "fill": "#F29A12", "fill_dim": "#F7C46E", "caption": "#5E6296", "card": "#FFFFFF", "line": "#D6D8F0"},
}


def font(px, weight=700, spacing=100):
    f = QFont(FAMILY)
    f.setPixelSize(int(px))
    f.setWeight(QFont.Weight(weight))
    f.setLetterSpacing(QFont.PercentageSpacing, spacing)
    f.setHintingPreference(QFont.PreferNoHinting)
    return f


def canvas(w, h, transparent=False):
    img = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
    img.fill(Qt.transparent if transparent else QColor("white"))
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.TextAntialiasing)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    return img, p


def rounded(p, rect, r, color):
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(color))
    p.drawRoundedRect(rect, r, r)


# ------------------------------------------------------------------ banner
LANES = [  # (start, progress) of each connection, as fractions of its lane — a frozen moment of a download
    (0.00, 0.92), (0.00, 0.74), (0.00, 0.81), (0.00, 0.58), (0.00, 0.66), (0.00, 0.43), (0.00, 0.71), (0.00, 0.37),
]


def banner(mode):
    c = THEMES[mode]
    w, h = 1760, 560
    img, p = canvas(w, h)
    g = QLinearGradient(0, 0, 0, h)
    g.setColorAt(0, QColor(c["bg_top"]))
    g.setColorAt(1, QColor(c["bg_bottom"]))
    clip = QPainterPath()
    clip.addRoundedRect(QRectF(0, 0, w, h), 28, 28)
    p.setClipPath(clip)
    p.fillRect(0, 0, w, h, g)

    # connection map: eight lanes running off the right edge, like the app's progress window.
    # Drawn on their own layer, then faded in from the left so they sit quietly behind nothing.
    x0, lane_h, gap = 1080, 24, 18
    top = (h - (len(LANES) * lane_h + (len(LANES) - 1) * gap)) / 2
    lane_w = w - x0 + 40
    layer = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
    layer.fill(Qt.transparent)
    lp = QPainter(layer)
    lp.setRenderHint(QPainter.Antialiasing)
    for i, (start, prog) in enumerate(LANES):
        y = top + i * (lane_h + gap)
        rounded(lp, QRectF(x0, y, lane_w, lane_h), lane_h / 2, c["track"])
        fw = lane_w * prog * 0.86
        fg = QLinearGradient(x0, 0, x0 + fw, 0)
        fg.setColorAt(0, QColor(c["fill_dim"]))
        fg.setColorAt(1, QColor(c["fill"]))
        lp.setBrush(fg)
        lp.drawRoundedRect(QRectF(x0, y, fw, lane_h), lane_h / 2, lane_h / 2)
        lp.setBrush(QColor(c["ink"]))
        lp.drawEllipse(QPointF(x0 + fw - lane_h / 2, y + lane_h / 2), 4.5, 4.5)
    lp.setCompositionMode(QPainter.CompositionMode_DestinationIn)
    mask = QLinearGradient(x0, 0, x0 + 300, 0)
    mask.setColorAt(0, QColor(0, 0, 0, 0))
    mask.setColorAt(1, QColor(0, 0, 0, 255))
    lp.fillRect(QRectF(0, 0, w, h), mask)
    lp.end()
    p.drawImage(0, 0, layer)

    # logo + wordmark
    ls = 148
    paint_logo(p, ls, 104, 150)
    p.setPen(QColor(c["ink"]))
    p.setFont(font(150, 800, 96))
    p.drawText(QRectF(282, 112, 800, 210), Qt.AlignLeft | Qt.AlignVCenter, "fetchly")
    p.setPen(QColor(c["sub"]))
    p.setFont(font(38, 500, 100))
    p.drawText(QRectF(110, 340, 900, 60), Qt.AlignLeft | Qt.AlignVCenter,
               "Faster downloads, up to 32 connections per file.")
    p.setFont(font(30, 500, 100))
    p.setPen(QColor(c["caption"]))
    p.drawText(QRectF(110, 398, 900, 50), Qt.AlignLeft | Qt.AlignVCenter,
               "Free and open source, for Windows 10 and 11.")
    p.end()
    img.save(os.path.join(OUT, f"banner-{mode}.png"))


# ------------------------------------------------------------------ download button
def windows_glyph(p, x, y, s, color):
    gap = s * 0.08
    q = (s - gap) / 2
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(color))
    for dx in (0, q + gap):
        for dy in (0, q + gap):
            p.drawRect(QRectF(x + dx, y + dy, q, q))


def button(mode):
    w, h = 660, 128
    img, p = canvas(w, h, transparent=True)
    g = QLinearGradient(0, 0, 0, h)
    g.setColorAt(0, QColor("#FFC453"))
    g.setColorAt(1, QColor("#FF9F24"))
    p.setPen(Qt.NoPen)
    p.setBrush(g)
    p.drawRoundedRect(QRectF(0, 0, w, h), 22, 22)
    p.setPen(QPen(QColor(255, 255, 255, 110), 2))
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(QRectF(1, 1, w - 2, h - 2), 21, 21)
    ink = "#161845"
    windows_glyph(p, 52, 42, 44, ink)
    p.setPen(QColor(ink))
    p.setFont(font(40, 700, 99))
    p.drawText(QRectF(120, 0, w - 140, h), Qt.AlignLeft | Qt.AlignVCenter, "Download for Windows")
    p.end()
    img.save(os.path.join(OUT, f"download-{mode}.png"))


# ------------------------------------------------------------------ diagram
def diagram(mode):
    """Same file, same server: one connection vs eight (numbers from tools/benchmark.py)."""
    c = THEMES[mode]
    w, h = 1760, 560
    img, p = canvas(w, h, transparent=True)
    rounded(p, QRectF(0, 0, w, h), 28, c["card"])
    p.setPen(QPen(QColor(c["line"]), 2))
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(QRectF(1, 1, w - 2, h - 2), 27, 27)

    p.setPen(QColor(c["ink"]))
    p.setFont(font(46, 700, 99))
    p.drawText(QRectF(72, 52, w - 144, 64), Qt.AlignLeft | Qt.AlignVCenter, "Same file, same server, 8× faster")
    p.setPen(QColor(c["caption"]))
    p.setFont(font(30, 500))
    p.drawText(QRectF(72, 112, w - 144, 48), Qt.AlignLeft | Qt.AlignVCenter,
               "64 MB from a server that allows 2 MB/s per connection")

    bx, bw, bh = 72, w - 144 - 230, 44

    def row(y, label, time_text, segments, highlight):
        p.setPen(QColor(c["sub"]))
        p.setFont(font(32, 700))
        p.drawText(QRectF(bx, y, bw, 44), Qt.AlignLeft | Qt.AlignVCenter, label)
        by = y + 60
        rounded(p, QRectF(bx, by, bw, bh), bh / 2, c["track"])
        p.save()
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(bx, by, bw, bh), bh / 2, bh / 2)
        p.setClipPath(clip)
        for a, b in segments:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(c["fill"]))
            p.drawRect(QRectF(bx + a * bw, by, (b - a) * bw, bh))
        for a, _ in segments[1:]:  # seams between connections
            p.setBrush(QColor(c["card"]))
            p.drawRect(QRectF(bx + a * bw - 2, by, 4, bh))
        p.restore()
        p.setPen(QColor(c["ink"] if highlight else c["caption"]))
        p.setFont(font(56 if highlight else 46, 800 if highlight else 500))
        p.drawText(QRectF(bx + bw + 24, by - 20, 206, bh + 40), Qt.AlignRight | Qt.AlignVCenter, time_text)

    # moment frozen 4.2 s in: the browser has 13% of the file, Fetchly's eight connections are done
    row(210, "Browser, 1 connection", "33.7 s", [(0.0, 0.125)], False)
    eight = [(i / 8, (i + 1) / 8) for i in range(8)]
    row(390, "Fetchly, 8 connections", "4.2 s", eight, True)
    p.end()
    img.save(os.path.join(OUT, f"speed-{mode}.png"))


# ------------------------------------------------------------------ framed screenshots
def framed(src, dst, title="Fetchly", radius=10, pad=48):
    """Wrap an app screenshot in a Windows 11 style window frame with a soft shadow."""
    dark = "dark" in src
    s = QImage(os.path.join(SHOTS, src))
    bar = 44
    w, h = s.width() + pad * 2, s.height() + bar + pad * 2
    img, p = canvas(w, h, transparent=True)
    win = QRectF(pad, pad, s.width(), s.height() + bar)
    for i in range(24, 0, -1):  # wide, faint shadow, offset downwards like a real window
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(12, 14, 46, 3 if not dark else 5))
        p.drawRoundedRect(win.adjusted(-i, -i * 0.6 + 10, i, i + 10), radius + i, radius + i)
    path = QPainterPath()
    path.addRoundedRect(win, radius, radius)
    p.setClipPath(path)
    p.fillRect(QRectF(win.left(), win.top(), win.width(), bar), QColor("#1F2228" if dark else "#F3F4F8"))
    paint_logo(p, 18, win.left() + 14, win.top() + 13, optical=18)
    p.setPen(QColor("#E7EAF0" if dark else "#1A2230"))
    f = QFont("Segoe UI")
    f.setPixelSize(13)
    p.setFont(f)
    p.drawText(QRectF(win.left() + 42, win.top(), 300, bar), Qt.AlignVCenter | Qt.AlignLeft, title)
    gl = QColor("#C9CDD6" if dark else "#3B4252")
    p.setPen(QPen(gl, 1.2))
    cx = win.right() - 23
    p.drawLine(QPointF(cx - 5, win.top() + 17), QPointF(cx + 5, win.top() + 27))   # close
    p.drawLine(QPointF(cx + 5, win.top() + 17), QPointF(cx - 5, win.top() + 27))
    cx -= 46
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(QRectF(cx - 5, win.top() + 17, 10, 10), 1.5, 1.5)          # maximize
    cx -= 46
    p.drawLine(QPointF(cx - 5, win.top() + 22), QPointF(cx + 5, win.top() + 22))   # minimize
    p.drawImage(QPointF(win.left(), win.top() + bar), s)
    p.setClipping(False)
    p.setPen(QPen(QColor(255, 255, 255, 28) if dark else QColor(0, 0, 0, 38), 1))
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(win.adjusted(0.5, 0.5, -0.5, -0.5), radius, radius)
    p.end()
    img.save(os.path.join(OUT, dst))


def main():
    QApplication([])
    for f in os.listdir(os.path.join(ROOT, "assets", "fonts")):
        if f.endswith(".ttf"):
            QFontDatabase.addApplicationFont(os.path.join(ROOT, "assets", "fonts", f))
    os.makedirs(OUT, exist_ok=True)
    for mode in ("dark", "light"):
        banner(mode)
        button(mode)
        diagram(mode)
    titles = {"main": "Fetchly", "progress": "ubuntu-26.04-desktop-amd64.iso", "download": "Download File Info"}
    for src in sorted(f for f in os.listdir(SHOTS) if f.endswith(".png")):
        framed(src, "framed-" + src, titles[src.split("-")[0]])
    print("README art written to docs/art")


if __name__ == "__main__":
    main()
