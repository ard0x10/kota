"""Account records, and the rule about whose token may be refreshed.

An account is keyed by the UUID the API gives it, never by its address: an
email can be renamed or reused, and either would split one account into two or
merge two into one.

The signed-in account's token chain belongs to Claude Code. kota reads that
token and returns it unchanged. Only an account that is not signed in is ever
refreshed, and the result goes into kota's own file and nowhere else.
"""

import dataclasses
import time

from . import api, creds, paths, secrets

# Treat a token as spent slightly before it is, so a request cannot leave with
# one that expires while it is in flight.
_EARLY_MS = 120_000


@dataclasses.dataclass
class Account:
    uuid: str
    email: str
    label: str
    plan: str = "pro"
    access: str = ""          # as stored: "<backend>:<payload>"
    refresh: str = ""
    expires_at: int = 0       # milliseconds since the epoch
    updated_at: float = 0.0   # seconds since the epoch, for "as of"

    @property
    def name(self):
        """What to call this account when there is room for one word."""
        return self.label or self.email or self.uuid[:8]

    def as_dict(self):
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data):
        known = {f.name for f in dataclasses.fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})


@dataclasses.dataclass
class Report:
    """One row of the table: an account, and either numbers or a reason."""

    account: Account
    active: bool = False
    usage: api.Usage = None
    error: str = ""


def _now_ms():
    return int(time.time() * 1000)


# --------------------------------------------------------------------------
def load():
    """Every account kota knows, oldest entry first."""
    document = paths.read_json(paths.ACCOUNTS_FILE)
    if not isinstance(document, dict):
        return []
    rows = document.get("accounts")
    if not isinstance(rows, list):
        return []
    return [Account.from_dict(row) for row in rows if isinstance(row, dict)]


def save(accounts):
    paths.write_json(paths.ACCOUNTS_FILE,
                     {"version": 2, "accounts": [a.as_dict() for a in accounts]})
    secrets.restrict(paths.ACCOUNTS_FILE)


# --------------------------------------------------------------------------
def capture(accounts):
    """Fold the signed-in account into `accounts`.

    Returns (accounts, uuid, message). `uuid` is None when nobody is signed in
    or the API would not say who they are; `message` is what to tell a person
    either way.
    """
    live = creds.read()
    if live is None:
        return accounts, None, "No account is signed in to Claude Code."

    # An unchanged token is one we have already identified. Asking again would
    # be a request per run for an answer that cannot have changed.
    for account in accounts:
        if secrets.unprotect(account.access) == live.access_token:
            return accounts, account.uuid, "%s is already known." % account.name

    try:
        uuid, email, plan = api.identity(live.access_token)
    except api.ApiError as error:
        return accounts, None, "Could not read the signed-in account: %s" % error
    if not uuid:
        return accounts, None, "The signed-in account has no id to file it under."

    entry = Account(
        uuid=uuid,
        email=email,
        label=email.split("@")[0] if email else uuid[:8],
        plan=live.plan or plan,
        access=secrets.protect(live.access_token),
        refresh=secrets.protect(live.refresh_token),
        expires_at=live.expires_at,
        updated_at=time.time(),
    )

    kept, replaced = [], False
    for account in accounts:
        if account.uuid == uuid:
            secrets.forget(account.access)
            secrets.forget(account.refresh)
            kept.append(entry)
            replaced = True
        else:
            kept.append(account)
    if not replaced:
        kept.append(entry)

    save(kept)
    verb = "updated" if replaced else "added"
    return kept, uuid, "%s %s." % (entry.email or entry.name, verb)


def remove(accounts, target):
    """Forget the account called `target`, by label or by address."""
    kept, gone = [], None
    for account in accounts:
        if gone is None and target in (account.label, account.email, account.uuid):
            gone = account
        else:
            kept.append(account)
    if gone is None:
        return accounts, None
    secrets.forget(gone.access)
    secrets.forget(gone.refresh)
    save(kept)
    return kept, gone


def active_uuid(accounts):
    """Which of these accounts is signed in to Claude Code, if any."""
    live = creds.read()
    if live is None:
        return None
    for account in accounts:
        if secrets.unprotect(account.access) == live.access_token:
            return account.uuid
    return None


# --------------------------------------------------------------------------
def _token_for(account, is_active, live):
    """A usable access token for one account, refreshing only where allowed.

    Returns (token, changed). `changed` says whether the account was rewritten
    and the file needs saving.
    """
    if is_active and live is not None:
        # Claude Code has just put a fresh token in the credentials file; use
        # that one, and leave its chain entirely alone.
        return live.access_token, False

    token = secrets.unprotect(account.access)
    if token and account.expires_at > _now_ms() + _EARLY_MS:
        return token, False

    if is_active:
        # Signed in, but the credentials could not be read. Still not ours to
        # refresh: a rotation here is what signs the running session out.
        return token, False

    refresh_token = secrets.unprotect(account.refresh)
    if not refresh_token:
        return None, False

    access, rotated, lifetime = api.refresh(refresh_token)
    secrets.forget(account.access)
    if rotated != refresh_token:
        secrets.forget(account.refresh)
        account.refresh = secrets.protect(rotated)
    account.access = secrets.protect(access)
    account.expires_at = _now_ms() + lifetime * 1000
    account.updated_at = time.time()
    return access, True


def collect(accounts, on_row=None):
    """Read every account's usage. Returns (reports, accounts).

    `on_row` is called with each Report as it lands, so a window can fill in
    one account at a time instead of waiting for the slowest.
    """
    live = creds.read()
    active = None
    if live is not None:
        for account in accounts:
            if secrets.unprotect(account.access) == live.access_token:
                active = account.uuid
                break

    reports, dirty = [], False
    for account in accounts:
        is_active = account.uuid == active
        report = Report(account=account, active=is_active)
        try:
            token, changed = _token_for(account, is_active, live)
            dirty = dirty or changed
            if not token:
                raise api.ApiError("no usable token; capture this account again")
            report.usage = api.usage(token)
            account.updated_at = time.time()
        except api.ApiError as error:
            if error.is_auth:
                report.error = "signed out; capture this account again"
            else:
                report.error = str(error)
        reports.append(report)
        if on_row is not None:
            on_row(report)

    if dirty:
        save(accounts)
    return reports, accounts


def sync_active(accounts):
    """Quietly keep the signed-in account current, and say if anything moved.

    This is what makes switching accounts the normal way enough: every refresh
    of the display folds in whoever is signed in now, without anybody having to
    remember a command.
    """
    live = creds.read()
    if live is None:
        return accounts, False
    for account in accounts:
        if secrets.unprotect(account.access) == live.access_token:
            return accounts, False
    accounts, uuid, _ = capture(accounts)
    return accounts, uuid is not None
