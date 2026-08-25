"""Settings: the defaults, and reading and writing settings.json.

An unreadable settings file falls back to the defaults rather than stopping the
application. The accounts are the valuable part and they live elsewhere.
"""

import dataclasses

from . import i18n, paths

# How often to look, in minutes. Fifteen by default: the five-hour window moves
# by about a third of a percent a minute at full tilt, so anything finer is
# watching paint dry, and the endpoint is not ours to lean on.
INTERVALS = (5, 15, 30, 60)

# What counts as running low. Offered as a few sensible steps rather than every
# whole number: nobody has an opinion about 73% that they do not have about 75%.
THRESHOLDS = (50, 60, 70, 75, 80, 85, 90, 95)


def _fits(want, value):
    """Whether a value out of the file is the shape its setting expects."""
    if want is bool:
        return isinstance(value, bool)
    if want is int:
        # bool is a subclass of int in Python, and "interval_minutes": true is
        # not one minute.
        return isinstance(value, int) and not isinstance(value, bool)
    return want is str and isinstance(value, str)


@dataclasses.dataclass
class Settings:
    autostart: bool = False
    interval_minutes: int = 15
    warn_at: int = 80
    notify: bool = True
    appearance: str = "system"        # system | light | dark
    language: str = ""                # "" means follow the desktop
    tray_percent: bool = True
    close_to_tray: bool = True

    def resolved_language(self):
        return self.language or i18n.system_language()

    def as_dict(self):
        return dataclasses.asdict(self)


def load():
    document = paths.read_json(paths.SETTINGS_FILE)
    if not isinstance(document, dict):
        return Settings()
    known = {f.name: f.type for f in dataclasses.fields(Settings)}
    # A settings file edited by hand is a normal thing to find. Take what is
    # the right shape and leave the rest at its default.
    clean = {key: value for key, value in document.items()
             if key in known and _fits(known[key], value)}
    settings = Settings(**clean)
    if settings.interval_minutes not in INTERVALS:
        settings.interval_minutes = Settings.interval_minutes
    settings.warn_at = max(10, min(100, settings.warn_at))
    if settings.appearance not in ("system", "light", "dark"):
        settings.appearance = "system"
    return settings


def save(settings):
    paths.write_json(paths.SETTINGS_FILE, settings.as_dict())
