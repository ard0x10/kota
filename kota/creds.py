"""Reads the account Claude Code is currently signed in to.

This module never writes. Claude Code owns that file and the token chain in it,
and kota is very often running next to a live session: rotating the signed-in
account's refresh token would sign that session out.

Only `claudeAiOauth` is read. The same file carries `mcpOAuth`, which holds
client secrets for whatever MCP servers the user has connected.
"""

import dataclasses
import json
import os
import pathlib
import subprocess
import sys

# What macOS keeps instead of a file. Written from Claude Code's own behaviour
# and not yet watched working; on a Mac with nothing in the keychain kota simply
# finds no signed-in account, which is the same as not having signed in.
_MAC_SERVICE = "Claude Code-credentials"


@dataclasses.dataclass(frozen=True)
class Live:
    """The account signed in to Claude Code right now."""

    access_token: str
    refresh_token: str
    expires_at: int          # milliseconds since the epoch
    plan: str                # "pro", "max", whatever the file says


def path():
    """Where the credentials live on this system, file-shaped systems only."""
    return pathlib.Path(os.path.expanduser("~/.claude/.credentials.json"))


def stamp():
    """A value that changes when the credentials file does, or None.

    The window watches this to notice an account switch. Not for macOS, where
    there is no file to watch and a poll is the only way.
    """
    try:
        info = path().stat()
    except OSError:
        return None
    return (info.st_mtime_ns, info.st_size)


def _from_mapping(oauth):
    if not isinstance(oauth, dict):
        return None
    access = oauth.get("accessToken")
    if not access:
        return None
    return Live(
        access_token=access,
        refresh_token=oauth.get("refreshToken") or "",
        expires_at=int(oauth.get("expiresAt") or 0),
        plan=(oauth.get("subscriptionType") or "").lower(),
    )


def _read_macos():
    try:
        found = subprocess.run(
            ["security", "find-generic-password", "-s", _MAC_SERVICE, "-w"],
            capture_output=True, text=True, check=True, timeout=20)
        return json.loads(found.stdout)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def read():
    """The signed-in account, or None when nobody is signed in.

    Anything unreadable answers None too. A missing file, a half-written one, a
    shape that has changed under us: none of them is worth an exception here,
    because the honest report to the person is the same either way: kota cannot
    see an account signed in right now.
    """
    document = None
    if sys.platform == "darwin":
        document = _read_macos()
    if document is None:
        try:
            document = json.loads(path().read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            return None
    if not isinstance(document, dict):
        return None
    return _from_mapping(document.get("claudeAiOauth"))
