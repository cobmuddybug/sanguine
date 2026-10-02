"""Modal screens. Everything closes on click, Esc, or Enter."""
from __future__ import annotations

from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Static

from .widgets import AMBER, DIM, ActionButton


class TextModal(ModalScreen[None]):
    BINDINGS = [("escape", "close", "Close"), ("enter", "close", "Close"), ("space", "close", "Close")]

    def __init__(self, title: str, body: Text, button: str = "CLOSE") -> None:
        super().__init__()
        self.title_text, self.body, self.button = title, body, button

    def compose(self) -> ComposeResult:
        with Vertical(id="modal"):
            yield Static(self.title_text, id="modal-title")
            with VerticalScroll(id="modal-body"):
                yield Static(self.body)
            yield ActionButton(Text.assemble((self.button + "\n", "bold"), ("esc / enter", DIM)),
                               action_id="close", id="modal-close")

    def on_action_button_pressed(self, event: ActionButton.Pressed) -> None:
        self.dismiss(None)

    def action_close(self) -> None:
        self.dismiss(None)

    def on_click(self, event: events.Click) -> None:
        # a click on the dim backdrop (outside the dialog) also closes
        if self.get_widget_at(event.screen_x, event.screen_y)[0] is self:
            self.dismiss(None)


class ChoiceModal(ModalScreen[int | None]):
    """A modal with large, separated choice buttons (keys 1-3 select too).

    choices: list of (label, detail Text, enabled). Dismisses with the chosen index,
    or None when closed (only if `closable`).
    """

    BINDINGS = [("1", "pick(0)", "Choice 1"), ("2", "pick(1)", "Choice 2"), ("3", "pick(2)", "Choice 3"),
                ("escape", "close", "Close")]

    def __init__(self, title: str, body: Text, choices: list[tuple[str, Text, bool]], closable: bool = True,
                 close_label: str = "CLOSE") -> None:
        super().__init__()
        self.title_text, self.body, self.choices = title, body, choices
        self.closable, self.close_label = closable, close_label

    def compose(self) -> ComposeResult:
        with Vertical(id="modal", classes="choice"):
            yield Static(self.title_text, id="modal-title")
            with VerticalScroll(id="modal-body"):
                yield Static(self.body)
            for i, (label, detail, ok) in enumerate(self.choices):
                head = Text.assemble((f"[{i + 1}] ", AMBER), (label + "\n", "bold"))
                btn = ActionButton(Text.assemble(head, detail), action_id=f"choice:{i}", classes="choice-btn")
                btn.set_disabled_look(not ok)
                yield btn
            if self.closable:
                yield ActionButton(Text.assemble((self.close_label + "\n", "bold"), ("esc", DIM)),
                                   action_id="close", id="modal-close")

    def on_action_button_pressed(self, event: ActionButton.Pressed) -> None:
        aid = event.button.action_id
        if aid == "close":
            self.dismiss(None)
        elif aid.startswith("choice:"):
            self.action_pick(int(aid.split(":")[1]))

    def action_pick(self, i: int) -> None:
        if i < len(self.choices) and self.choices[i][2]:
            self.dismiss(i)

    def action_close(self) -> None:
        if self.closable:
            self.dismiss(None)


class QuietScreen(ModalScreen[None]):
    """A pause at the end of a chapter. Nearly nothing. It waits, and then it lets you go on."""

    def __init__(self) -> None:
        super().__init__()
        self._ready = False

    def compose(self) -> ComposeResult:
        yield Static("", id="quiet")

    def on_mount(self) -> None:
        self.set_timer(2.5, lambda: self._say("it is fed."))
        self.set_timer(7.0, lambda: self._say("it is fed.\n\nnothing is required of you. yet."))
        self.set_timer(11.0, self._arm)

    def _say(self, text: str) -> None:
        self.query_one("#quiet", Static).update(Text(text, justify="center"))

    def _arm(self) -> None:
        self._ready = True
        self._say("it is fed.\n\nnothing is required of you. yet.\n\n\n· press any key ·")

    def on_key(self, event: events.Key) -> None:
        event.stop()
        if self._ready:
            self.dismiss(None)

    def on_click(self, event: events.Click) -> None:
        if self._ready:
            self.dismiss(None)
