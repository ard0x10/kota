"""Percentages, money and countdowns, as strings.

Pure functions, no Qt and no network, so the tests can cover the part most
likely to be wrong without standing anything up.
"""

import datetime
import time

# Where a number stops being comfortable and starts being worth noticing. The
# window, the tray icon and the terminal all take their colour from these two,
# so there is one place to argue with.
WARN_AT = 50.0
ALARM_AT = 80.0

OK, WARN, ALARM = "ok", "warn", "alarm"


def level(percent):
    """Which of the three bands a percentage falls in."""
    if percent >= ALARM_AT:
        return ALARM
    if percent >= WARN_AT:
        return WARN
    return OK


def parse_time(text):
    """The moment an ISO 8601 string names, as an aware datetime, or None."""
    if not text:
        return None
    try:
        # fromisoformat has understood a trailing Z since 3.11, which is the
        # oldest Python kota runs on.
        moment = datetime.datetime.fromisoformat(str(text))
    except (TypeError, ValueError):
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=datetime.UTC)
    return moment


def remaining(text, now=None):
    """How long until `text`, as a timedelta, or None if it says nothing."""
    moment = parse_time(text)
    if moment is None:
        return None
    return moment - (now or datetime.datetime.now(datetime.UTC))


DAY, HOUR, MINUTE = "d", "h", "m"


def countdown(text, now=None, units=(DAY, HOUR, MINUTE)):
    """"2h 48m": how long is left, in the two units that matter.

    Whole units, always rounded down: a window with 2h48m in it has two hours
    left, not three. The unit below is the remainder, never the total, so the
    two never contradict each other.

    `units` is how those two are spelled, because a Turkish window says
    "2s 48dk" and the terminal, which has a column to fit, says neither.
    """
    left = remaining(text, now)
    if left is None:
        return ""
    day, hour, minute = units
    seconds = int(left.total_seconds())
    if seconds <= 0:
        return "now"
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes = seconds // 60
    if days:
        return "%d%s %d%s" % (days, day, hours, hour)
    if hours:
        return "%d%s %d%s" % (hours, hour, minutes, minute)
    return "%d%s" % (minutes, minute)


def clock(text, now=None):
    """The local time of day a window comes back, "01:00"."""
    moment = parse_time(text)
    if moment is None:
        return ""
    return moment.astimezone().strftime("%H:%M")


def ago(when, now=None):
    """How long ago a reading was taken, for the line under the table."""
    if not when:
        return ""
    seconds = int((now or time.time()) - when)
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        return "%dm ago" % (seconds // 60)
    if seconds < 86400:
        return "%dh ago" % (seconds // 3600)
    return "%dd ago" % (seconds // 86400)


def money(amount):
    """A cost, with the cents only when there are any worth showing."""
    if amount is None:
        return ""
    if abs(amount - round(amount)) < 0.005:
        return "$%d" % round(amount)
    return "$%.2f" % amount


def money_pair(used, limit):
    """What has been spent, against what may be. Cents only where there are any."""
    return money(used) + " / " + money(limit)


def bar(percent, width=7, filled="#", empty="."):
    """The ASCII meter the terminal draws.

    ASCII rather than Unicode blocks: a Windows console on code page 857 or
    1254 turns those into noise, and the terminal output is exactly where that
    console is.
    """
    whole = round(max(0.0, min(100.0, percent)) / 100.0 * width)
    return filled * whole + empty * (width - whole)


def cut(text, width):
    """`text` in `width` columns, marked where it had to be cut."""
    if len(text) <= width:
        return text
    return text[:width - 1] + "~"
