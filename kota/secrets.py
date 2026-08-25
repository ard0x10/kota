"""Token storage, through whatever the platform provides.

An access token is a bearer token, and a refresh token renews it for a month,
so the accounts file holds only a reference and the secret goes to the system
keystore.

Every stored value carries the name of the backend that made it, so a file
written by one is never handed to another. A value that cannot be decrypted
comes back as None rather than raising: that account needs capturing again, it
is not a crash.

Windows is the tested path. The macOS and Linux backends are written against
the documented behaviour of `security` and `secret-tool` and are untried.
"""

import base64
import contextlib
import os
import shutil
import subprocess
import sys
import uuid

# What a stored value looks like: "<backend>:<payload>". Splitting on the first
# colon is safe because no backend name contains one.
_SEP = ":"


# --------------------------------------------------------------------------
# Windows: DPAPI, through ctypes, so nothing has to be installed for it.
# --------------------------------------------------------------------------
def _dpapi_calls():
    import ctypes
    import ctypes.wintypes

    class Blob(ctypes.Structure):
        _fields_ = [("cbData", ctypes.wintypes.DWORD),
                    ("pbData", ctypes.POINTER(ctypes.c_char))]

    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32

    def call(fn, data):
        buffer = ctypes.create_string_buffer(data, len(data))
        source = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char)))
        result = Blob()
        if not fn(ctypes.byref(source), None, None, None, None, 0, ctypes.byref(result)):
            raise OSError(ctypes.GetLastError(), "DPAPI refused the data")
        try:
            return ctypes.string_at(result.pbData, result.cbData)
        finally:
            kernel32.LocalFree(result.pbData)

    return (lambda data: call(crypt32.CryptProtectData, data),
            lambda data: call(crypt32.CryptUnprotectData, data))


def _dpapi_protect(text):
    protect, _ = _dpapi_calls()
    return base64.b64encode(protect(text.encode("utf-8"))).decode("ascii")


def _dpapi_unprotect(payload):
    _, unprotect = _dpapi_calls()
    return unprotect(base64.b64decode(payload)).decode("utf-8")


# --------------------------------------------------------------------------
# macOS and Linux: the system keeps the secret, kota keeps a name for it.
# --------------------------------------------------------------------------
_SERVICE = "kota"


def _run(argv, stdin=None):
    return subprocess.run(argv, input=stdin, capture_output=True, text=True,
                          check=True, timeout=20)


def _keychain_protect(text):
    name = uuid.uuid4().hex
    _run(["security", "add-generic-password", "-U",
          "-s", _SERVICE, "-a", name, "-w", text])
    return name


def _keychain_unprotect(name):
    return _run(["security", "find-generic-password",
                 "-s", _SERVICE, "-a", name, "-w"]).stdout.rstrip("\n")


def _libsecret_protect(text):
    name = uuid.uuid4().hex
    _run(["secret-tool", "store", "--label=kota",
          "service", _SERVICE, "account", name], stdin=text)
    return name


def _libsecret_unprotect(name):
    return _run(["secret-tool", "lookup",
                 "service", _SERVICE, "account", name]).stdout


# --------------------------------------------------------------------------
# The fallback, when a system offers nowhere better.
# --------------------------------------------------------------------------
def _plain_protect(text):
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


def _plain_unprotect(payload):
    return base64.b64decode(payload).decode("utf-8")


_BACKENDS = {
    "dpapi": (_dpapi_protect, _dpapi_unprotect),
    "keychain": (_keychain_protect, _keychain_unprotect),
    "libsecret": (_libsecret_protect, _libsecret_unprotect),
    "plain": (_plain_protect, _plain_unprotect),
}


def backend(platform=None):
    """The name of the backend this system can actually use."""
    here = platform or sys.platform
    if here == "win32":
        return "dpapi"
    if here == "darwin":
        return "keychain" if shutil.which("security") else "plain"
    return "libsecret" if shutil.which("secret-tool") else "plain"


def is_encrypted(name=None):
    """Whether the backend in use puts the secret out of plain sight.

    False means `plain`, and the window says so: base64 is not encryption, and
    a person deciding whether to keep a refresh token on that machine deserves
    to be told rather than reassured.
    """
    return (name or backend()) != "plain"


def protect(text):
    """A stored form of `text`, tagged with the backend that made it."""
    if not text:
        return ""
    name = backend()
    try:
        return name + _SEP + _BACKENDS[name][0](text)
    except (OSError, ValueError, subprocess.SubprocessError):
        # Falling back is better than losing the account, and the window is
        # already showing that this machine has nowhere safe to put it.
        return "plain" + _SEP + _plain_protect(text)


def unprotect(stored):
    """The text behind a stored value, or None if it cannot be read here."""
    if not stored or _SEP not in stored:
        return None
    name, _, payload = stored.partition(_SEP)
    if name not in _BACKENDS:
        return None
    try:
        return _BACKENDS[name][1](payload) or None
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def forget(stored):
    """Remove a secret the system is holding for us, if it is holding one.

    DPAPI and base64 keep nothing outside the file, so for those there is
    nothing to do; a keychain entry would otherwise outlive the account.
    """
    if not stored or _SEP not in stored:
        return
    name, _, payload = stored.partition(_SEP)
    with contextlib.suppress(OSError, subprocess.SubprocessError):
        if name == "keychain":
            _run(["security", "delete-generic-password",
                  "-s", _SERVICE, "-a", payload])
        elif name == "libsecret":
            _run(["secret-tool", "clear", "service", _SERVICE, "account", payload])


def restrict(path):
    """Take a file's permissions down to its owner, where that means anything.

    Windows inherits ACLs from the user's own AppData, which is already
    private; chmod there sets a bit nothing reads.
    """
    if sys.platform == "win32":
        return
    with contextlib.suppress(OSError):
        os.chmod(path, 0o600)
