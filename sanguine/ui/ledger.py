"""Generic list rows for the Dynasty / Ages / Annals tabs. Each row is driven by a `view` callback."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Static

from .widgets import DIM, GREEN, ActionButton


@dataclass
class RowView:
    title: str
    sub: str = ""
    button: str = ""
    sub_button: str = ""
    state: str = "open"            # open | owned | locked | info
    enabled: bool = True
    info: Text = field(default_factory=Text)
    show: bool = True


class LedgerRow(Horizontal):
    """Name + description on the left, one action button on the right."""

    def __init__(self, view: Callable[[], RowView], press: Callable[[], None] | None = None) -> None:
        super().__init__(classes="nrow")
        self.view = view
        self.press = press

    def compose(self) -> ComposeResult:
        yield Static("", classes="n-name")
        yield ActionButton("", action_id="ledger", classes="n-btn")

    @property
    def tab(self) -> str:
        return next(a.id for a in self.ancestors if getattr(a, "id", None) in ("dynasty", "ages", "annals"))

    def on_click(self, event: events.Click) -> None:
        if event.button == 1:
            self.app.select(self.app.rows_index(self))  # type: ignore[attr-defined]

    def on_action_button_pressed(self, event: ActionButton.Pressed) -> None:
        event.stop()
        self.app.select(self.app.rows_index(self))  # type: ignore[attr-defined]
        self.activate()

    def on_resize(self, event: events.Resize) -> None:
        self.update(self.has_class("-selected"))

    def activate(self) -> None:
        if self.press and self.view().enabled:
            self.press()
            self.app.refresh_ui()  # type: ignore[attr-defined]

    def hover_info(self) -> Text:
        return self.view().info

    def update(self, selected: bool = False) -> None:
        v = self.view()
        if self.display != v.show:
            self.display = v.show
        if not v.show:
            return
        self.set_class(selected, "-selected")
        self.set_class(v.state == "locked", "-locked")
        head = f"bold {GREEN}" if v.state == "owned" else ("bold" if v.state != "locked" else DIM)
        room = max(12, self.size.width - 34) if self.size.width else 200   # leave generous room beside the 14-wide button
        sub = v.sub if len(v.sub) <= room else v.sub[: room - 1].rstrip() + "…"
        self.query_one(".n-name", Static).update(Text.assemble((f" {v.title[:room]}\n", head), (f" {sub}", DIM)))
        btn = self.query_one(".n-btn", ActionButton)
        label = v.button + (" [⏎]" if selected and v.enabled and v.state == "open" and v.button else "")
        btn.update(Text.assemble((label + "\n", "bold"), (v.sub_button, "")))
        btn.set_disabled_look(not v.enabled or v.state in ("owned", "info"))
