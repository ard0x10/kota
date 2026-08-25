"""Light and dark palettes, and the stylesheet built from one of them.

Catppuccin Latte and Frappe, rather than an invented palette: the same twelve
roles exist in both and are already balanced against each other, so light and
dark are one design instead of a design and a guess at its opposite.

Nothing outside this module names a colour. A widget asks for the role it means
and the two palettes stay in step on their own.
"""

import dataclasses

from PyQt6.QtCore import Qt

from . import formatting


@dataclasses.dataclass(frozen=True)
class Palette:
    dark: bool
    base: str        # the window behind everything
    mantle: str      # the header and footer bands
    surface: str     # a card sitting on the window
    line: str        # the hairline between things
    text: str        # what is being said
    subtext: str     # what is being said quietly
    faint: str       # a bar with nothing in it yet
    accent: str      # the marker on the signed-in account
    ok: str
    warn: str
    alarm: str

    def level(self, name):
        """The colour for one of formatting's three bands."""
        return {formatting.OK: self.ok,
                formatting.WARN: self.warn,
                formatting.ALARM: self.alarm}[name]


LIGHT = Palette(
    dark=False,
    base="#eff1f5", mantle="#e6e9ef", surface="#ffffff", line="#ccd0da",
    text="#4c4f69", subtext="#6c6f85", faint="#dce0e8", accent="#1e66f5",
    ok="#40a02b", warn="#df8e1d", alarm="#d20f39",
)

DARK = Palette(
    dark=True,
    base="#303446", mantle="#292c3c", surface="#3a3f52", line="#454a5f",
    text="#c6d0f5", subtext="#a5adce", faint="#414559", accent="#8caaee",
    ok="#a6d189", warn="#e5c890", alarm="#e78284",
)


def follows_system(app):
    """Whether the desktop is currently asking for a dark interface.

    Qt 6.5 and later answer this directly and change it under us when the
    desktop does. Older ones have no such notion, and the brightness of the
    palette they were built with is the next best evidence.
    """
    hints = app.styleHints()
    scheme = getattr(hints, "colorScheme", None)
    if scheme is not None:
        return scheme() == Qt.ColorScheme.Dark
    window = app.palette().window().color()
    return window.lightness() < 128


def choose(app, preference):
    """The palette to use, given what the person asked for."""
    if preference == "light":
        return LIGHT
    if preference == "dark":
        return DARK
    return DARK if follows_system(app) else LIGHT


def stylesheet(palette):
    """Everything Qt can be told in a stylesheet, which is most of the chrome.

    The meters and the tray icon are painted by hand instead; a stylesheet
    cannot express a bar whose colour depends on how full it is.
    """
    return """
    QWidget            { color: %(text)s; font-size: 13px; }
    #root              { background: %(base)s; }
    #band              { background: %(mantle)s; }
    #card              { background: %(surface)s; border: 1px solid %(line)s;
                         border-radius: 10px; }
    #title             { font-size: 15px; font-weight: 600; }
    #subtle            { color: %(subtext)s; }
    #plan              { color: %(subtext)s; border: 1px solid %(line)s;
                         border-radius: 7px; padding: 1px 7px; font-size: 11px; }
    #active            { color: %(accent)s; font-weight: 600; }

    QPushButton        { background: transparent; border: 1px solid %(line)s;
                         border-radius: 7px; padding: 5px 12px; color: %(text)s; }
    QPushButton:hover  { background: %(faint)s; }
    QPushButton:pressed{ background: %(line)s; }
    QPushButton:disabled { color: %(subtext)s; }
    QPushButton#quiet  { border: none; padding: 5px 8px; color: %(subtext)s; }
    QPushButton#quiet:hover { background: %(faint)s; color: %(text)s; }
    QPushButton#primary{ background: %(accent)s; border: none; color: %(surface)s;
                         font-weight: 600; }

    QComboBox          { background: %(surface)s; border: 1px solid %(line)s;
                         border-radius: 7px; padding: 4px 8px; min-width: 120px; }
    QComboBox QAbstractItemView { background: %(surface)s; border: 1px solid %(line)s;
                         selection-background-color: %(faint)s; outline: none; }
    QToolTip           { background: %(surface)s; color: %(text)s;
                         border: 1px solid %(line)s; padding: 4px; }
    QScrollArea        { border: none; background: %(base)s; }
    QScrollArea > QWidget > QWidget { background: %(base)s; }
    QScrollBar:vertical { background: transparent; width: 10px; margin: 0; }
    QScrollBar::handle:vertical { background: %(line)s; border-radius: 5px;
                         min-height: 30px; }
    QScrollBar::add-line, QScrollBar::sub-line { height: 0; }
    QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
    """ % dataclasses.asdict(palette)
