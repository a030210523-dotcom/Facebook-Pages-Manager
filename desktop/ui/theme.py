"""Professional theme for Facebook Pages Manager — colors, stylesheet, hand-drawn icons.

Icons are drawn with QPainter at runtime (no external image files needed), so the
single-file .exe stays self-contained. Palette: Meta blue on deep-navy sidebar,
light content area, white cards.
"""
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QPen, QBrush, QPainterPath, QLinearGradient, QFont

BLUE = "#1877F2"
BLUE_DARK = "#1463CC"
NAVY = "#0C1B31"
NAVY_HOVER = "#16283F"
INK = "#0F1E33"
MUTED = "#64748B"
BORDER = "#DFE6F0"
BG = "#F1F4F9"

STYLESHEET = f"""
* {{ font-family: "Segoe UI", "Inter", sans-serif; color: {INK}; }}
QMainWindow, QDialog {{ background: {BG}; }}
QWidget#Sidebar {{ background: {NAVY}; }}
QLabel#BrandName {{ color: #FFFFFF; font-size: 15px; font-weight: 700; }}
QLabel#BrandSub {{ color: #8FA8C8; font-size: 11px; }}
QLabel#SidebarFoot {{ color: #7189AC; font-size: 11px; padding: 10px 14px; }}
QListWidget#Nav {{ background: {NAVY}; border: none; outline: none; padding: 8px 10px; }}
QListWidget#Nav::item {{ color: #C9D6EC; padding: 11px 12px; margin: 2px 0; border-radius: 9px; font-size: 13px; }}
QListWidget#Nav::item:hover {{ background: {NAVY_HOVER}; }}
QListWidget#Nav::item:selected {{ background: {BLUE}; color: #FFFFFF; font-weight: 600; }}
QLabel#PageTitle {{ font-size: 21px; font-weight: 700; color: {INK}; }}
QLabel#PageSub {{ font-size: 12.5px; color: {MUTED}; }}
QFrame#Card {{ background: #FFFFFF; border: 1px solid {BORDER}; border-radius: 14px; }}
QFrame#Welcome {{ background: {BLUE}; border-radius: 14px; border: none; }}
QLabel#WelcomeTitle {{ color: #FFFFFF; font-size: 17px; font-weight: 700; }}
QLabel#WelcomeSub {{ color: #CFE4FF; font-size: 12.5px; }}
QLabel#CardValue {{ font-size: 23px; font-weight: 800; color: {INK}; }}
QLabel#CardTitle {{ font-size: 11.5px; color: {MUTED}; font-weight: 600; }}
QLabel#MiniValue {{ font-size: 17px; font-weight: 800; color: {INK}; }}
QLabel#MiniTitle {{ font-size: 11px; color: {MUTED}; font-weight: 600; }}
QFrame#EmptyCard {{ background: #F8FAFD; border: 1.5px dashed #C3D2E6; border-radius: 12px; }}
QLabel#EmptyText {{ color: {MUTED}; font-size: 13px; }}
QLabel#SectionLabel {{ font-size: 13px; font-weight: 700; color: {INK}; }}
QPushButton {{ background: #FFFFFF; border: 1px solid #D3DCEA; border-radius: 9px;
               padding: 8px 15px; font-size: 13px; color: {INK}; }}
QPushButton:hover {{ border-color: {BLUE}; color: {BLUE}; }}
QPushButton:pressed {{ background: #EAF2FE; }}
QPushButton#Primary {{ background: {BLUE}; border: 1px solid {BLUE}; color: #FFFFFF; font-weight: 600; }}
QPushButton#Primary:hover {{ background: {BLUE_DARK}; color: #FFFFFF; }}
QPushButton#Primary:pressed {{ background: #0F56B4; }}
QPushButton#Danger {{ color: #DC2626; }}
QPushButton#Danger:hover {{ border-color: #DC2626; color: #DC2626; background: #FEF2F2; }}
QLineEdit, QComboBox {{ background: #FFFFFF; border: 1px solid #D3DCEA; border-radius: 9px;
                        padding: 8px 11px; font-size: 13px; }}
QLineEdit:focus, QComboBox:focus {{ border-color: {BLUE}; }}
QTableWidget {{ background: #FFFFFF; alternate-background-color: #F4F8FD; border: 1px solid {BORDER};
                border-radius: 12px; gridline-color: #E8EEF6; font-size: 12.5px;
                selection-background-color: #C9DFFC; selection-color: {INK}; outline: 0; }}
QTableWidget::item {{ padding: 7px 10px; border-bottom: 1px solid #EEF3F9; }}
QTableWidget::item:selected {{ background: #C9DFFC; color: {INK}; }}
QHeaderView {{ background: transparent; }}
QHeaderView::section {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #E6EFFC, stop:1 #CFE1F8);
                        color: #16324F; font-weight: 700; font-size: 12px;
                        padding: 10px; border: none; border-bottom: 2px solid {BLUE};
                        border-right: 1px solid #D8E5F6; }}
QTableCornerButton::section {{ background: #CFE1F8; border: none; border-bottom: 2px solid {BLUE}; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: #C4CFDE; border-radius: 5px; min-width: 30px; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QStatusBar {{ background: #FFFFFF; color: {MUTED}; border-top: 1px solid {BORDER}; font-size: 12px; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #C4CFDE; border-radius: 5px; min-height: 30px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QToolTip {{ background: {INK}; color: #FFFFFF; border: none; padding: 5px 8px; }}
"""

# ---------------- icons (drawn, 28x28 logical, 2x for sharpness) ----------------

def _canvas(size=28, scale=2):
    pm = QPixmap(size * scale, size * scale)
    pm.setDevicePixelRatio(scale)
    pm.fill(Qt.transparent)
    return pm, QPainter(pm)

def _pen(color, w=2.1):
    p = QPen(QColor(color), w)
    p.setCapStyle(Qt.RoundCap); p.setJoinStyle(Qt.RoundJoin)
    return p

def _g_grid(p, c):
    p.setBrush(QBrush(QColor(c))); p.setPen(Qt.NoPen)
    for x, y in [(5, 5), (15.5, 5), (5, 15.5), (15.5, 15.5)]:
        p.drawRoundedRect(QRectF(x, y, 8, 8), 2.2, 2.2)

def _g_person(p, c):
    p.setBrush(QBrush(QColor(c))); p.setPen(Qt.NoPen)
    p.drawEllipse(QRectF(9.5, 3.5, 9, 9))
    path = QPainterPath(); path.moveTo(4.5, 25)
    path.cubicTo(4.5, 16.5, 23.5, 16.5, 23.5, 25); path.closeSubpath(); p.drawPath(path)

def _g_flag(p, c):
    p.setPen(_pen(c, 2.4)); p.drawLine(QPointF(7, 3.5), QPointF(7, 24.5))
    p.setBrush(QBrush(QColor(c))); p.setPen(Qt.NoPen)
    path = QPainterPath(); path.moveTo(7, 4.5)
    path.cubicTo(12, 2.5, 16, 8, 23, 5.5); path.lineTo(23, 13)
    path.cubicTo(16, 15.5, 12, 10, 7, 12.5); path.closeSubpath(); p.drawPath(path)

def _g_pulse(p, c):
    p.setPen(_pen(c, 2.3))
    pts = [QPointF(3, 15), QPointF(9, 15), QPointF(12, 7.5), QPointF(16.5, 21), QPointF(19.5, 15), QPointF(25, 15)]
    for a, b in zip(pts, pts[1:]): p.drawLine(a, b)

def _g_money(p, c):
    p.setPen(_pen(c, 2.0)); p.setBrush(Qt.NoBrush); p.drawEllipse(QRectF(4.5, 4.5, 19, 19))
    f = QFont(); f.setBold(True); f.setPixelSize(15)
    p.setFont(f); p.setPen(QPen(QColor(c)))
    p.drawText(QRectF(0, 1.5, 28, 25), Qt.AlignCenter, "$")

def _g_sync(p, c):
    p.setPen(_pen(c, 2.2)); p.setBrush(Qt.NoBrush)
    p.drawArc(QRectF(5.5, 5.5, 17, 17), 35 * 16, 115 * 16)
    p.drawArc(QRectF(5.5, 5.5, 17, 17), 215 * 16, 115 * 16)
    p.setBrush(QBrush(QColor(c))); p.setPen(Qt.NoPen)
    t1 = QPainterPath(); t1.moveTo(22.6, 3.2); t1.lineTo(24.6, 9.6); t1.lineTo(17.9, 8.6); t1.closeSubpath(); p.drawPath(t1)
    t2 = QPainterPath(); t2.moveTo(5.4, 24.8); t2.lineTo(3.4, 18.4); t2.lineTo(10.1, 19.4); t2.closeSubpath(); p.drawPath(t2)

def _g_chart(p, c):
    p.setBrush(QBrush(QColor(c))); p.setPen(Qt.NoPen)
    for x, h in [(5.5, 8), (12, 13.5), (18.5, 18)]:
        p.drawRoundedRect(QRectF(x, 23 - h, 4.4, h), 1.4, 1.4)
    p.setPen(_pen(c, 2.0)); p.drawLine(QPointF(3.5, 24.5), QPointF(24.5, 24.5))

def _g_key(p, c):
    p.setPen(_pen(c, 2.1)); p.setBrush(Qt.NoBrush)
    p.drawEllipse(QRectF(4, 4, 12.5, 12.5))
    p.drawLine(QPointF(14.5, 14.5), QPointF(23.5, 23.5))
    p.drawLine(QPointF(19.5, 19.5), QPointF(23.5, 19.5))
    p.drawLine(QPointF(17, 22), QPointF(21, 22))

def _g_gear(p, c):
    import math
    p.setPen(_pen(c, 2.6))
    for i in range(8):
        a = math.radians(i * 45)
        p.drawLine(QPointF(14 + 7.6 * math.cos(a), 14 + 7.6 * math.sin(a)),
                   QPointF(14 + 11 * math.cos(a), 14 + 11 * math.sin(a)))
    p.setBrush(QBrush(QColor(c))); p.setPen(Qt.NoPen); p.drawEllipse(QRectF(7.6, 7.6, 12.8, 12.8))
    p.setCompositionMode(QPainter.CompositionMode_Clear)
    p.drawEllipse(QRectF(11.2, 11.2, 5.6, 5.6)); p.setCompositionMode(QPainter.CompositionMode_SourceOver)

def _g_info(p, c):
    p.setPen(_pen(c, 2.0)); p.setBrush(Qt.NoBrush); p.drawEllipse(QRectF(4.5, 4.5, 19, 19))
    p.setBrush(QBrush(QColor(c))); p.setPen(Qt.NoPen); p.drawEllipse(QRectF(12.4, 8, 3.2, 3.2))
    p.setPen(_pen(c, 2.6)); p.drawLine(QPointF(14, 13.4), QPointF(14, 20))

def _g_link(p, c):
    p.setPen(_pen(c, 2.0)); p.setBrush(Qt.NoBrush)
    p.drawEllipse(QRectF(3.5, 8, 12.5, 12.5)); p.drawEllipse(QRectF(12, 8, 12.5, 12.5))

def _g_plus(p, c):
    p.setPen(_pen(c, 2.6))
    p.drawLine(QPointF(14, 5.5), QPointF(14, 22.5)); p.drawLine(QPointF(5.5, 14), QPointF(22.5, 14))

def _g_pencil(p, c):
    p.setPen(_pen(c, 2.2))
    p.drawLine(QPointF(6, 22), QPointF(19.5, 8.5)); p.drawLine(QPointF(21.5, 6.5), QPointF(20, 5))
    p.drawLine(QPointF(20, 5), QPointF(23, 8)); p.drawLine(QPointF(23, 8), QPointF(21.5, 6.5))
    p.drawLine(QPointF(4.5, 23.5), QPointF(8.5, 20.5))

def _g_trash(p, c):
    p.setPen(_pen(c, 2.1))
    p.drawLine(QPointF(5, 7.5), QPointF(23, 7.5))
    p.drawLine(QPointF(10.5, 7.5), QPointF(10.5, 4.5)); p.drawLine(QPointF(17.5, 7.5), QPointF(17.5, 4.5))
    p.drawLine(QPointF(10.5, 4.5), QPointF(17.5, 4.5))
    p.drawRoundedRect(QRectF(7.5, 7.5, 13, 16), 1.6, 1.6)
    p.drawLine(QPointF(11.8, 11.5), QPointF(11.8, 19)); p.drawLine(QPointF(16.2, 11.5), QPointF(16.2, 19))

def _g_download(p, c):
    p.setPen(_pen(c, 2.3))
    p.drawLine(QPointF(14, 4), QPointF(14, 16.5))
    p.drawLine(QPointF(8, 11.5), QPointF(14, 17.5)); p.drawLine(QPointF(20, 11.5), QPointF(14, 17.5))
    p.drawLine(QPointF(5, 23), QPointF(23, 23))

_GLYPHS = {"grid": _g_grid, "person": _g_person, "flag": _g_flag, "pulse": _g_pulse,
           "money": _g_money, "sync": _g_sync, "chart": _g_chart, "key": _g_key,
           "gear": _g_gear, "info": _g_info, "link": _g_link, "plus": _g_plus,
           "pencil": _g_pencil, "trash": _g_trash, "download": _g_download}

def icon(kind, color="#A9C1E8"):
    """Small glyph icon for nav/buttons."""
    try:
        pm, p = _canvas()
        p.setRenderHint(QPainter.Antialiasing, True)
        _GLYPHS[kind](p, color)
        p.end()
        return QIcon(pm)
    except Exception:
        return QIcon()

def chip(kind, bg, size=46):
    """Round colored chip with a white glyph — used on dashboard cards."""
    try:
        scale = 2
        pm = QPixmap(size * scale, size * scale); pm.setDevicePixelRatio(scale); pm.fill(Qt.transparent)
        p = QPainter(pm); p.setRenderHint(QPainter.Antialiasing, True)
        p.setBrush(QBrush(QColor(bg))); p.setPen(Qt.NoPen); p.drawEllipse(QRectF(0, 0, size, size))
        inner, ip = _canvas(28)
        ip.setRenderHint(QPainter.Antialiasing, True); _GLYPHS[kind](ip, "#FFFFFF"); ip.end()
        p.drawPixmap(int((size - 28) / 2), int((size - 28) / 2), inner)
        p.end()
        return pm
    except Exception:
        return QPixmap()

def logo_pixmap(size=64):
    """App logo: blue rounded square with a white pages glyph + F."""
    try:
        scale = 2
        pm = QPixmap(size * scale, size * scale); pm.setDevicePixelRatio(scale); pm.fill(Qt.transparent)
        p = QPainter(pm); p.setRenderHint(QPainter.Antialiasing, True)
        grad = QLinearGradient(0, 0, size, size)
        grad.setColorAt(0, QColor("#2B8CFF")); grad.setColorAt(1, QColor(BLUE_DARK))
        p.setBrush(QBrush(grad)); p.setPen(Qt.NoPen)
        p.drawRoundedRect(QRectF(1, 1, size - 2, size - 2), size * 0.24, size * 0.24)
        f = QFont(); f.setBold(True); f.setPixelSize(int(size * 0.58))
        p.setFont(f); p.setPen(QPen(QColor("#FFFFFF")))
        p.drawText(QRectF(0, size * 0.08, size, size), Qt.AlignCenter, "f")
        p.end()
        return pm
    except Exception:
        return QPixmap()

def logo_icon():
    ic = QIcon()
    for s in (16, 24, 32, 48, 64, 128, 256):
        ic.addPixmap(logo_pixmap(s))
    return ic
