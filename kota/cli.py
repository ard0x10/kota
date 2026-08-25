"""The command line interface.

Runs through the same `store.collect` as the window, so the two can never come
to different conclusions.
"""

import argparse
import json
import os
import sys

from . import __version__, formatting, secrets, store

# The eight colours every terminal has had since the 1980s, which is all this
# needs and the only set that survives a Windows console honestly.
_ANSI = {
    "reset": "\033[0m", "dim": "\033[90m", "cyan": "\033[36m",
    formatting.OK: "\033[32m", formatting.WARN: "\033[33m",
    formatting.ALARM: "\033[31m",
}


def _colour_ready(stream):
    """Whether to put colour on this stream at all.

    NO_COLOR is honoured because it is the convention, a redirected stream gets
    none because the file would only fill with escapes, and a Windows console
    has to be asked to interpret them before any of it means anything.
    """
    if os.environ.get("NO_COLOR"):
        return False
    if not hasattr(stream, "isatty") or not stream.isatty():
        return False
    if sys.platform == "win32":
        return _enable_windows_ansi()
    return True


def _enable_windows_ansi():
    """Turn on the console's own escape handling. True if it took."""
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        # ENABLE_VIRTUAL_TERMINAL_PROCESSING
        return bool(kernel32.SetConsoleMode(handle, mode.value | 0x0004))
    except (OSError, AttributeError):
        return False


class Painter:
    def __init__(self, enabled):
        self.enabled = enabled

    def __call__(self, text, colour):
        if not self.enabled or colour not in _ANSI:
            return text
        return _ANSI[colour] + text + _ANSI["reset"]


# --------------------------------------------------------------------------
def _table(reports, paint, out):
    header = "    %-14s%-14s%-14s%-16s%s" % (
        "ACCOUNT", "SESSION", "WEEK", "EXTRA", "RESETS (5H)")
    print(file=out)
    print(paint(header, "dim"), file=out)
    print(paint("  " + "-" * 76, "dim"), file=out)

    for report in reports:
        marker = ">" if report.active else " "
        line = paint("  %s " % marker, "cyan")
        line += formatting.cut(report.account.name, 13).ljust(14)

        if report.error:
            print(line + paint(report.error, formatting.ALARM), file=out)
            continue

        for window in (report.usage.session, report.usage.week):
            cell = "%s %3.0f%%" % (formatting.bar(window.percent), window.percent)
            line += paint(cell.ljust(14), formatting.level(window.percent))

        extra = report.usage.extra
        if extra is None:
            line += paint("-".ljust(16), "dim")
        else:
            cost = formatting.money_pair(extra.used, extra.limit)
            line += paint(cost.ljust(16), formatting.level(extra.percent))

        when = report.usage.session.resets_at
        line += paint("%s  %s" % (formatting.clock(when), formatting.countdown(when)),
                      "dim")
        print(line, file=out)

    print(file=out)
    for report in reports:
        if not report.error and report.usage.week.resets_at:
            when = report.usage.week.resets_at
            print(paint("  Week resets: %s  %s" % (formatting.clock(when),
                                                   formatting.countdown(when)), "dim"),
                  file=out)
            break
    print(paint("  > = signed in right now", "dim"), file=out)
    print(file=out)


def _as_json(reports):
    accounts = []
    for report in reports:
        row = {
            "label": report.account.label,
            "email": report.account.email,
            "plan": report.account.plan,
            "active": report.active,
            "error": report.error or None,
        }
        if report.usage is not None:
            row["session"] = {"utilization": report.usage.session.percent,
                              "resets_at": report.usage.session.resets_at or None}
            row["week"] = {"utilization": report.usage.week.percent,
                           "resets_at": report.usage.week.resets_at or None}
            extra = report.usage.extra
            row["extra"] = None if extra is None else {
                "used": extra.used, "limit": extra.limit,
                "utilization": extra.percent}
        accounts.append(row)
    return json.dumps({"version": 2, "accounts": accounts}, indent=2)


# --------------------------------------------------------------------------
def _read_all():
    accounts = store.load()
    accounts, _ = store.sync_active(accounts)
    return accounts


def show(args, out):
    accounts = _read_all()
    paint = Painter(_colour_ready(out) and not args.no_color)
    if not accounts:
        print("\n  No accounts yet. Run 'kota capture' while signed in.\n", file=out)
        return 0
    reports, _ = store.collect(accounts)
    _table(reports, paint, out)
    return 1 if any(r.error for r in reports) else 0


def as_json(args, out):
    accounts = _read_all()
    if not accounts:
        print(json.dumps({"version": 2, "accounts": []}, indent=2), file=out)
        return 0
    reports, _ = store.collect(accounts)
    print(_as_json(reports), file=out)
    return 0


def capture(args, out):
    accounts, uuid, message = store.capture(store.load())
    print("\n  %s" % message, file=out)
    if uuid is None:
        print(file=out)
        return 1
    print("  Accounts known: %d" % len(accounts), file=out)
    if len(accounts) < 2:
        print("  Sign in to the other account and run it again.", file=out)
    print(file=out)
    return 0


def listing(args, out):
    accounts = store.load()
    if not accounts:
        print("\n  No accounts yet. Run 'kota capture' while signed in.\n", file=out)
        return 0
    active = store.active_uuid(accounts)
    print(file=out)
    for account in accounts:
        marker = ">" if account.uuid == active else " "
        print("  %s %-14s %-34s %s" % (marker, account.label, account.email,
                                       account.plan), file=out)
    print(file=out)
    return 0


def remove(args, out):
    _, gone = store.remove(store.load(), args.name)
    if gone is None:
        print("\n  '%s' is not one of the accounts kota knows.\n" % args.name, file=out)
        return 1
    print("\n  '%s' removed.\n" % (gone.email or gone.name), file=out)
    return 0


def where(args, out):
    """Say where everything is, for when something has gone wrong."""
    from . import creds, paths

    print(file=out)
    print("  kota            %s" % __version__, file=out)
    print("  python          %s" % sys.version.split()[0], file=out)
    print("  settings        %s" % paths.pretty(paths.SETTINGS_FILE), file=out)
    print("  accounts        %s" % paths.pretty(paths.ACCOUNTS_FILE), file=out)
    plain = "" if secrets.is_encrypted() else "  (NOT encrypted)"
    print("  secrets         %s%s" % (secrets.backend(), plain), file=out)
    print("  claude code     %s%s" % (paths.pretty(creds.path()),
                                      "" if creds.path().exists() else "  (not found)"),
          file=out)
    print("  signed in       %s" % ("yes" if creds.read() else "no"), file=out)
    print(file=out)
    return 0


# --------------------------------------------------------------------------
def build_parser():
    parser = argparse.ArgumentParser(
        prog="kota",
        description="How much Claude quota every account you have has left.")
    parser.add_argument("--version", action="version",
                        version="kota " + __version__)
    parser.add_argument("--no-color", action="store_true",
                        help="plain output; NO_COLOR in the environment does the same")
    parser.add_argument("--gui", action="store_true",
                        help="open the window instead of printing a table")

    commands = parser.add_subparsers(dest="command")
    commands.add_parser("capture", help="remember the account signed in right now")
    commands.add_parser("list", help="the accounts kota knows about")
    commands.add_parser("json", help="the same numbers, for a script to read")
    commands.add_parser("doctor", help="where everything is, when something is wrong")
    forget = commands.add_parser("remove", help="forget an account")
    forget.add_argument("name", help="its label or its address")
    return parser


_COMMANDS = {
    None: show, "capture": capture, "list": listing,
    "json": as_json, "remove": remove, "doctor": where,
}


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.gui:
        from .app import main as gui

        return gui([])
    return _COMMANDS[args.command](args, sys.stdout)
