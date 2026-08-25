"""Tray icon, window, and the background thread that reads accounts.

Nothing here touches the network on the interface thread. `Reader` does that on
its own and hands each account back the moment it lands, so a slow account
holds up nothing but its own card.
"""

import sys
import time

from PyQt6.QtCore import QLockFile, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from . import (
    autostart,
    config,
    creds,
    formatting,
    i18n,
    paths,
    store,
    theme,
    trayicon,
    widgets,
)
from .window import MainWindow

# How often the "updated 3m ago" line is re-said while the window is open.
STATUS_TICK_MS = 30_000


class Reader(QThread):
    """One pass over every account, off the interface thread."""

    accounts_ready = pyqtSignal(list)
    row = pyqtSignal(object)
    done = pyqtSignal(float)

    def run(self):
        try:
            accounts = store.load()
            accounts, _ = store.sync_active(accounts)
            # The window has to have a card before a row can go into it, and
            # queued signals arrive in the order they were sent.
            self.accounts_ready.emit(list(accounts))
            store.collect(accounts, on_row=self.row.emit)
        except Exception as error:
            # A reader that dies takes the schedule with it. Whatever went
            # wrong, the application stays up and says so on the next pass.
            sys.stderr.write("kota: reading failed: %r\n" % (error,))
        self.done.emit(time.time())


class Kota:
    def __init__(self, app):
        self.app = app
        self.settings = config.load()
        i18n.set_language(self.settings.resolved_language())
        self.palette = theme.choose(app, self.settings.appearance)

        self.reports = []
        self.reading = None
        self.warned = set()
        self.creds_stamp = creds.stamp()

        self.window = MainWindow(self.palette, self.settings)
        self.window.refresh_clicked.connect(self.refresh)
        self.window.capture_clicked.connect(self.capture)
        self.window.remove_requested.connect(self.remove)
        self.window.settings_changed.connect(self.adopt_settings)

        self.tray = self._build_tray()
        self._apply_appearance()

        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh)
        self.timer.start(self.settings.interval_minutes * 60_000)

        # Two cheap clocks: one to keep "updated 3m ago" honest, one to notice
        # that Claude Code has been signed in to a different account.
        self.ticker = QTimer()
        self.ticker.timeout.connect(self._tick)
        self.ticker.start(STATUS_TICK_MS)

        self.window.set_accounts(store.load())
        self.refresh()

    # ------------------------------------------------------------------
    def _build_tray(self):
        # The menu is built either way. Its actions are the only place some of
        # this text lives, and a machine with no tray was crashing on startup
        # reaching for actions that had never been made.
        # Held on the instance: a QMenu that only a local names is collected,
        # and its actions go with it.
        self.menu = menu = self._build_menu()
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return None
        tray = QSystemTrayIcon()
        tray.setIcon(trayicon.unknown_icon(self.palette))
        tray.activated.connect(self._tray_activated)
        tray.setContextMenu(menu)
        tray.show()
        return tray

    def _build_menu(self):
        menu = QMenu()
        self.menu_rows = []
        # Four lines kept ready: enough for anybody's accounts, and rebuilding
        # the menu under an open menu is what makes it flicker.
        for _ in range(4):
            action = QAction("", menu)
            action.setEnabled(False)
            action.setVisible(False)
            menu.addAction(action)
            self.menu_rows.append(action)
        menu.addSeparator()

        self.action_open = QAction(menu)
        self.action_open.triggered.connect(self.show_window)
        menu.addAction(self.action_open)

        self.action_refresh = QAction(menu)
        self.action_refresh.triggered.connect(self.refresh)
        menu.addAction(self.action_refresh)

        menu.addSeparator()
        self.action_quit = QAction(menu)
        self.action_quit.triggered.connect(self.app.quit)
        menu.addAction(self.action_quit)
        return menu

    def _retranslate_menu(self):
        self.action_open.setText(i18n.t("Open kota"))
        self.action_refresh.setText(i18n.t("Refresh"))
        self.action_quit.setText(i18n.t("Quit"))

    def _tray_activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger,
                      QSystemTrayIcon.ActivationReason.DoubleClick):
            if self.window.isVisible() and not self.window.isMinimized():
                self.window.hide()
            else:
                self.show_window()

    def show_window(self):
        self.window.showNormal()
        self.window.raise_()
        self.window.activateWindow()

    # ------------------------------------------------------------------
    def _apply_appearance(self):
        self.palette = theme.choose(self.app, self.settings.appearance)
        self.app.setStyleSheet(theme.stylesheet(self.palette))
        self.window.apply_palette(self.palette)
        self.window.retranslate()
        self._retranslate_menu()
        self._paint_tray()

    def adopt_settings(self, settings):
        was_language = self.settings.resolved_language()
        # Only asked for when it changed, and the answer is what the system
        # actually did rather than what was clicked.
        if (settings.autostart != self.settings.autostart
                and not autostart.apply(settings.autostart)):
            settings.autostart = autostart.enabled()
        self.settings = settings
        config.save(settings)

        i18n.set_language(settings.resolved_language())
        self.window.set_settings(settings)
        self.timer.start(settings.interval_minutes * 60_000)
        self._apply_appearance()
        if settings.resolved_language() != was_language:
            # The cards carry translated notes that only redraw on new data.
            for report in self.reports:
                self.window.show_report(report)

    # ------------------------------------------------------------------
    def refresh(self):
        if self.reading is not None and self.reading.isRunning():
            return
        self.window.show_waiting()
        self.reports = []
        self.reading = Reader()
        self.reading.accounts_ready.connect(self.window.set_accounts)
        self.reading.row.connect(self._took_row)
        self.reading.done.connect(self._finished)
        self.reading.start()

    def _took_row(self, report):
        self.reports.append(report)
        self.window.show_report(report)

    def _finished(self, when):
        self.creds_stamp = creds.stamp()
        self.window.mark_taken(when)
        self._paint_tray()
        self._maybe_warn()

    def _tick(self):
        self.window.touch_status()
        # A changed credentials file means a different account is signed in,
        # which is worth knowing about sooner than the next scheduled read.
        stamp = creds.stamp()
        if stamp != self.creds_stamp:
            self.creds_stamp = stamp
            self.refresh()

    # ------------------------------------------------------------------
    def _headline(self):
        """The one number the tray shows: the signed-in account's session.

        With no account signed in there is no obvious "mine", so the fullest
        window of the ones on show is the honest thing to put in the corner.
        """
        usable = [r for r in self.reports if r.usage is not None]
        if not usable:
            return None
        for report in usable:
            if report.active:
                return report
        return max(usable, key=lambda r: r.usage.session.percent)

    def _paint_tray(self):
        for index, action in enumerate(self.menu_rows):
            if index < len(self.reports):
                action.setText(self._menu_line(self.reports[index]))
                action.setVisible(True)
            else:
                action.setVisible(False)

        if self.tray is None:
            return
        headline = self._headline()
        if headline is None:
            self.tray.setIcon(trayicon.unknown_icon(self.palette))
            self.tray.setToolTip("kota")
        else:
            percent = headline.usage.session.percent
            self.tray.setIcon(trayicon.usage_icon(
                percent, self.palette, self.settings.tray_percent))
            self.tray.setToolTip(self._tooltip())

    def _menu_line(self, report):
        if report.usage is None:
            return "%s  —  %s" % (report.account.name, report.error or "?")
        return "%s  %.0f%% / %.0f%%  %s" % (
            report.account.name,
            report.usage.session.percent,
            report.usage.week.percent,
            formatting.countdown(report.usage.session.resets_at,
                                 units=widgets.units()))

    def _tooltip(self):
        lines = ["kota"]
        for report in self.reports:
            lines.append(self._menu_line(report))
        return "\n".join(lines)

    def _maybe_warn(self):
        """Say something once when a window crosses the line, not every pass."""
        if not self.settings.notify or self.tray is None:
            return
        limit = float(self.settings.warn_at)
        for report in self.reports:
            if report.usage is None:
                continue
            for key, percent, text in (
                    ("session", report.usage.session.percent,
                     "%s has used %.0f%% of the session"),
                    ("week", report.usage.week.percent,
                     "%s has used %.0f%% of the week")):
                token = (report.account.uuid, key)
                if percent >= limit and token not in self.warned:
                    self.warned.add(token)
                    self.tray.showMessage(
                        i18n.t("Quota is running out"),
                        i18n.t(text) % (report.account.name, percent),
                        trayicon.usage_icon(percent, self.palette, False))
                elif percent < limit:
                    self.warned.discard(token)

    # ------------------------------------------------------------------
    def capture(self):
        accounts, uuid, message = store.capture(store.load())
        if uuid is None and self.tray is not None:
            self.tray.showMessage("kota", i18n.t(message),
                                  trayicon.unknown_icon(self.palette))
        self.window.set_accounts(accounts)
        self.refresh()

    def remove(self, uuid):
        accounts = store.load()
        target = next((a for a in accounts if a.uuid == uuid), None)
        if target is None:
            return
        accounts, _ = store.remove(accounts, target.label or target.uuid)
        self.reports = [r for r in self.reports if r.account.uuid != uuid]
        self.window.set_accounts(accounts)
        if accounts:
            self.refresh()
        else:
            self._paint_tray()


def main(argv=None):
    app = QApplication(list(argv or sys.argv))
    app.setApplicationName("kota")
    app.setApplicationDisplayName("kota")
    # The tray is the application. Closing the window must not end it.
    app.setQuitOnLastWindowClosed(False)

    # One kota at a time: a second tray icon reading the same accounts would
    # only disagree with the first about when it last looked.
    paths.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(paths.CONFIG_DIR / "kota.lock"))
    lock.setStaleLockTime(0)
    if not lock.tryLock(100):
        sys.stderr.write("kota is already running.\n")
        return 0

    kota = Kota(app)
    if not QSystemTrayIcon.isSystemTrayAvailable():
        # With nowhere to live in the corner, the window is the application:
        # closing it has to end the process, or kota carries on invisibly with
        # no way left to reach it.
        kota.settings.close_to_tray = False
        app.setQuitOnLastWindowClosed(True)
        kota.show_window()
    elif "--hidden" not in (argv or sys.argv):
        kota.show_window()
    return app.exec()
