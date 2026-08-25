"""The tray icon: a ring showing how full the session window is.

An icon that is only a logo wastes the one place kota is always visible. This
one takes the same three colours the meters use, so a glance at the corner
answers the question without opening anything.

Painted at several sizes rather than scaled from one, because a 2px ring scaled
down turns to grey mush.
"""

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QIcon, QPainter, QPen, QPixmap

from . import formatting

SIZES = (16, 20, 24, 32, 48, 64)

# How much of the circle the ring occupies, and how thick it is, as fractions
# of the icon. Kept in fractions so every size draws the same shape.
INSET = 0.13
THICKNESS = 0.17


def _ring(size, percent, colour, track, ink=None):
    """One pixmap: the track, the arc over it, and the number if it fits."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    width = max(2.0, size * THICKNESS)
    inset = size * INSET + width / 2.0
    box = QRectF(inset, inset, size - inset * 2, size - inset * 2)

    pen = QPen(QColor(track), width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    painter.drawArc(box, 0, 360 * 16)

    if percent > 0:
        pen.setColor(QColor(colour))
        painter.setPen(pen)
        # From twelve o'clock, clockwise, the way a gauge fills.
        span = int(-360 * 16 * min(100.0, percent) / 100.0)
        painter.drawArc(box, 90 * 16, span)

    # The number only where there are pixels to be legible in. Below that the
    # ring alone says it, and a smudge in the middle would say less.
    if ink is not None and size >= 32:
        font = QFont(painter.font())
        font.setPixelSize(int(size * 0.42))
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor(ink))
        painter.drawText(QRectF(0, 0, size, size),
                         int(Qt.AlignmentFlag.AlignCenter),
                         "%.0f" % min(99, percent))
    painter.end()
    return pixmap


def usage_icon(percent, palette, with_number=True):
    """The tray icon for a reading."""
    colour = palette.level(formatting.level(percent))
    ink = palette.text if with_number else None
    icon = QIcon()
    for size in SIZES:
        icon.addPixmap(_ring(size, percent, colour, palette.faint, ink))
    return icon


def unknown_icon(palette):
    """What the tray shows before the first reading lands, or after it fails."""
    icon = QIcon()
    for size in SIZES:
        icon.addPixmap(_ring(size, 0, palette.subtext, palette.faint, None))
    return icon


def app_icon(palette):
    """The window's own icon: the same ring, on a tile so it reads at 16px."""
    icon = QIcon()
    for size in (16, 32, 48, 64, 128, 256):
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(palette.accent))
        radius = size * 0.22
        painter.drawRoundedRect(QRectF(0, 0, size, size), radius, radius)

        width = max(2.0, size * 0.13)
        inset = size * 0.24 + width / 2.0
        box = QRectF(inset, inset, size - inset * 2, size - inset * 2)
        pen = QPen(QColor(255, 255, 255, 90), width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawArc(box, 0, 360 * 16)
        pen.setColor(QColor(255, 255, 255))
        painter.setPen(pen)
        painter.drawArc(box, 90 * 16, -252 * 16)
        painter.end()
        icon.addPixmap(pixmap)
    return icon
