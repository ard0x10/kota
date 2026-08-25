"""The main window and the settings dialog.

It knows how to show a reading and how to ask for one. Taking one is the
poller's job, off the interface thread, and the window holds no opinion about
when.
"""

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from . import config, formatting, i18n, icons, paths, secrets, trayicon
from .widgets import AccountCard, CheckBox


class MainWindow(QWidget):
    refresh_clicked = pyqtSignal()
    capture_clicked = pyqtSignal()
    remove_requested = pyqtSignal(str)
    settings_changed = pyqtSignal(object)

    def __init__(self, palette, settings):
        super().__init__()
        self.setObjectName("root")
        self._palette = palette
        self._settings = settings
        self._cards = {}
        self._taken_at = 0.0

        self.setWindowTitle("kota")
        self.setMinimumWidth(430)
        self.resize(470, 560)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        outer.addWidget(self._build_header())

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._holder = QWidget()
        self._stack = QVBoxLayout(self._holder)
        self._stack.setContentsMargins(14, 12, 14, 12)
        self._stack.setSpacing(10)
        self._stack.addStretch(1)
        self._scroll.setWidget(self._holder)
        outer.addWidget(self._scroll, 1)

        outer.addWidget(self._build_footer())
        self._empty = None
        # The buttons have no text, so an icon is the whole of them: set them
        # here rather than leaving a window with three blank buttons in it if
        # nobody gets round to calling apply_palette.
        self.apply_palette(palette)

    # ------------------------------------------------------------------
    def _build_header(self):
        band = QFrame()
        band.setObjectName("band")
        row = QHBoxLayout(band)
        row.setContentsMargins(14, 10, 10, 10)
        row.setSpacing(8)

        column = QVBoxLayout()
        column.setSpacing(1)
        title = QLabel("kota")
        title.setObjectName("title")
        column.addWidget(title)
        self._status = QLabel("")
        self._status.setObjectName("subtle")
        column.addWidget(self._status)
        row.addLayout(column)
        row.addStretch(1)

        self._refresh = QPushButton()
        self._refresh.setObjectName("quiet")
        self._refresh.setFixedWidth(34)
        self._refresh.setIconSize(QSize(18, 18))
        self._refresh.clicked.connect(self.refresh_clicked)
        row.addWidget(self._refresh)

        self._gear = QPushButton()
        self._gear.setObjectName("quiet")
        self._gear.setFixedWidth(34)
        self._gear.setIconSize(QSize(18, 18))
        self._gear.clicked.connect(self._open_settings)
        row.addWidget(self._gear)
        return band

    def _build_footer(self):
        band = QFrame()
        band.setObjectName("band")
        row = QHBoxLayout(band)
        row.setContentsMargins(14, 10, 14, 10)
        self._add = QPushButton("")
        self._add.setIconSize(QSize(15, 15))
        self._add.clicked.connect(self.capture_clicked)
        row.addWidget(self._add)
        row.addStretch(1)
        return band

    # ------------------------------------------------------------------
    def apply_palette(self, palette):
        self._palette = palette
        self._refresh.setIcon(icons.refresh(palette))
        self._gear.setIcon(icons.gear(palette))
        self._add.setIcon(icons.plus(palette))
        for card in self._cards.values():
            card.set_palette(palette)
        self.setWindowIcon(trayicon.app_icon(palette))

    def retranslate(self):
        self._refresh.setToolTip(i18n.t("Refresh"))
        self._gear.setToolTip(i18n.t("Settings"))
        self._add.setText("  " + i18n.t("Add the account signed in now"))
        for card in self._cards.values():
            card.retranslate()
        if self._empty is not None:
            self._empty_title.setText(i18n.t("No accounts yet"))
            self._empty_body.setText(i18n.t(
                "Sign in to Claude Code, then add the account here. Do it again "
                "for the second one."))
        self.touch_status()

    # ------------------------------------------------------------------
    def set_accounts(self, accounts):
        """Rebuild the stack so it holds exactly these accounts, in order."""
        for card in self._cards.values():
            card.setParent(None)
        self._cards.clear()
        if self._empty is not None:
            self._empty.setParent(None)
            self._empty = None

        if not accounts:
            self._show_empty()
        else:
            for index, account in enumerate(accounts):
                card = AccountCard(account, self._palette)
                card.remove_requested.connect(self._confirm_remove)
                card.show_waiting()
                self._stack.insertWidget(index, card)
                self._cards[account.uuid] = card
        self.retranslate()

    def _show_empty(self):
        self._empty = QWidget()
        column = QVBoxLayout(self._empty)
        column.setContentsMargins(20, 40, 20, 20)
        column.setSpacing(8)
        self._empty_title = QLabel("")
        self._empty_title.setObjectName("title")
        self._empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_body = QLabel("")
        self._empty_body.setObjectName("subtle")
        self._empty_body.setWordWrap(True)
        self._empty_body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        column.addWidget(self._empty_title)
        column.addWidget(self._empty_body)
        self._stack.insertWidget(0, self._empty)

    def show_report(self, report):
        card = self._cards.get(report.account.uuid)
        if card is not None:
            card.show_reading(report)

    def show_waiting(self):
        for card in self._cards.values():
            card.show_waiting()
        self._status.setText(i18n.t("Reading..."))

    def mark_taken(self, when):
        self._taken_at = when
        self.touch_status()

    def touch_status(self):
        """Re-say how old the reading is. Called on a timer while open."""
        if not self._taken_at:
            self._status.setText("")
            return
        self._status.setText(i18n.t("updated %s")
                             % i18n.t(formatting.ago(self._taken_at)))

    # ------------------------------------------------------------------
    def _confirm_remove(self, uuid):
        card = self._cards.get(uuid)
        name = card.uuid if card is None else card._name.text()
        box = QMessageBox(self)
        box.setWindowTitle(i18n.t("Remove"))
        box.setText(i18n.t("Remove %s?") % name)
        box.setInformativeText(
            i18n.t("kota will forget this account. Nothing is signed out."))
        remove = box.addButton(i18n.t("Remove"), QMessageBox.ButtonRole.DestructiveRole)
        box.addButton(i18n.t("Cancel"), QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is remove:
            self.remove_requested.emit(uuid)

    def _open_settings(self):
        dialog = SettingsDialog(self._settings, self._palette, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._settings = dialog.result_settings()
            self.settings_changed.emit(self._settings)

    def set_settings(self, settings):
        self._settings = settings

    # ------------------------------------------------------------------
    def closeEvent(self, event):
        """Closing puts kota back in the tray, unless it was told otherwise."""
        if self._settings.close_to_tray:
            event.ignore()
            self.hide()
        else:
            event.accept()


class SettingsDialog(QDialog):
    """Everything there is to decide, on one page and in plain words."""

    def __init__(self, settings, palette, parent=None):
        super().__init__(parent)
        self.setObjectName("root")
        self.setWindowTitle(i18n.t("Settings"))
        self.setMinimumWidth(400)
        self._settings = settings

        column = QVBoxLayout(self)
        column.setContentsMargins(18, 16, 18, 14)
        column.setSpacing(10)

        self._autostart = CheckBox(i18n.t("Start kota when I sign in"), palette)
        self._autostart.setChecked(settings.autostart)
        column.addWidget(self._autostart)

        self._interval = QComboBox()
        for minutes in config.INTERVALS:
            label = (i18n.t("1 hour") if minutes == 60
                     else i18n.t("%d minutes") % minutes)
            self._interval.addItem(label, minutes)
        self._interval.setCurrentIndex(config.INTERVALS.index(settings.interval_minutes))
        column.addLayout(_row(i18n.t("Check every"), self._interval))

        self._warn = QComboBox()
        steps = list(config.THRESHOLDS)
        if settings.warn_at not in steps:
            steps = sorted([*steps, settings.warn_at])
        for step in steps:
            self._warn.addItem("%d%%" % step, step)
        self._warn.setCurrentIndex(steps.index(settings.warn_at))
        # One thing to click, and the number it applies to beside it: a bare
        # checkbox in front of a label is two controls for one decision.
        self._notify = CheckBox(i18n.t("Warn me when a window passes"), palette)
        self._notify.setChecked(settings.notify)
        self._notify.toggled.connect(self._warn.setEnabled)
        self._warn.setEnabled(settings.notify)
        warn_row = QHBoxLayout()
        warn_row.setSpacing(8)
        warn_row.addWidget(self._notify)
        warn_row.addStretch(1)
        warn_row.addWidget(self._warn)
        column.addLayout(warn_row)

        self._appearance = QComboBox()
        for value, label in (("system", "System"), ("light", "Light"), ("dark", "Dark")):
            self._appearance.addItem(i18n.t(label), value)
        self._appearance.setCurrentIndex(
            ["system", "light", "dark"].index(settings.appearance))
        column.addLayout(_row(i18n.t("Appearance"), self._appearance))

        self._language = QComboBox()
        self._language.addItem(i18n.t("System"), "")
        self._language.addItem("English", "en")
        self._language.addItem("Türkçe", "tr")
        self._language.setCurrentIndex(["", "en", "tr"].index(settings.language))
        column.addLayout(_row(i18n.t("Language"), self._language))

        self._tray_percent = CheckBox(
            i18n.t("Show the percentage on the tray icon"), palette)
        self._tray_percent.setChecked(settings.tray_percent)
        column.addWidget(self._tray_percent)

        self._close_to_tray = CheckBox(
            i18n.t("Closing the window keeps kota in the tray"), palette)
        self._close_to_tray.setChecked(settings.close_to_tray)
        column.addWidget(self._close_to_tray)

        if not secrets.is_encrypted():
            warning = QLabel("⚠  " + i18n.t("Tokens are not encrypted on this machine"))
            warning.setStyleSheet("color: %s;" % palette.alarm)
            warning.setWordWrap(True)
            column.addWidget(warning)

        column.addSpacing(4)
        where = QLabel("%s\n%s" % (paths.pretty(paths.SETTINGS_FILE),
                                   paths.pretty(paths.ACCOUNTS_FILE)))
        where.setObjectName("subtle")
        where.setWordWrap(True)
        where.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        column.addWidget(QLabel(i18n.t("Where things are")))
        column.addWidget(where)

        column.addStretch(1)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        done = QPushButton(i18n.t("Done"))
        done.setObjectName("primary")
        done.clicked.connect(self.accept)
        buttons.addWidget(done)
        column.addLayout(buttons)

    def result_settings(self):
        return config.Settings(
            autostart=self._autostart.isChecked(),
            interval_minutes=self._interval.currentData(),
            warn_at=self._warn.currentData(),
            notify=self._notify.isChecked(),
            appearance=self._appearance.currentData(),
            language=self._language.currentData(),
            tray_percent=self._tray_percent.isChecked(),
            close_to_tray=self._close_to_tray.isChecked(),
        )


def _row(label, widget):
    row = QHBoxLayout()
    row.setSpacing(8)
    row.addWidget(QLabel(label))
    row.addStretch(1)
    row.addWidget(widget)
    return row
