"""That the window can be built, filled and repainted without a screen.

Qt's offscreen platform, so this runs the same on a build machine as it does on
a desktop. It does not check that anything looks right, because no test can;
the pictures in docs/ are made by tools/screenshot.py and looked at. But it
does catch the window that comes up with three blank buttons, or the card that
throws on an account whose reading failed.
"""

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt6.QtWidgets import QApplication
except ImportError:                     # pragma: no cover
    QApplication = None

from kota import api, config, i18n, store, theme


@unittest.skipIf(QApplication is None, "PyQt6 will not load here")
class Window(unittest.TestCase):
    app = None

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def tearDown(self):
        i18n.set_language("en")

    def build(self, palette=None):
        from kota.window import MainWindow

        return MainWindow(palette or theme.DARK, config.Settings())

    def reports(self):
        account = store.Account(uuid="u1", email="a@example.com", label="work")
        other = store.Account(uuid="u2", email="b@example.com", label="personal")
        return [
            store.Report(account=account, active=True, usage=api.Usage(
                session=api.Window(45, ""), week=api.Window(76, ""),
                extra=api.Extra(39.6, 45.0, 88.0))),
            store.Report(account=other, error="signed out; capture again"),
        ]

    def test_a_window_with_accounts_in_it(self):
        window = self.build()
        reports = self.reports()
        window.set_accounts([r.account for r in reports])
        for report in reports:
            window.show_report(report)
        self.assertEqual(len(window._cards), 2)
        self.assertFalse(window.grab().isNull())

    def test_the_buttons_have_their_icons_from_the_start(self):
        """They carry no text, so an icon-less button is an invisible one."""
        window = self.build()
        for button in (window._refresh, window._gear, window._add):
            self.assertFalse(button.icon().isNull())

    def test_an_account_that_could_not_be_read(self):
        window = self.build()
        report = self.reports()[1]
        window.set_accounts([report.account])
        window.show_report(report)
        self.assertFalse(window.grab().isNull())

    def test_no_accounts_says_so(self):
        window = self.build()
        window.set_accounts([])
        self.assertEqual(len(window._cards), 0)
        self.assertFalse(window.grab().isNull())

    def test_both_palettes_paint(self):
        for palette in (theme.LIGHT, theme.DARK):
            window = self.build(palette)
            window.set_accounts([r.account for r in self.reports()])
            window.apply_palette(palette)
            self.assertFalse(window.grab().isNull())

    def test_switching_language_redraws(self):
        window = self.build()
        window.set_accounts([r.account for r in self.reports()])
        i18n.set_language("tr")
        window.retranslate()
        self.assertIn("hesab", window._add.text())

    def test_the_settings_dialog_builds(self):
        from kota.window import SettingsDialog

        dialog = SettingsDialog(config.Settings(warn_at=80), theme.DARK)
        self.assertEqual(dialog.result_settings().warn_at, 80)

    def test_a_threshold_the_dialog_does_not_offer_is_kept(self):
        from kota.window import SettingsDialog

        dialog = SettingsDialog(config.Settings(warn_at=73), theme.DARK)
        self.assertEqual(dialog.result_settings().warn_at, 73)


@unittest.skipIf(QApplication is None, "PyQt6 is not installed")
class Icons(unittest.TestCase):
    app = None

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_every_tray_size_has_a_pixmap(self):
        from kota import trayicon

        for icon in (trayicon.usage_icon(74, theme.DARK, True),
                     trayicon.usage_icon(0, theme.DARK, False),
                     trayicon.unknown_icon(theme.DARK)):
            for size in trayicon.SIZES:
                self.assertFalse(icon.pixmap(size, size).isNull())

    def test_the_chrome_icons_draw(self):
        from kota import icons

        for icon in (icons.refresh(theme.LIGHT), icons.gear(theme.LIGHT),
                     icons.close(theme.LIGHT), icons.plus(theme.LIGHT)):
            self.assertFalse(icon.pixmap(18, 18).isNull())


if __name__ == "__main__":
    unittest.main()
