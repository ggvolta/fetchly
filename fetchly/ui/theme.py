"""Application theme: light/dark palettes, Qt style sheet, Windows title-bar integration."""
import sys

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QGuiApplication, QPalette

LIGHT = {
    "window": "#f3f5f9", "surface": "#ffffff", "surface2": "#f7f9fc", "sidebar": "#f7f9fc", "border": "#e1e6ee",
    "border_strong": "#cfd6e1", "text": "#1a2230", "muted": "#677285", "faint": "#9aa3b2",
    "accent": "#3D42C9", "accent_hover": "#3237AE", "accent_press": "#2A2E93", "accent_text": "#ffffff",
    "accent_soft": "#ECEDFB", "selection": "#E3E4FA", "hover": "#F1F2FB", "track": "#e6ebf2",
    "danger": "#dc2626", "success": "#16a34a", "warning": "#d97706", "paused": "#94a3b8", "progress": "#F29A12",
    "tooltip_bg": "#1f2937", "tooltip_text": "#f9fafb",
}
DARK = {
    "window": "#1b1e23", "surface": "#22262c", "surface2": "#272c33", "sidebar": "#1f2328", "border": "#323842",
    "border_strong": "#424a56", "text": "#e7eaf0", "muted": "#9aa4b3", "faint": "#6b7482",
    "accent": "#6A70F2", "accent_hover": "#8086F7", "accent_press": "#575DE0", "accent_text": "#ffffff",
    "accent_soft": "#262955", "selection": "#2C2F63", "hover": "#2a3038", "track": "#343b45",
    "danger": "#f87171", "success": "#4ade80", "warning": "#fbbf24", "paused": "#7c8696", "progress": "#FFB33A",
    "tooltip_bg": "#e7eaf0", "tooltip_text": "#111827",
}

# toolbar / category icon colours
ACTION_COLORS = {
    # indigo = start something, amber = pause something, slate = manage
    "add": "#3D42C9", "resume": "#3D42C9", "qstart": "#3D42C9", "batch": "#3D42C9",
    "stop": "#D9820F", "stopall": "#D9820F", "qstop": "#D9820F",
    "delete": "#5B6478", "clean": "#5B6478", "options": "#5B6478", "scheduler": "#5B6478",
}
CATEGORY_COLORS = {
    "all": "#3D42C9", "General": "#64748b", "Compressed": "#b45309", "Documents": "#2563eb", "Music": "#c026d3",
    "Programs": "#16a34a", "Video": "#dc2626", "unfinished": "#d97706", "finished": "#16a34a", "queues": "#475569",
    "queue": "#7c3aed",
}

_current = dict(LIGHT)
_is_dark = False


def colors():
    return _current


def is_dark():
    return _is_dark


def system_prefers_dark():
    try:
        return QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark
    except AttributeError:
        return False


def _font():
    fams = set(QFontDatabase.families())
    for fam in ("Segoe UI Variable Text", "Segoe UI", "Inter", "Ubuntu", "Noto Sans", "DejaVu Sans"):
        if fam in fams:
            f = QFont(fam)
            f.setPointSizeF(9.5 if sys.platform == "win32" else 9.5)
            f.setHintingPreference(QFont.PreferNoHinting if fam.startswith("Segoe UI Variable") else
                                   QFont.PreferDefaultHinting)
            return f
    f = QFont()
    f.setPointSizeF(9.5)
    return f


QSS = """
* {{ outline: 0; }}
QMainWindow, QDialog {{ background: {window}; }}
QWidget {{ color: {text}; }}
QLabel#muted, QLabel[muted="true"] {{ color: {muted}; }}
QLabel#title {{ font-size: 13pt; font-weight: 600; }}
QLabel#subtitle {{ color: {muted}; }}
QLabel#sectionTitle {{ font-weight: 600; color: {text}; padding-top: 4px; }}
QLabel#link {{ color: {accent}; }}
QFrame#card {{ background: {surface}; border: 1px solid {border}; border-radius: 8px; }}
QFrame#separator {{ background: {border}; max-height: 1px; min-height: 1px; border: none; }}
QFrame#headerBar {{ background: {surface}; border-bottom: 1px solid {border}; }}

/* ---------- toolbar ---------- */
QToolBar#mainToolbar {{ background: {surface}; border: none; border-bottom: 1px solid {border};
    padding: 6px 8px; spacing: 2px; }}
QToolBar#mainToolbar::separator {{ background: {border}; width: 1px; margin: 8px 6px; }}
QToolBar#mainToolbar QToolButton {{ background: transparent; border: 1px solid transparent; border-radius: 8px;
    padding: 5px 6px 4px 6px; min-width: 64px; color: {text}; font-size: 8.5pt; }}
QToolBar#mainToolbar QToolButton:hover {{ background: {hover}; border-color: {border}; }}
QToolBar#mainToolbar QToolButton:pressed {{ background: {selection}; }}
QToolBar#mainToolbar QToolButton:disabled {{ color: {faint}; }}


/* ---------- sidebar ---------- */
QTreeWidget#sidebar {{ background: {sidebar}; border: none; border-right: 1px solid {border}; padding: 8px 6px; }}
QTreeWidget#sidebar::item {{ height: 30px; border-radius: 6px; padding-left: 2px; }}
QTreeWidget#sidebar::item:hover {{ background: {hover}; }}
QTreeWidget#sidebar::item:selected {{ background: {selection}; color: {text}; }}
QTreeWidget#sidebar::branch, QTreeWidget#sidebar::branch:selected {{ background: {sidebar}; border: none;
    image: none; }}

/* ---------- download list ---------- */
QTableView#downloads {{ background: {surface}; alternate-background-color: {surface}; border: none;
    selection-background-color: {selection}; selection-color: {text}; gridline-color: {border}; }}
QTableView#downloads::item {{ padding-left: 6px; border-bottom: 1px solid {surface2}; }}
QTableView#downloads::item:hover {{ background: {hover}; }}
QTableView#downloads::item:selected {{ background: {selection}; color: {text}; }}
QHeaderView {{ background: {surface}; border: none; }}
QHeaderView::section {{ background: {surface}; color: {muted}; border: none; border-bottom: 1px solid {border};
    border-right: 1px solid {surface2}; padding: 7px 8px; font-weight: 600; font-size: 8.5pt; }}
QHeaderView::section:hover {{ background: {surface2}; color: {text}; }}
QTableCornerButton::section {{ background: {surface}; border: none; }}

/* ---------- inputs ---------- */
QLineEdit, QComboBox, QSpinBox, QTimeEdit, QPlainTextEdit, QTextEdit {{ background: {surface};
    border: 1px solid {border_strong}; border-radius: 6px; padding: 5px 8px;
    selection-background-color: {accent}; selection-color: {accent_text}; }}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QTimeEdit:focus, QPlainTextEdit:focus {{ border-color: {accent}; }}
QLineEdit:read-only {{ background: {surface2}; color: {muted}; }}
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled, QTimeEdit:disabled {{ color: {faint};
    background: {surface2}; border-color: {border}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{ background: {surface}; border: 1px solid {border}; border-radius: 6px;
    selection-background-color: {selection}; selection-color: {text}; padding: 4px; }}
QSpinBox::up-button, QSpinBox::down-button, QTimeEdit::up-button, QTimeEdit::down-button {{ width: 18px;
    border: none; }}

/* ---------- buttons ---------- */
QPushButton {{ background: {surface}; border: 1px solid {border_strong}; border-radius: 6px; padding: 6px 16px;
    min-height: 18px; color: {text}; }}
QPushButton:hover {{ background: {hover}; }}
QPushButton:pressed {{ background: {selection}; }}
QPushButton:disabled {{ color: {faint}; border-color: {border}; }}
QPushButton#primary, QPushButton:default {{ background: {accent}; border-color: {accent}; color: {accent_text};
    font-weight: 600; }}
QPushButton#primary:hover, QPushButton:default:hover {{ background: {accent_hover}; border-color: {accent_hover}; }}
QPushButton#primary:pressed, QPushButton:default:pressed {{ background: {accent_press}; }}
QPushButton#danger {{ color: {danger}; }}
QPushButton#flat {{ background: transparent; border: none; color: {accent}; padding: 4px 6px; }}
QPushButton#flat:hover {{ text-decoration: underline; }}
QToolButton {{ border-radius: 6px; padding: 4px; }}
QToolButton:hover {{ background: {hover}; }}

/* ---------- tabs ---------- */
QTabWidget::pane {{ background: {surface}; border: 1px solid {border}; border-radius: 8px; top: -1px; }}
QTabBar::tab {{ background: transparent; color: {muted}; padding: 7px 14px; margin-right: 2px;
    border: 1px solid transparent; border-top-left-radius: 6px; border-top-right-radius: 6px; }}
QTabBar::tab:selected {{ background: {surface}; color: {text}; border-color: {border}; border-bottom-color: {surface};
    font-weight: 600; }}
QTabBar::tab:hover:!selected {{ color: {text}; }}

/* ---------- misc ---------- */
QGroupBox {{ background: {surface}; border: 1px solid {border}; border-radius: 8px; margin-top: 14px;
    padding: 12px 10px 10px 10px; font-weight: 600; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; color: {text}; }}
QProgressBar {{ background: {track}; border: none; border-radius: 4px; max-height: 8px; min-height: 8px; }}
QProgressBar::chunk {{ background: {progress}; border-radius: 4px; }}
QMenuBar {{ background: {surface}; border: none; padding: 2px 4px; }}
QMenuBar::item {{ padding: 5px 10px; border-radius: 5px; background: transparent; }}
QMenuBar::item:selected {{ background: {hover}; }}
QMenu {{ background: {surface}; border: 1px solid {border}; border-radius: 8px; padding: 5px; }}
QMenu::item {{ padding: 6px 28px 6px 10px; border-radius: 5px; }}
QMenu::item:selected {{ background: {selection}; color: {text}; }}
QMenu::item:disabled {{ color: {faint}; }}
QMenu::separator {{ height: 1px; background: {border}; margin: 4px 6px; }}
QMenu::icon {{ padding-left: 8px; }}
QStatusBar {{ background: {surface}; border-top: 1px solid {border}; color: {muted}; }}
QStatusBar::item {{ border: none; }}
QStatusBar QLabel {{ color: {muted}; padding: 0 6px; }}
QToolTip {{ background: {tooltip_bg}; color: {tooltip_text}; border: none; border-radius: 4px; padding: 5px 8px; }}
QListWidget, QTableWidget {{ background: {surface}; border: 1px solid {border}; border-radius: 6px;
    alternate-background-color: {surface2}; selection-background-color: {selection}; selection-color: {text}; }}
QListWidget::item {{ padding: 5px 6px; border-radius: 4px; }}
QScrollBar:vertical {{ background: transparent; width: 11px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {border_strong}; border-radius: 3px; min-height: 30px; margin: 0 2px; }}
QScrollBar::handle:vertical:hover {{ background: {faint}; }}
QScrollBar:horizontal {{ background: transparent; height: 11px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {border_strong}; border-radius: 3px; min-width: 30px; margin: 2px 0; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QSplitter::handle {{ background: {border}; }}
QCheckBox, QRadioButton {{ spacing: 8px; }}
QCheckBox::indicator, QAbstractItemView::indicator {{ width: 15px; height: 15px; border: 1px solid {border_strong};
    border-radius: 4px; background: {surface}; }}
QCheckBox::indicator:hover, QAbstractItemView::indicator:hover {{ border-color: {accent}; }}
QCheckBox::indicator:checked, QAbstractItemView::indicator:checked {{ background: {accent}; border-color: {accent};
    image: url({img_check}); }}
QCheckBox::indicator:disabled {{ background: {surface2}; border-color: {border}; }}
QRadioButton::indicator {{ width: 15px; height: 15px; border: 1px solid {border_strong}; border-radius: 8px;
    background: {surface}; }}
QRadioButton::indicator:hover {{ border-color: {accent}; }}
QRadioButton::indicator:checked {{ border: 5px solid {accent}; background: {accent_text}; width: 7px; height: 7px; }}
QComboBox::down-arrow {{ image: url({img_down}); width: 10px; height: 10px; }}
QSpinBox::up-arrow, QTimeEdit::up-arrow {{ image: url({img_up}); width: 8px; height: 8px; }}
QSpinBox::down-arrow, QTimeEdit::down-arrow {{ image: url({img_down}); width: 8px; height: 8px; }}
QFrame#search {{ background: {surface2}; border: 1px solid {border}; border-radius: 16px; }}
QFrame#search[focused="true"] {{ border-color: {accent}; background: {surface}; }}
QFrame#search QLineEdit {{ background: transparent; border: none; padding: 6px 4px; min-width: 220px; }}
"""


def _write_images(c):
    """Small SVG glyphs referenced by the style sheet (check mark, chevrons)."""
    import os
    from ..config import app_data_dir
    d = os.path.join(app_data_dir(), "ui")
    os.makedirs(d, exist_ok=True)
    glyphs = {
        "check": ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><path d="M3.5 8.5l3 3 6-7" '
                  f'fill="none" stroke="{c["accent_text"]}" stroke-width="2" stroke-linecap="round" '
                  'stroke-linejoin="round"/></svg>'),
        "down": ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><path d="M3.5 6l4.5 4.5L12.5 6" '
                 f'fill="none" stroke="{c["muted"]}" stroke-width="1.8" stroke-linecap="round" '
                 'stroke-linejoin="round"/></svg>'),
        "up": ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><path d="M3.5 10l4.5-4.5L12.5 10" '
               f'fill="none" stroke="{c["muted"]}" stroke-width="1.8" stroke-linecap="round" '
               'stroke-linejoin="round"/></svg>'),
    }
    tag = "dark" if _is_dark else "light"
    out = {}
    for name, svg in glyphs.items():
        path = os.path.join(d, f"{name}_{tag}.svg")
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(svg)
        except OSError:
            pass
        out["img_" + name] = path.replace("\\", "/")
    return out


def apply(app, mode="system"):
    """mode: 'system', 'light' or 'dark'."""
    global _current, _is_dark
    _is_dark = system_prefers_dark() if mode == "system" else mode == "dark"
    _current = dict(DARK if _is_dark else LIGHT)
    c = _current
    app.setStyle("Fusion")
    font = _font()
    app.setFont(font)
    # Windows assigns some widget classes their own (smaller) fonts; make everything consistent
    for cls in ("QAbstractItemView", "QTableView", "QTreeView", "QListView", "QHeaderView", "QMenu", "QMenuBar",
                "QStatusBar", "QToolButton", "QLabel", "QPushButton", "QLineEdit", "QComboBox", "QTabBar",
                "QCheckBox", "QRadioButton", "QGroupBox", "QToolTip"):
        app.setFont(font, cls)
    pal = QPalette()
    roles = {
        QPalette.Window: c["window"], QPalette.WindowText: c["text"], QPalette.Base: c["surface"],
        QPalette.AlternateBase: c["surface2"], QPalette.Text: c["text"], QPalette.Button: c["surface"],
        QPalette.ButtonText: c["text"], QPalette.Highlight: c["accent"], QPalette.HighlightedText: c["accent_text"],
        QPalette.ToolTipBase: c["tooltip_bg"], QPalette.ToolTipText: c["tooltip_text"],
        QPalette.PlaceholderText: c["faint"], QPalette.Link: c["accent"], QPalette.Mid: c["border"],
        QPalette.Midlight: c["surface2"], QPalette.Dark: c["border_strong"], QPalette.Light: c["surface"],
    }
    for role, col in roles.items():
        pal.setColor(role, QColor(col))
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        pal.setColor(QPalette.Disabled, role, QColor(c["faint"]))
    app.setPalette(pal)
    app.setStyleSheet(QSS.format(**c, **_write_images(c)))
    for w in app.topLevelWidgets():
        set_title_bar(w)


def set_title_bar(widget):
    """Dark/light native title bar on Windows 10/11."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        hwnd = int(widget.winId())
        val = ctypes.c_int(1 if _is_dark else 0)
        for attr in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE (new / pre-20H1)
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(val), ctypes.sizeof(val)) == 0:
                break
    except (OSError, AttributeError, ValueError):
        pass


class TitleBarFilter(QObject):
    """Applies the title-bar colour to every window as it is shown."""

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Show and getattr(obj, "isWindow", None) and obj.isWindow():
            set_title_bar(obj)
        return False
