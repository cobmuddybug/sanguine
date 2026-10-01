"""Reusable mouse-first widgets.

Every interactive element is a widget with a real hit area (>=3 rows for primary
buttons). Hover is CSS `:hover`; details go to the fixed InfoPane via the
`hover_info()` protocol so the app can route hover without floating popups.
"""
from __future__ import annotations

from rich.console import RenderableType
from rich.text import Text
from textual import events
from textual.containers import Horizontal, VerticalScroll
from textual.message import Message
from textual.widget import Widget
from textual.widgets import RichLog, Static

from ..engine.bignum import duration, fmt, money
from ..engine.state import BULK_MODES

from .theme import PAL

GREEN, DIM, RED, AMBER = PAL["green"], PAL["muted"], PAL["red"], PAL["amber"]


class ActionButton(Static):
    """A clickable block. Left-click posts Pressed; other buttons bubble to the parent."""

    can_focus = False

    class Pressed(Message):
        def __init__(self, button: "ActionButton") -> None:
            super().__init__()
            self.button = button

    def __init__(self, label: RenderableType = "", *, action_id: str = "", **kw) -> None:
        super().__init__(label, **kw)
        self.action_id = action_id
        self.disabled_look = False

    def set_disabled_look(self, flag: bool) -> None:
        if flag != self.disabled_look:
            self.disabled_look = flag
            self.set_class(flag, "-off")

    def on_click(self, event: events.Click) -> None:
        if event.button == 1:
            event.stop()
            self.post_message(self.Pressed(self))


class CycleBar(Static):
    """Three-row progress bar. Clicking it starts the venture's cycle."""

    can_focus = False

    class Pressed(Message):
        def __init__(self, bar: "CycleBar") -> None:
            super().__init__()
            self.bar = bar

    def __init__(self, **kw) -> None:
        super().__init__("", **kw)
        self.frac = 0.0
        self.label = ""
        self.state = "idle"  # idle | running | auto

    def set(self, frac: float, label: str, state: str) -> None:
        self.frac, self.label, self.state = frac, label, state
        self.refresh()

    def on_click(self, event: events.Click) -> None:
        if event.button == 1:
            event.stop()
            self.post_message(self.Pressed(self))

    def render(self) -> RenderableType:
        w = max(self.size.width, 1)
        h = max(self.size.height, 1)
        filled = int(round(min(max(self.frac, 0.0), 1.0) * w))
        fill_bg = {"auto": PAL["ok_mid"], "running": PAL["ok_hi"], "idle": PAL["line"]}[self.state]
        empty_bg = PAL["panel2"]
        label = self.label[:w]
        start = (w - len(label)) // 2
        out = Text(no_wrap=True, overflow="crop")
        for row in range(h):
            for x in range(w):
                bg = fill_bg if x < filled else empty_bg
                ch = " "
                if row == h // 2 and start <= x < start + len(label):
                    ch = label[x - start]
                fg = PAL["fg_bright"] if x < filled else DIM
                out.append(ch, style=f"{fg} on {bg}")
            if row < h - 1:
                out.append("\n")
        return out


class BulkBar(Horizontal):
    """Segmented control: [x1] [x10] [x100] [MAX], plus a HIRE-ALL button."""

    class Changed(Message):
        def __init__(self, index: int) -> None:
            super().__init__()
            self.index = index

    def compose(self):
        yield Static("BULK", id="bulk-label")
        for i, m in enumerate(BULK_MODES):
            yield ActionButton(f"x{m}" if m else "MAX", action_id=f"bulk:{i}", classes="seg")
        yield Static("", classes="spacer")
        yield ActionButton(Text.assemble(("BIND ALL THRALLS\n", "bold"), ("key: m", DIM)), action_id="hire_all",
                           id="hire-all")

    def sync(self, active: int) -> None:
        for btn in self.query(".seg"):
            idx = int(btn.action_id.split(":")[1])
            btn.set_class(idx == active, "-active")


class Scroller(VerticalScroll, can_focus=False, can_focus_children=False):
    """Scroll container that never takes focus (a focused widget would force its tab active)."""


class LogView(RichLog, can_focus=False):
    pass
