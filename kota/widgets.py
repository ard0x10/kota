"""The meter and the account card.

Both are painted rather than styled. A bar whose colour depends on how full it
is cannot be written in a stylesheet, and once the bar is painted the text
beside it has to be painted too, or the two sit on different baselines at
different scale factors.
"""

from PyQt6.QtCore import QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath
from PyQt6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from . import formatting, i18n, icons

# The row: a label, the track, the number, and a note about when it empties.
LABEL_WIDTH = 72
VALUE_WIDTH = 46
NOTE_WIDTH = 116
ROW_HEIGHT = 30
TRACK_HEIGHT = 7


class Meter(QWidget):
    """One window's worth: how full it is, and when it comes back."""

    def __init__(self, label, palette, parent=None):
        super().__init__(parent)
        self._label = label
        self._palette = palette
        self._percent = 0.0
        self._note = ""
        self._known = False
        self.setFixedHeight(ROW_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_palette(self, palette):
        self._palette = palette
        self.update()

    def set_value(self, percent, note="", known=True):
        self._percent = max(0.0, min(100.0, float(percent)))
        self._note = note
        self._known = known
        self.update()

    def clear(self):
        self._percent, self._note, self._known = 0.0, "", False
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        palette = self._palette
        height = self.height()
        middle = height / 2.0

        small = QFont(self.font())
        small.setPointSizeF(max(7.5, small.pointSizeF() - 0.5))

        painter.setFont(small)
        painter.setPen(QColor(palette.subtext))
        painter.drawText(QRectF(0, 0, LABEL_WIDTH, height),
                         int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                         i18n.t(self._label))

        right = self.width()
        note_left = right - NOTE_WIDTH
        value_left = note_left - VALUE_WIDTH
        track_left = LABEL_WIDTH
        track_width = max(24, value_left - track_left - 12)

        track = QRectF(track_left, middle - TRACK_HEIGHT / 2.0,
                       track_width, TRACK_HEIGHT)
        radius = TRACK_HEIGHT / 2.0
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(palette.faint))
        painter.drawRoundedRect(track, radius, radius)

        if self._known:
            colour = QColor(palette.level(formatting.level(self._percent)))
            filled = track_width * self._percent / 100.0
            if filled > 0:
                # Never narrower than the cap it is drawn with, or a small
                # percentage renders as a lens rather than a bar.
                filled = max(filled, TRACK_HEIGHT)
                clip = QPainterPath()
                clip.addRoundedRect(track, radius, radius)
                painter.setClipPath(clip)
                painter.setBrush(colour)
                painter.drawRoundedRect(
                    QRectF(track.left(), track.top(), filled, TRACK_HEIGHT),
                    radius, radius)
                painter.setClipping(False)

            painter.setPen(colour)
            value_font = QFont(self.font())
            value_font.setBold(True)
            painter.setFont(value_font)
            painter.drawText(
                QRectF(value_left, 0, VALUE_WIDTH, height),
                int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
                "%.0f%%" % self._percent)

        if self._note:
            painter.setFont(small)
            painter.setPen(QColor(palette.subtext))
            box = QRectF(note_left + 8, 0, NOTE_WIDTH - 8, height)
            metrics = painter.fontMetrics()
            painter.drawText(
                box,
                int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
                metrics.elidedText(self._note, Qt.TextElideMode.ElideRight,
                                   int(box.width())))
        painter.end()

    def sizeHint(self):
        return QSize(LABEL_WIDTH + 200 + VALUE_WIDTH + NOTE_WIDTH, ROW_HEIGHT)


class AccountCard(QFrame):
    """One account: who it is, and the three meters that describe it."""

    remove_requested = pyqtSignal(str)

    def __init__(self, account, palette, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.uuid = account.uuid
        self._palette = palette

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 12, 14, 12)
        outer.setSpacing(6)

        head = QHBoxLayout()
        head.setSpacing(8)

        self._name = QLabel(account.name)
        self._name.setObjectName("title")
        head.addWidget(self._name)

        self._active = QLabel("")
        self._active.setObjectName("active")
        head.addWidget(self._active)

        head.addStretch(1)

        self._plan = QLabel(account.plan.upper())
        self._plan.setObjectName("plan")
        head.addWidget(self._plan)

        self._remove = QPushButton()
        self._remove.setObjectName("quiet")
        self._remove.setFixedWidth(26)
        self._remove.setIcon(icons.close(palette))
        self._remove.setIconSize(QSize(15, 15))
        self._remove.setToolTip(i18n.t("Remove"))
        self._remove.clicked.connect(lambda: self.remove_requested.emit(self.uuid))
        # Kept in the layout so nothing shifts, faded out until the pointer is
        # over the card: a row of crosses reads as a list of things to delete.
        self._fade = QGraphicsOpacityEffect(self._remove)
        self._fade.setOpacity(0.0)
        self._remove.setGraphicsEffect(self._fade)
        head.addWidget(self._remove)
        outer.addLayout(head)

        self._email = QLabel(account.email)
        self._email.setObjectName("subtle")
        outer.addWidget(self._email)
        outer.addSpacing(4)

        self.session = Meter("Session", palette)
        self.week = Meter("Week", palette)
        self.extra = Meter("Extra", palette)
        for meter in (self.session, self.week, self.extra):
            outer.addWidget(meter)

        self._message = QLabel("")
        self._message.setObjectName("subtle")
        self._message.setWordWrap(True)
        self._message.hide()
        outer.addWidget(self._message)

    def set_palette(self, palette):
        self._palette = palette
        self._remove.setIcon(icons.close(palette))
        for meter in (self.session, self.week, self.extra):
            meter.set_palette(palette)

    def enterEvent(self, event):
        self._fade.setOpacity(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._fade.setOpacity(0.0)
        super().leaveEvent(event)

    def retranslate(self):
        self._remove.setToolTip(i18n.t("Remove"))
        for meter in (self.session, self.week, self.extra):
            meter.update()

    def show_reading(self, report):
        """Fill the card in from one reading, or show why there is none."""
        self._active.setText("● " + i18n.t("signed in") if report.active else "")
        self._plan.setText(report.account.plan.upper())
        self._name.setText(report.account.name)
        self._email.setText(report.account.email)

        if report.error:
            for meter in (self.session, self.week, self.extra):
                meter.clear()
                meter.hide()
            self._message.setText(report.error)
            self._message.show()
            return

        self._message.hide()
        usage = report.usage
        self.session.show()
        self.session.set_value(usage.session.percent, _when(usage.session.resets_at))
        self.week.show()
        self.week.set_value(usage.week.percent, _when(usage.week.resets_at))

        if usage.extra is None:
            self.extra.hide()
        else:
            self.extra.show()
            self.extra.set_value(usage.extra.percent,
                                 formatting.money_pair(usage.extra.used,
                                                       usage.extra.limit))

    def show_waiting(self):
        self._message.hide()
        for meter in (self.session, self.week, self.extra):
            meter.show()
            meter.set_value(0, i18n.t("Reading..."), known=False)


def units():
    """How a countdown spells its units in the language in use."""
    return (i18n.t(formatting.DAY), i18n.t(formatting.HOUR), i18n.t(formatting.MINUTE))


def _when(resets_at):
    """"resets 2h 30m", said the way the language in use says it."""
    left = formatting.countdown(resets_at, units=units())
    if not left:
        return ""
    if left == "now":
        return i18n.t("resets now")
    return i18n.t("resets %s") % left


class CheckBox(QCheckBox):
    """A checkbox drawn here, because a stylesheet cannot draw the tick.

    Qt will style the box through `::indicator` but the mark inside it can only
    come from an image file, and this application ships none. Painting both is
    less code than shipping and finding a picture, and it follows the palette.
    """

    BOX = 16
    GAP = 9

    def __init__(self, text, palette, parent=None):
        super().__init__(text, parent)
        self._palette = palette
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_palette(self, palette):
        self._palette = palette
        self.update()

    def sizeHint(self):
        metrics = self.fontMetrics()
        return QSize(self.BOX + self.GAP + metrics.horizontalAdvance(self.text()) + 2,
                     max(self.BOX + 4, metrics.height() + 6))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        palette = self._palette
        top = (self.height() - self.BOX) / 2.0
        box = QRectF(0.5, top, self.BOX, self.BOX)

        if self.isChecked():
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(palette.accent))
            painter.drawRoundedRect(box, 4.5, 4.5)
            path, pen = icons.tick(palette.surface if palette.dark else "#ffffff",
                                   self.BOX)
            painter.save()
            painter.translate(box.topLeft())
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)
            painter.restore()
        else:
            painter.setPen(QColor(palette.line))
            painter.setBrush(QColor(palette.surface))
            painter.drawRoundedRect(box, 4.5, 4.5)

        painter.setPen(QColor(palette.text))
        painter.setFont(self.font())
        painter.drawText(
            QRectF(self.BOX + self.GAP, 0, self.width() - self.BOX - self.GAP,
                   self.height()),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            self.text())
        painter.end()
