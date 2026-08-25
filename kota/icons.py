"""Button icons, painted rather than taken from a font.

A gear or a refresh arrow out of the system font is a gamble: one machine
renders it as a full-colour emoji, the next has no glyph and leaves a box.
Painting them also lets them take their colour from the palette.
"""

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

SIZES = (16, 20, 24, 32, 40)


def _draw(size, colour, shape):
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    shape(painter, size, QColor(colour))
    painter.end()
    return pixmap


def _icon(colour, shape):
    icon = QIcon()
    for size in SIZES:
        icon.addPixmap(_draw(size, colour, shape))
    return icon


def _refresh(painter, size, ink):
    """An open circle with an arrowhead on the end of it."""
    unit = size / 24.0
    pen = QPen(ink, 2.0 * unit)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    box = QRectF(5.5 * unit, 5.5 * unit, 13 * unit, 13 * unit)
    # Open at the top right, which is where the arrowhead goes.
    painter.drawArc(box, 60 * 16, 300 * 16)

    head = QPainterPath()
    tip = QPointF(12 * unit + 6.5 * unit * 0.5, 12 * unit - 6.5 * unit * 0.866)
    head.moveTo(tip.x() - 1.0 * unit, tip.y() - 3.4 * unit)
    head.lineTo(tip.x() + 3.6 * unit, tip.y() + 0.2 * unit)
    head.lineTo(tip.x() - 1.6 * unit, tip.y() + 2.2 * unit)
    head.closeSubpath()
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(ink)
    painter.drawPath(head)


def _gear(painter, size, ink):
    """A ring with eight teeth and a hole, built from one path.

    Drawn as a single path with an even-odd fill so the hole is a hole rather
    than a circle painted in the background colour, which would be wrong the
    moment the thing under it is not the background.
    """
    unit = size / 24.0
    centre = QPointF(12 * unit, 12 * unit)
    path = QPainterPath()
    path.addEllipse(centre, 7.0 * unit, 7.0 * unit)
    for index in range(8):
        tooth = QPainterPath()
        tooth.addRoundedRect(
            QRectF(-1.7 * unit, -10.2 * unit, 3.4 * unit, 4.6 * unit),
            1.1 * unit, 1.1 * unit)
        painter.save()
        painter.translate(centre)
        painter.rotate(index * 45)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(ink)
        painter.drawPath(tooth)
        painter.restore()
    hole = QPainterPath()
    hole.addEllipse(centre, 2.9 * unit, 2.9 * unit)
    path = path.subtracted(hole)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(ink)
    painter.drawPath(path)


def _close(painter, size, ink):
    unit = size / 24.0
    pen = QPen(ink, 1.9 * unit)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    painter.drawLine(QPointF(8.2 * unit, 8.2 * unit), QPointF(15.8 * unit, 15.8 * unit))
    painter.drawLine(QPointF(15.8 * unit, 8.2 * unit), QPointF(8.2 * unit, 15.8 * unit))


def _plus(painter, size, ink):
    unit = size / 24.0
    pen = QPen(ink, 1.9 * unit)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    painter.drawLine(QPointF(12 * unit, 7.4 * unit), QPointF(12 * unit, 16.6 * unit))
    painter.drawLine(QPointF(7.4 * unit, 12 * unit), QPointF(16.6 * unit, 12 * unit))


def refresh(palette):
    return _icon(palette.subtext, _refresh)


def gear(palette):
    return _icon(palette.subtext, _gear)


def close(palette):
    return _icon(palette.subtext, _close)


def plus(palette):
    return _icon(palette.text, _plus)


def tick(colour, size):
    """The mark inside a checked box, as a path for a caller already painting."""
    unit = size / 16.0
    path = QPainterPath()
    path.moveTo(3.6 * unit, 8.4 * unit)
    path.lineTo(6.6 * unit, 11.4 * unit)
    path.lineTo(12.4 * unit, 4.9 * unit)
    return path, QPen(QColor(colour), 2.0 * unit, Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
