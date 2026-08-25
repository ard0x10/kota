"""Calls to the three OAuth endpoints that Claude Code itself uses.

None of them is documented or public, so every read here is defensive: a field
that has gone missing leaves a gap in the table rather than raising. urllib
keeps the dependency list at PyQt6 and the standard library.
"""

import dataclasses
import json
import urllib.error
import urllib.request

from . import __version__

USAGE_URL = "https://api.anthropic.com/api/oauth/usage"
PROFILE_URL = "https://api.anthropic.com/api/oauth/profile"
TOKEN_URL = "https://claude.ai/v1/oauth/token"

# Claude Code's own client id, which is public: it travels in every OAuth
# redirect the desktop client makes.
CLIENT_ID = "9d1c250a-e61b-44d9-88ed-5944d1962f5e"

TIMEOUT = 25


class ApiError(Exception):
    """A request that did not come back with what was asked for."""

    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status

    @property
    def is_auth(self):
        return self.status == 401

    @property
    def is_rate_limit(self):
        return self.status == 429


def _request(url, *, token=None, body=None):
    headers = {
        "User-Agent": "kota/" + __version__,
        "anthropic-beta": "oauth-2025-04-20",
    }
    data = None
    if token:
        headers["Authorization"] = "Bearer " + token
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=data, headers=headers,
                                     method="POST" if data else "GET")
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        raise ApiError(_explain(error), error.code) from None
    except urllib.error.URLError as error:
        raise ApiError(str(error.reason)) from None
    except (OSError, ValueError) as error:
        raise ApiError(str(error)) from None


def _explain(error):
    """The clearest sentence available about a failed request."""
    if error.code == 401:
        return "signed out"
    if error.code == 429:
        return "rate limited"
    try:
        detail = json.loads(error.read().decode("utf-8"))
        message = detail.get("error")
        if isinstance(message, dict):
            message = message.get("message")
        if message:
            return str(message)
    except (OSError, ValueError, AttributeError):
        pass
    return "HTTP %d" % error.code


# --------------------------------------------------------------------------
@dataclasses.dataclass(frozen=True)
class Window:
    """One usage window: how full it is, and when it empties."""

    percent: float = 0.0
    resets_at: str = ""      # ISO 8601, UTC, as the API sends it


@dataclasses.dataclass(frozen=True)
class Extra:
    """Extra usage bought beyond the plan, in the account's own currency."""

    used: float = 0.0
    limit: float = 0.0
    percent: float = 0.0


@dataclasses.dataclass(frozen=True)
class Usage:
    """Everything the table shows for one account."""

    session: Window = dataclasses.field(default_factory=Window)
    week: Window = dataclasses.field(default_factory=Window)
    extra: Extra = None


def _number(value):
    """A float, whatever the field turned out to hold."""
    if isinstance(value, bool) or value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value))
    except ValueError:
        return 0.0


def _window(payload):
    if not isinstance(payload, dict):
        return Window()
    return Window(percent=_number(payload.get("utilization")),
                  resets_at=str(payload.get("resets_at") or ""))


def _extra(payload):
    """Extra usage, or None when the account has none switched on.

    The amounts arrive in minor units, with `decimal_places` saying how many to
    move the point by; a plan with none of this enabled sends nulls throughout.
    """
    if not isinstance(payload, dict) or not payload.get("is_enabled"):
        return None
    divisor = 10 ** int(_number(payload.get("decimal_places")))
    if divisor <= 0:
        divisor = 1
    return Extra(used=_number(payload.get("used_credits")) / divisor,
                 limit=_number(payload.get("monthly_limit")) / divisor,
                 percent=_number(payload.get("utilization")))


def usage(token):
    """What is left of this account's windows."""
    payload = _request(USAGE_URL, token=token)
    return Usage(session=_window(payload.get("five_hour")),
                 week=_window(payload.get("seven_day")),
                 extra=_extra(payload.get("extra_usage")))


def identity(token):
    """(uuid, email, plan) for whoever this token belongs to."""
    payload = _request(PROFILE_URL, token=token)
    account = payload.get("account") or {}
    return (str(account.get("uuid") or ""),
            str(account.get("email") or ""),
            "max" if account.get("has_claude_max") else "pro")


def refresh(refresh_token):
    """A new (access token, refresh token, lifetime in seconds).

    The refresh token that comes back may be the same one; when it is not, the
    old one is spent and the new one has to be kept or the account is lost.
    """
    payload = _request(TOKEN_URL, body={
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": CLIENT_ID,
    })
    access = payload.get("access_token")
    if not access:
        raise ApiError("the refresh answered without a token")
    return (str(access),
            str(payload.get("refresh_token") or refresh_token),
            int(_number(payload.get("expires_in")) or 0))
