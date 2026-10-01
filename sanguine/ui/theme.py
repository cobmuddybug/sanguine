"""Colour palette. Follows the active Omarchy theme when available; crimson otherwise.

Every colour the UI uses is derived from a handful of theme colours (background,
foreground, muted, red, yellow), so switching Omarchy themes re-colours the game
on next launch. SANGUINE_THEME=crimson forces the built-in palette.
"""
from __future__ import annotations

import os
import re
import tomllib
from pathlib import Path

CSS_FILE = Path(__file__).with_name("sanguine.tcss")

# The built-in crimson palette: bone-white text on near-black, blood-red accents, hellfire orange for danger.
# NB: the keys "green" and "red" are roles, not hues: "green" is the primary accent (blood) and
# "red" is the alert colour (hellfire); the stylesheet literals still use the original key names.
CRIMSON = {
    "bg": "#0a0607", "fg": "#d9c9c4", "fg_bright": "#fff1ec", "muted": "#8f6d73",
    "green": "#ff2e58", "red": "#ff7a2e", "yellow": "#d9a520",
}


def _rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _hex(c) -> str:
    return "#%02x%02x%02x" % tuple(max(0, min(255, round(v))) for v in c)


def mix(a: str, b: str, t: float) -> str:
    """t=0 -> a, t=1 -> b."""
    ca, cb = _rgb(a), _rgb(b)
    return _hex([x + (y - x) * t for x, y in zip(ca, cb)])


def _lum(h: str) -> float:
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (ch(v) for v in _rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast(a: str, b: str) -> float:
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _readable(color: str, bg: str, want: float = 4.5) -> str:
    """Lighten a colour until it reads on the (dark) background."""
    for i in range(12):
        if _contrast(color, bg) >= want:
            break
        color = mix(color, "#ffffff", 0.12)
    return color


def _theme_colors() -> dict | None:
    if os.environ.get("SANGUINE_THEME", "").lower() == "crimson":
        return None
    state = os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state")
    path = Path(state) / "omarchy" / "current" / "theme" / "colors.toml"
    try:
        c = tomllib.loads(path.read_text())
        if c.get("mode", "dark") != "dark":
            return None
        for k in ("background", "foreground"):
            _rgb(c[k])
        return c
    except (OSError, ValueError, KeyError, IndexError):
        return None


def base_colors() -> dict:
    c = _theme_colors()
    if not c:
        return dict(CRIMSON)
    bg = c["background"]
    if _lum(bg) > 0.05:      # not a dark theme after all
        return dict(CRIMSON)
    g = lambda *keys, default: next((c[k] for k in keys if k in c), default)
    fg = g("foreground", default=CRIMSON["fg"])
    return {
        "bg": bg,
        "fg": _readable(fg, bg, 7),
        "fg_bright": _readable(g("bright_foreground", default=fg), bg, 9),
        "muted": _readable(g("muted", "dark_foreground", default=mix(bg, fg, 0.5)), bg, 4.5),
        # accent = the theme's red (blood); alert = red pulled toward yellow (hellfire)
        "green": _readable(g("bright_red", "red", default=CRIMSON["green"]), bg, 5),
        "red": _readable(mix(g("bright_red", "red", default=CRIMSON["green"]),
                             g("bright_yellow", "yellow", default=CRIMSON["yellow"]), 0.45), bg, 5),
        "yellow": _readable(g("bright_yellow", "yellow", default=CRIMSON["yellow"]), bg, 6),
    }


def build_palette(b: dict) -> dict:
    bg, fg = b["bg"], b["fg"]
    return {
        "bg": bg,
        "panel": mix(bg, fg, 0.04), "panel2": mix(bg, fg, 0.07),
        "hover": mix(bg, fg, 0.11), "hover2": mix(bg, fg, 0.15),
        "line": mix(bg, fg, 0.14), "line2": mix(bg, fg, 0.20),
        "off_fg": mix(bg, fg, 0.34), "off_fg2": mix(bg, fg, 0.26),
        "ok_btn": mix(bg, b["green"], 0.30), "ok_mid": mix(bg, b["green"], 0.50), "ok_hi": mix(bg, b["green"], 0.75),
        "green": b["green"], "red": b["red"], "red_hi": mix(b["red"], "#ffffff", 0.3),
        "red_dim": mix(bg, b["red"], 0.55), "red_btn": mix(bg, b["red"], 0.22),
        "red_txt": mix(fg, b["red"], 0.25), "red_off": mix(bg, b["red"], 0.45),
        "fg": fg, "fg_bright": b["fg_bright"], "muted": b["muted"], "muted2": mix(fg, b["muted"], 0.5),
        "amber": b["yellow"],
    }


PAL = build_palette(base_colors())

# literal in sanguine.tcss -> palette key
_LITERALS = {
    "#07090a": "bg", "#0a100d": "panel", "#0c1210": "panel", "#0d1210": "panel",
    "#0f1712": "panel2", "#101713": "panel2", "#0f1a14": "panel2",
    "#12201a": "hover", "#16261d": "hover2", "#1c2a22": "line", "#1a2a20": "line",
    "#1c3a2a": "ok_btn", "#16803a": "ok_mid", "#1fbf55": "ok_hi",
    "#33ff66": "green", "#e0243a": "red", "#ff5a6e": "red_hi", "#7a1d28": "red_dim",
    "#2a1418": "red_btn", "#f3c2c8": "red_txt", "#7a5a60": "red_off",
    "#b7d4bf": "fg", "#eafff0": "fg_bright", "#6f8f78": "muted", "#8fb59b": "muted2",
    "#4a5f52": "off_fg", "#3a4a40": "off_fg2", "#ffb000": "amber",
}


_HEX6 = re.compile(r"#[0-9a-fA-F]{6}")


def css_text() -> str:
    """The stylesheet with every original literal replaced by the themed colour.

    Trailing alpha digits (e.g. #10171380) are left in place after the substituted colour.
    """
    css = CSS_FILE.read_text()
    return _HEX6.sub(lambda m: PAL[_LITERALS[m.group(0).lower()]] if m.group(0).lower() in _LITERALS else m.group(0), css)
