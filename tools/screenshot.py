"""Pictures of the window, from accounts that do not exist.

This is what the README shows. Made-up numbers on purpose: a screenshot of a
real run would put somebody's address and somebody's spending in a public
repository, and nothing about the design needs either to be true.

    python tools/screenshot.py docs

It also serves the other purpose the README does not care about: seeing the
window at every size and in both palettes without waiting on the network.
"""

import datetime
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from PyQt6.QtWidgets import QApplication

from kota import api, config, i18n, store, theme
from kota.window import MainWindow, SettingsDialog


def _in(**kwargs):
    """An ISO timestamp that far ahead, so the countdowns read sensibly."""
    moment = datetime.datetime.now(datetime.UTC) + datetime.timedelta(**kwargs)
    return moment.isoformat()


def sample():
    rows = [
        (store.Account(uuid="1", email="work@example.com", label="work", plan="max"),
         True,
         api.Usage(session=api.Window(45, _in(hours=2, minutes=30)),
                   week=api.Window(76, _in(days=1, hours=21)),
                   extra=api.Extra(39.6, 45.0, 88.0))),
        (store.Account(uuid="2", email="personal@example.com", label="personal"),
         False,
         api.Usage(session=api.Window(54, _in(hours=1, minutes=30)),
                   week=api.Window(84, _in(days=1, hours=21)),
                   extra=api.Extra(25.0, 65.0, 38.5))),
        (store.Account(uuid="3", email="side@example.com", label="side"),
         False,
         api.Usage(session=api.Window(3, _in(hours=4, minutes=12)),
                   week=api.Window(11, _in(days=2, hours=6)),
                   extra=None)),
    ]
    return [store.Report(account=a, active=active, usage=u) for a, active, u in rows]


def shoot(app, palette, language, into, name, dialog=False):
    i18n.set_language(language)
    settings = config.Settings()
    app.setStyleSheet(theme.stylesheet(palette))

    window = MainWindow(palette, settings)
    reports = sample()
    window.set_accounts([r.account for r in reports])
    for report in reports:
        window.show_report(report)
    window.mark_taken(time.time())
    window.resize(470, 560)
    window.show()
    app.processEvents()

    target = window
    if dialog:
        target = SettingsDialog(settings, palette, window)
        target.show()
        app.processEvents()

    path = into / (name + ".png")
    target.grab().save(str(path))
    target.close()
    window.close()
    print("wrote", path)


def main():
    into = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "docs")
    into.mkdir(parents=True, exist_ok=True)
    app = QApplication(sys.argv)
    shoot(app, theme.DARK, "en", into, "window-dark")
    shoot(app, theme.LIGHT, "en", into, "window-light")
    shoot(app, theme.DARK, "tr", into, "window-tr")
    shoot(app, theme.DARK, "en", into, "settings-dark", dialog=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
