"""Where the settings and accounts files live on each platform.

On Windows both go under `%LOCALAPPDATA%`. The accounts file must never end up
somewhere that roams: its tokens are encrypted against this machine and this
user, so on another machine they would arrive as noise and the account would
have to be captured again with no hint as to why.

`directories()` takes the platform as an argument so a test can stand on one it
is not running on.
"""

import os
import pathlib
import sys


def _env(var, default):
    """The directory a variable names, or the one it stands in for."""
    return pathlib.Path(os.environ.get(var) or os.path.expanduser(default))


def directories(platform=None):
    """(config, data), in the two places this system keeps them."""
    here = platform or sys.platform
    if here == "darwin":
        support = pathlib.Path.home() / "Library/Application Support/kota"
        return support, support
    if here == "win32":
        local = _env("LOCALAPPDATA", "~/AppData/Local")
        return local / "kota", local / "kota"
    return (_env("XDG_CONFIG_HOME", "~/.config") / "kota",
            _env("XDG_DATA_HOME", "~/.local/share") / "kota")


CONFIG_DIR, DATA_DIR = directories()

SETTINGS_FILE = CONFIG_DIR / "settings.json"
ACCOUNTS_FILE = DATA_DIR / "accounts.json"



def pretty(path):
    r"""A path said the way the system says it, and without a username in it.

    "%LOCALAPPDATA%\kota" is what a Windows user would type, is shorter than
    the real thing, and (the reason it matters here) can go in a screenshot
    without carrying whoever took it along with it.
    """
    text = str(path)
    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA")
        if local and text.startswith(local):
            return "%LOCALAPPDATA%" + text[len(local):]
    home = str(pathlib.Path.home())
    if text.startswith(home):
        return "~" + text[len(home):]
    return text


def write_json(path, data):
    """Write JSON to `path` so that a failure cannot leave it half written.

    Opening the real file for writing truncates it before anything is encoded,
    and an exception between those two moments loses the accounts. The
    temporary file next to it is on the same filesystem, so the replace is
    atomic.
    """
    import json

    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(data, indent=2, ensure_ascii=False)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(encoded, encoding="utf-8")
    os.replace(temp, path)


def read_json(path, default=None):
    """The JSON in `path`, or `default` when it is missing or unreadable.

    utf-8-sig rather than utf-8, because settings.json is a file people edit
    by hand and some editors leave a byte order mark in front of it.
    """
    import json

    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return default
