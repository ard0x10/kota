# Contributing

kota is a small application and means to stay one. Two dependencies, Python
and PyQt6, and no third.

## Running it, and checking it

```sh
python -m kota            # the table
python -m kota --gui      # the window
python -m unittest discover -s tests -t .
ruff check .
```

The tests are offline, all of them: nothing signs in, nothing calls the API,
nothing reads or writes the real accounts file. `tests/test_gui.py` builds the
window on Qt's offscreen platform, so it runs the same on a build machine as on
a desktop.

Nothing tests that the window *looks* right, because no test can.
`tools/screenshot.py` draws it from accounts that do not exist, at both
palettes and in both languages, and somebody looks:

```sh
python tools/screenshot.py docs
```

Those pictures are what the README shows. Real accounts never go in one: a
screenshot of a live run puts somebody's address and somebody's spending in a
public repository.

## The rule that is not negotiable

**Nothing may write to `~/.claude/.credentials.json`.** kota runs next to a live
Claude Code session, and rotating the signed-in account's refresh token signs
that session out. `kota/creds.py` only ever reads, and `store._token_for`
refuses to refresh an account that is the active one, including the case where
the credentials file could not be read, which is the tempting one to get wrong.

`tests/test_store.py` has a class named after this. If you change anything in
that area, watch the file as well as the tests:

```powershell
$before = (Get-Item "$env:USERPROFILE\.claude\.credentials.json").LastWriteTime
kota
(Get-Item "$env:USERPROFILE\.claude\.credentials.json").LastWriteTime -eq $before
```

And do not test a refresh by rotating a live token. Rotation can invalidate the
copy Claude Code is holding and sign that account out. To check the endpoint,
send it a token you know is bad: the right address answers `400 invalid_grant`,
a wrong one answers `429` or `404`.

While reading `.credentials.json`, read `claudeAiOauth` and nothing else. The
same file carries `mcpOAuth`, which holds client secrets for whatever MCP
servers the person has connected. They are none of kota's business.

## How it is put together

`api.py` knows the three endpoints and how to read their answers, and knows
nothing about accounts. `store.py` knows about accounts and whose token may be
refreshed, and nothing about windows. `app.py` owns the tray, the window and
the thread that reads; `Reader` is the only thing that touches the network, and
it hands each account back the moment it lands so a slow one holds up nothing
but its own card.

Both the window and the terminal go through `store.collect`, so the two cannot
come to different conclusions about the same account.

Nothing outside `theme.py` names a colour. Ask for the role you mean
(`palette.warn`, `palette.surface`) and the light and dark palettes stay in
step on their own. Nothing outside `formatting.py` decides what counts as
running low, either.

Every string a person reads goes through `i18n.t()`, whose keys are the English
text itself: a string nobody has translated comes out in English, which is a
worse interface but never a broken one. That is also why the format strings are
`%`-style throughout: an f-string has already been formatted by the time
anything could translate it, and ruff is told so in `pyproject.toml`.

## Things worth knowing before you change them

- **The meters and the icons are painted, not styled.** A bar whose colour
  depends on how full it is cannot be written in a stylesheet, and neither can
  a checkbox's tick without shipping an image. `widgets.py` and `icons.py`.
- **Qt names its methods in camelCase.** An override has to match, which is why
  `N802` is switched off for the files that have them.
- **A QMenu that only a local variable names gets collected**, and its actions
  go with it. That was a crash once.
- **The menu is built whether or not there is a tray.** A machine with no
  system tray was crashing on startup reaching for actions never made, and the
  offscreen tests are exactly such a machine.
- **The countdown truncates, it does not round.** Round the hours and 2h48m
  reads "3h 48m", contradicting its own minutes. `test_formatting.py` pins
  this.

## Another system

Windows is what kota has been run on. macOS and Linux are written for, in
`paths.py`, `secrets.py`, `creds.py` and `autostart.py`. Each of them takes
the platform as an argument or reads `sys.platform` in one place, so a test can
stand on a system it is not on. None of it has been tried.

If you are on one of them: say what happened, including the boring parts. Where
the files landed, whether the tokens went into the keychain, whether the tray
icon appeared at all. `kota doctor` prints most of it.

## What a pull request should carry

What changed and why, in a sentence or two. If it touches the token paths, say
what you did to check `.credentials.json` did not move. If it changes the
window, put the before and after in; `tools/screenshot.py` makes both.
