"""Registering kota to start when the user signs in.

Windows uses a value under the user's own Run key: no administrator, no COM, no
shortcut file to keep in step with a moved checkout. The macOS and Linux paths
are written from their documented shapes and are untried.

Everything here returns False rather than raising. Autostart is a convenience,
never a reason to take the application down.
"""

import contextlib
import os
import pathlib
import sys

NAME = "kota"

_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def _entry_point():
    """The command that starts the window, as this copy was actually run."""
    module = pathlib.Path(__file__).resolve().parent / "__main__.py"
    executable = pathlib.Path(sys.executable)
    if sys.platform == "win32":
        # pythonw runs it with no console window standing behind the tray icon.
        quiet = executable.with_name("pythonw.exe")
        if quiet.exists():
            executable = quiet
    return executable, module


def _windows_command():
    executable, module = _entry_point()
    return '"%s" "%s" --gui' % (executable, module)


# --------------------------------------------------------------------------
def _windows_set(enabled):
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0,
                            winreg.KEY_SET_VALUE) as key:
            if enabled:
                winreg.SetValueEx(key, NAME, 0, winreg.REG_SZ, _windows_command())
            else:
                with contextlib.suppress(FileNotFoundError):
                    winreg.DeleteValue(key, NAME)
        return True
    except OSError:
        return False


def _windows_get():
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key, NAME)
            return bool(value)
    except OSError:
        return False


# --------------------------------------------------------------------------
def _desktop_file():
    root = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return pathlib.Path(root) / "autostart" / "kota.desktop"


def _linux_set(enabled):
    target = _desktop_file()
    try:
        if not enabled:
            target.unlink(missing_ok=True)
            return True
        executable, module = _entry_point()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            "[Desktop Entry]\n"
            "Type=Application\n"
            "Name=kota\n"
            "Comment=Claude quota, in the tray\n"
            'Exec="%s" "%s" --gui\n'
            "Terminal=false\n"
            "X-GNOME-Autostart-enabled=true\n" % (executable, module),
            encoding="utf-8")
        return True
    except OSError:
        return False


def _agent_file():
    return pathlib.Path.home() / "Library/LaunchAgents/dev.kota.plist"


def _macos_set(enabled):
    target = _agent_file()
    try:
        if not enabled:
            target.unlink(missing_ok=True)
            return True
        executable, module = _entry_point()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
            '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
            '<plist version="1.0"><dict>\n'
            "  <key>Label</key><string>dev.kota</string>\n"
            "  <key>ProgramArguments</key>\n"
            "  <array><string>%s</string><string>%s</string>"
            "<string>--gui</string></array>\n"
            "  <key>RunAtLoad</key><true/>\n"
            "</dict></plist>\n" % (executable, module),
            encoding="utf-8")
        return True
    except OSError:
        return False


# --------------------------------------------------------------------------
def enabled():
    """Whether this system is set to start kota at sign-in."""
    if sys.platform == "win32":
        return _windows_get()
    if sys.platform == "darwin":
        return _agent_file().exists()
    return _desktop_file().exists()


def apply(wanted):
    """Ask for autostart, or ask for it to stop. True if the system agreed."""
    if sys.platform == "win32":
        return _windows_set(wanted)
    if sys.platform == "darwin":
        return _macos_set(wanted)
    return _linux_set(wanted)
