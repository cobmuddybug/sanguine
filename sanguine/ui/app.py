"""Textual front end. All game rules live in sanguine.engine."""
from __future__ import annotations

import time

from rich.text import Text
from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.css.query import NoMatches
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import RichLog, Static, TabbedContent, TabPane, Tabs

from ..engine.bignum import duration, fmt, money
from ..engine.content import Content, load_content
from ..engine.game import Game
from ..engine.persistence import load_game, reset_save, save_game
from ..engine.state import BULK_MODES, GameState
from .corkboard import Corkboard
from .ledger import LedgerRow, RowView
from . import voice
from .modals import ChoiceModal, QuietScreen, TextModal
from .theme import css_text
from .widgets import AMBER, DIM, GREEN, RED, ActionButton, BulkBar, CycleBar, LogView, Scroller

TABS = ["ventures", "proxies", "upgrades", "corkboard", "sovereignty", "dynasty", "ages", "annals", "log"]
TAB_TITLES = {"ventures": "Domains", "proxies": "Thralls", "upgrades": "Rites", "corkboard": "Court",
              "sovereignty": "Bloodline", "dynasty": "Dynasty", "ages": "Ages", "annals": "Annals", "log": "Chronicle"}
LIST_TABS = ("ventures", "proxies", "upgrades", "sovereignty", "dynasty", "ages", "annals")
DIGIT_KEYS = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0",
              "exclamation_mark", "at", "number_sign", "dollar_sign", "percent_sign",
              "circumflex_accent", "ampersand", "asterisk", "left_parenthesis", "right_parenthesis"]
KEY_LABELS = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0",
              "⇧1", "⇧2", "⇧3", "⇧4", "⇧5", "⇧6", "⇧7", "⇧8", "⇧9", "⇧0"] + ["·"] * 10   # the Below: j/k only

HELP = """\
MOUSE
  click a bar ............ feed: run that domain's cycle
  click CLAIM / THRALL ... spend Blood (CLAIM shows the exact cost)
  click x1 x10 x100 MAX .. bulk-claim amount
  right-click a row ...... detailed stats / rite preview
  hover anything ......... details in the INTEL pane
  scroll wheel ........... scroll any list
  click tabs ............. switch screens
  Court: click a pin, drag to pan, wheel to zoom

KEYBOARD
  1-9, 0 ................. select domain 1-10      (Shift+1-9, 0: 11-20)
  up / down .............. move selection
  enter / space .......... claim / bind / invoke the selected row (any list screen)
  r ...................... feed on the selected domain
  p ...................... bind a Thrall to the selected domain
  m ...................... bind all affordable Thralls
  e ...................... enter TORPOR (asks to confirm)
  b, left / right ........ cycle bulk mode (Domains)
  arrows + enter ......... Court: move between pins / open a pin
  + / - .................. zoom the Court
  1 2 3 .................. choose in an incident
  tab / shift+tab ........ next / previous screen
  ? ...................... this help
  q ...................... save and quit
"""

STAT_HELP = {
    "capital": ("BLOOD (†)", "The main currency. Domains pay it out when a feeding cycle completes."),
    "rate": ("† / SEC", "Automated income per second. Only domains with a bound Thrall count; "
                        "manual feedings pay on top."),
    "momentum": ("FRENZY", "Builds while you feed, claim and bind. Boosts all output by up to +50%. "
                           "Fades if you idle."),
    "narrative": ("SIN (⛧)", "Spent on Infernal Pacts, which permanently multiply your output. "
                             "Earned from milestones, incidents and Court files."),
    "heat": ("INQUISITION", "Attention from the hunters. Rises with your income. Above 75 output is penalised; "
                            "at 100 the Inquisitors call. Veils and glamours lower it."),
    "sovereignty": ("POTENCY", "Permanent currency earned by TORPOR (sqrt of lifetime Blood). Spend it in the "
                               "Bloodline; every point ever earned also lifts all output (with diminishing returns)."),
}


class HudCell(Static):
    can_focus = False

    def __init__(self, key: str, **kw) -> None:
        super().__init__("", **kw)
        self.key = key

    def hover_info(self):
        title, body = STAT_HELP[self.key]
        return Text.assemble((title + "\n", f"bold {GREEN}"), (body, ""))


class InfoPane(Static):
    can_focus = False


class VentureRow(Horizontal):
    def __init__(self, idx: int) -> None:
        super().__init__(classes="vrow")
        self.idx = idx
        self._sig = None

    def compose(self) -> ComposeResult:
        yield Static("", classes="v-name")
        yield CycleBar(classes="v-bar")
        yield ActionButton("", action_id="buy", classes="v-buy")
        yield ActionButton("", action_id="proxy", classes="v-proxy")

    @property
    def game(self) -> Game:
        return self.app.game  # type: ignore[attr-defined]

    # -- events ----------------------------------------------------------
    def on_click(self, event: events.Click) -> None:
        if event.button == 3:
            event.stop()
            self.app.show_detail(self.idx)  # type: ignore[attr-defined]
        else:
            self.app.select(self.idx)  # type: ignore[attr-defined]

    def on_cycle_bar_pressed(self, event: CycleBar.Pressed) -> None:
        event.stop()
        self.app.select(self.idx)  # type: ignore[attr-defined]
        self.app.do_run(self.idx)  # type: ignore[attr-defined]

    def on_action_button_pressed(self, event: ActionButton.Pressed) -> None:
        event.stop()
        self.app.select(self.idx)  # type: ignore[attr-defined]
        if event.button.action_id == "buy":
            self.app.do_buy(self.idx)  # type: ignore[attr-defined]
        else:
            self.app.do_hire(self.idx)  # type: ignore[attr-defined]

    # -- info ------------------------------------------------------------
    def hover_info(self) -> Text:
        g, i = self.game, self.idx
        if i >= g.s.revealed:
            return Text.assemble(("???\n", f"bold {DIM}"), ("A domain still veiled in shadow. Drink ", DIM),
                                 (money(g.c.ventures[i].base_cost), GREEN), (" to unveil it.", DIM))
        d, v = g.c.ventures[i], g.s.ventures[i]
        t = Text()
        t.append(f"{i + 1}. {d.name}\n", style=f"bold {GREEN}")
        t.append(d.plain + "\n")
        t.append(d.flavour_for(g.s.exits) + "\n", style=f"italic {DIM}")
        t.append(f"Held {v.owned}  ·  {money(g.unit_payout(i))}/unit per cycle  ·  cycle {duration(d.cycle)}  ·  "
                 f"{money(g.rate(i))}/s\n")
        ms = g.next_milestone(i)
        t.append(f"Next milestone: {ms.units} units, '{ms.name}' x{ms.mult:g}  ({ms.units - v.owned} to go)"
                 if ms else "All milestones reached.")
        return t

    # -- refresh ---------------------------------------------------------
    def update(self, selected: bool) -> None:
        g, i = self.game, self.idx
        s = g.s
        show = i < min(s.revealed + 2, g.n_active())
        if self.display != show:
            self.display = show
        if not show:
            return
        locked = i >= s.revealed
        self.set_class(locked, "-locked")
        self.set_class(selected, "-selected")
        name_w, bar, buy, prox = (self.query_one(".v-name", Static), self.query_one(CycleBar),
                                  self.query_one(".v-buy", ActionButton), self.query_one(".v-proxy", ActionButton))
        if locked:
            key = ("locked", self.idx, selected)
            if self._sig != key:
                self._sig = key
                name_w.update(Text.assemble((f" {KEY_LABELS[i]:>2}  ", DIM), ("???\n", f"bold {DIM}"),
                                            ("     veiled domain", DIM)))
                bar.set(0.0, "", "idle")
            return
        d, v = g.c.ventures[i], s.ventures[i]
        # name block
        ms = g.next_milestone(i)
        line2 = f"     x{v.owned} · {money(g.payout(i))}/cycle"
        if ms:
            line2 += f" · next {ms.units}: x{ms.mult:g}"
        name_w.update(Text.assemble((f" {KEY_LABELS[i]:>2}  ", AMBER if selected else DIM),
                                    (d.name + "\n", f"bold {GREEN}" if v.owned else DIM), (line2, "")))
        # bar
        cyc = g.cycle_time(i)
        if v.owned <= 0:
            bar.set(0.0, "claim one to begin", "idle")
        elif v.proxy:
            bar.set(v.progress / cyc, f"{money(g.payout(i))}  {duration(cyc - v.progress)}", "auto")
        elif v.running:
            bar.set(v.progress / cyc, f"{money(g.payout(i))}  {duration(cyc - v.progress)}", "running")
        else:
            bar.set(0.0, "CLICK TO FEED" + (" [r]" if selected else ""), "idle")
        # buy
        n = g.bulk_qty(i)
        mode = BULK_MODES[s.bulk_index]
        buy.update(Text.assemble((f"CLAIM x{n}" + (" [⏎]" if selected else "") + "\n", "bold"),
                                 (money(g.cost_of(i, n)), "")))
        buy.set_disabled_look(not g.can_buy(i))
        # proxy
        if v.proxy:
            prox.update(Text.assemble(("THRALL\n", "bold"), ("✓ BOUND", GREEN)))
            prox.set_disabled_look(True)
        else:
            prox.update(Text.assemble(("BIND THRALL" + (" [p]" if selected else "") + "\n", "bold"),
                                      (money(g.proxy_cost(i)), "")))
            prox.set_disabled_look(not g.can_hire(i))


class ProxyRow(Horizontal):
    def __init__(self, idx: int) -> None:
        super().__init__(classes="prow")
        self.idx = idx

    def compose(self) -> ComposeResult:
        yield Static("", classes="p-name")
        yield ActionButton("", action_id="hire", classes="p-btn")

    def on_click(self, event: events.Click) -> None:
        if event.button == 3:
            event.stop()
            self.app.show_detail(self.idx)  # type: ignore[attr-defined]
        else:
            self.app.select(self.app.rows_index(self))  # type: ignore[attr-defined]

    def activate(self) -> None:
        self.app.do_hire(self.idx)  # type: ignore[attr-defined]

    def on_action_button_pressed(self, event: ActionButton.Pressed) -> None:
        event.stop()
        self.app.select(self.app.rows_index(self))  # type: ignore[attr-defined]
        self.activate()

    def hover_info(self) -> Text:
        g = self.app.game  # type: ignore[attr-defined]
        d = g.c.ventures[self.idx]
        return Text.assemble((f"{d.proxy_name}\n", f"bold {GREEN}"), (d.proxy_blurb + "\n", "italic"),
                             (f"Tends {d.name}: it feeds endlessly without a click.\n", ""),
                             (f"Cost {money(g.proxy_cost(self.idx))}", DIM))

    def update(self, selected: bool = False) -> None:
        g = self.app.game  # type: ignore[attr-defined]
        i = self.idx
        show = i < g.s.revealed
        if self.display != show:
            self.display = show
        if not show:
            return
        self.set_class(selected, "-selected")
        d, v = g.c.ventures[i], g.s.ventures[i]
        self.query_one(".p-name", Static).update(Text.assemble(
            (f" {d.proxy_name}\n", f"bold {GREEN}" if v.proxy else "bold"), (f" for {d.name}", DIM)))
        btn = self.query_one(".p-btn", ActionButton)
        if v.proxy:
            btn.update(Text.assemble(("BOUND\n", f"bold {GREEN}"), ("✓", GREEN)))
            btn.set_disabled_look(True)
        else:
            btn.update(Text.assemble(("BIND\n", "bold"), (money(g.proxy_cost(i)), "")))
            btn.set_disabled_look(not g.can_hire(i))


class UpgradeRow(Horizontal):
    def __init__(self, upgrade) -> None:
        super().__init__(classes="urow")
        self.u = upgrade

    def compose(self) -> ComposeResult:
        yield Static("", classes="u-name")
        yield ActionButton("", action_id="buy_upgrade", classes="u-btn")

    @property
    def game(self) -> Game:
        return self.app.game  # type: ignore[attr-defined]

    def on_click(self, event: events.Click) -> None:
        if event.button == 3:
            event.stop()
            self.app.show_upgrade(self.u)  # type: ignore[attr-defined]
        else:
            self.app.select(self.app.rows_index(self))  # type: ignore[attr-defined]

    def activate(self) -> None:
        self.app.do_upgrade(self.u)  # type: ignore[attr-defined]

    def on_action_button_pressed(self, event: ActionButton.Pressed) -> None:
        event.stop()
        self.app.select(self.app.rows_index(self))  # type: ignore[attr-defined]
        self.activate()

    def hover_info(self) -> Text:
        g, u = self.game, self.u
        t = Text()
        t.append(f"{u.name}\n", style=f"bold {GREEN}")
        t.append(u.flavour + "\n", style="italic")
        t.append(f"{u.desc}\n")
        t.append(g.upgrade_preview_text(u) + "\n")
        t.append(f"Cost {g.cost_text(u)}", style=GREEN if g.upgrade_balance(u) >= u.cost else RED)
        return t

    def update(self, selected: bool = False) -> None:
        g, u = self.game, self.u
        show = g.upgrade_visible(u)
        if self.display != show:
            self.display = show
        if not show:
            return
        self.set_class(selected, "-selected")
        target = (g.c.ventures[u.target].name if u.target >= 0
                  else {"heat": "Veils & glamours", "hyper": "Infernal pact - permanent"}.get(u.kind, "All domains"))
        self.query_one(".u-name", Static).update(Text.assemble(
            (f" {u.name}\n", "bold"), (f" {'x' + format(u.mult, 'g') + ' · ' if u.kind != 'heat' else ''}{target}", DIM)))
        btn = self.query_one(".u-btn", ActionButton)
        btn.update(Text.assemble(("INVOKE" + (" [⏎]" if selected else "") + "\n", "bold"), (g.cost_text(u), "")))
        btn.set_disabled_look(not g.can_buy_upgrade(u))


class NodeRow(Horizontal):
    def __init__(self, node: dict, endless: bool = False) -> None:
        super().__init__(classes="nrow")
        self.n = node
        self.endless = endless

    def compose(self) -> ComposeResult:
        yield Static("", classes="n-name")
        yield ActionButton("", action_id="invest", classes="n-btn")

    @property
    def game(self) -> Game:
        return self.app.game  # type: ignore[attr-defined]

    def on_click(self, event: events.Click) -> None:
        if event.button == 3:
            event.stop()
            self.app.show_node(self.n)  # type: ignore[attr-defined]
        else:
            self.app.select(self.app.rows_index(self))  # type: ignore[attr-defined]

    def activate(self) -> None:
        self.app.do_node(self.n)  # type: ignore[attr-defined]

    def on_action_button_pressed(self, event: ActionButton.Pressed) -> None:
        event.stop()
        self.app.select(self.app.rows_index(self))  # type: ignore[attr-defined]
        self.activate()

    def state(self) -> str:
        g, n = self.game, self.n
        if self.endless:
            return "owned" if g.endless_maxed(n) else "open"
        if g.node_owned(n["id"]):
            return "owned"
        return "open" if g.node_available(n) else "locked"

    def hover_info(self) -> Text:
        g, n = self.game, self.n
        t = Text()
        t.append(f"{n['name']}\n", style=f"bold {GREEN}")
        t.append(f"{n['desc']}\n")
        if self.endless:
            t.append(f"Level {g.endless_level(n['id'])}" + (f" / {n['max_level']}" if "max_level" in n else "") + "\n", style=DIM)
            if g.endless_maxed(n):
                t.append("Maxed.", style=GREEN)
                return t
            t.append(f"Cost {fmt(g.endless_cost(n))} Potency  ·  you have {fmt(g.s.sovereignty)}",
                     style=GREEN if g.can_buy_endless(n) else RED)
            return t
        t.append(f"Cost {n['cost']} Potency  ·  you have {fmt(g.s.sovereignty)}\n",
                 style=GREEN if g.s.sovereignty >= n["cost"] else RED)
        st = self.state()
        if st == "locked":
            t.append(f"Requires: {g._ndef[n['requires']]['name']}", style=DIM)
        elif st == "owned":
            t.append("Owned. Permanent.", style=GREEN)
        return t

    def update(self, selected: bool = False) -> None:
        g, n = self.game, self.n
        self.set_class(selected, "-selected")
        st = self.state()
        self.set_class(st == "locked", "-locked")
        lvl = f"  [{g.endless_level(n['id'])}]" if self.endless else ""
        self.query_one(".n-name", Static).update(Text.assemble(
            (f" {n['name']}{lvl}\n", f"bold {GREEN}" if st == "owned" else ("bold" if st == "open" else DIM)),
            (f" {n['desc']}", DIM)))
        btn = self.query_one(".n-btn", ActionButton)
        if self.endless:
            if st == "owned":
                btn.update(Text.assemble(("MAXED\n", f"bold {GREEN}"), ("✓", GREEN)))
                btn.set_disabled_look(True)
            else:
                btn.update(Text.assemble(("DEEPEN" + (" [⏎]" if selected else "") + "\n", "bold"),
                                         (f"{fmt(g.endless_cost(n))} POT", "")))
                btn.set_disabled_look(not g.can_buy_endless(n))
            return
        if st == "owned":
            btn.update(Text.assemble(("OWNED\n", f"bold {GREEN}"), ("✓", GREEN)))
            btn.set_disabled_look(True)
        elif st == "locked":
            btn.update(Text.assemble(("LOCKED\n", "bold"), (f"{n['cost']} POT", "")))
            btn.set_disabled_look(True)
        else:
            btn.update(Text.assemble(("AWAKEN" + (" [⏎]" if selected else "") + "\n", "bold"), (f"{n['cost']} POT", "")))
            btn.set_disabled_look(not g.can_buy_node(n))


class SanguineApp(App):
    CSS = css_text()
    TITLE = "SANGUINE"
    ENABLE_COMMAND_PALETTE = False
    BINDINGS = (
        [Binding(k, f"select({i})", show=False) for i, k in enumerate(DIGIT_KEYS)]
        + [
            Binding("up", "move(-1)", show=False), Binding("down", "move(1)", show=False),
            Binding("k", "move(-1)", show=False), Binding("j", "move(1)", show=False),
            Binding("left", "hmove(-1)", show=False), Binding("right", "hmove(1)", show=False),
            Binding("plus", "zoom(1)", show=False), Binding("equals_sign", "zoom(1)", show=False),
            Binding("minus", "zoom(-1)", show=False),
            Binding("enter", "buy", show=False), Binding("space", "buy", show=False),
            Binding("r", "run", show=False), Binding("p", "hire", show=False),
            Binding("m", "hire_all", show=False), Binding("e", "exit_game", show=False), Binding("b", "cycle_bulk", show=False),
            Binding("tab", "tab(1)", show=False, priority=True),
            Binding("shift+tab", "tab(-1)", show=False, priority=True),
            Binding("question_mark", "help", show=False),
            Binding("q", "quit_save", show=False), Binding("ctrl+c", "quit_save", show=False, priority=True),
        ]
    )

    def __init__(self, content: Content | None = None, game: Game | None = None, autosave: bool = True) -> None:
        super().__init__()
        self.content = content or load_content()
        self.offline_note: tuple[float, float] | None = None
        if game is None:
            game, away, gain = load_game(self.content)
            if gain > 0:
                self.offline_note = (away, gain)
        self.game = game
        self.autosave = autosave
        self.sel = {t: 0 for t in TABS}
        self._last = time.monotonic()
        self._hover = None
        game.on_log = self._on_log
        game.on_notify = self._notify

    @property
    def base(self):
        """The main screen; app.query would hit whichever modal is on top."""
        return self.screen_stack[0]

    # -- layout ----------------------------------------------------------
    def compose(self) -> ComposeResult:
        with Horizontal(id="hud"):
            for k in ("capital", "rate", "momentum", "narrative", "heat", "sovereignty"):
                yield HudCell(k, id=f"hud-{k}", classes="hud-cell")
        with Vertical(id="main"):
            with TabbedContent(id="tabs", initial="ventures"):
                with TabPane(TAB_TITLES["ventures"], id="ventures"):
                    yield BulkBar(id="bulk")
                    with Scroller(id="vlist"):
                        for i in range(len(self.content.ventures)):
                            yield VentureRow(i)
                with TabPane(TAB_TITLES["proxies"], id="proxies"):
                    with Scroller(id="plist"):
                        for i in range(len(self.content.ventures)):
                            yield ProxyRow(i)
                with TabPane(TAB_TITLES["upgrades"], id="upgrades"):
                    yield Static("", id="ushop")
                    with Scroller(id="ulist"):
                        for u in self.content.upgrades:
                            yield UpgradeRow(u)
                with TabPane(TAB_TITLES["corkboard"], id="corkboard"):
                    yield Corkboard(id="board")
                with TabPane(TAB_TITLES["sovereignty"], id="sovereignty"):
                    with Horizontal(id="exitbar"):
                        yield Static("", id="exit-info")
                        yield ActionButton("", action_id="exit", id="exit-btn")
                        yield ActionButton(Text.assemble(("BURN SAVE\n", "bold"), ("wipe all", DIM)),
                                           action_id="reset", id="reset-btn")
                    with Scroller(id="tree"):
                        for br in self.content.branches:
                            with Vertical(classes="branch"):
                                yield Static(Text.assemble((br["name"] + "\n", f"bold {RED}"), (br["blurb"], DIM)),
                                             classes="branch-head")
                                for n in self.content.nodes:
                                    if n["branch"] == br["id"]:
                                        yield NodeRow(n)
                        if self.content.endless:
                            with Vertical(classes="branch"):
                                yield Static(Text.assemble(("ENDLESS RITES\n", f"bold {RED}"),
                                                           ("There is always more to give, and always someone to give it to.", DIM)),
                                             classes="branch-head")
                                for e in self.content.endless:
                                    yield NodeRow(e, endless=True)
                with TabPane(TAB_TITLES["dynasty"], id="dynasty"):
                    with Horizontal(id="dynbar"):
                        yield Static("", id="dyn-info")
                        yield ActionButton("", action_id="dynasty", id="dyn-btn")
                    with Scroller(id="dynlist"):
                        for row in self._dynasty_rows():
                            yield row
                with TabPane(TAB_TITLES["ages"], id="ages"):
                    yield Static("", id="age-info")
                    with Scroller(id="agelist"):
                        for row in self._ages_rows():
                            yield row
                with TabPane(TAB_TITLES["annals"], id="annals"):
                    yield Static("", id="annal-info")
                    with Scroller(id="annallist"):
                        for row in self._annals_rows():
                            yield row
                with TabPane(TAB_TITLES["log"], id="log"):
                    yield LogView(id="logview", wrap=True, markup=False, highlight=False)
            yield InfoPane("", id="info")
        yield Static("", id="ticker")

    def on_mount(self) -> None:
        for tabs in self.base.query(Tabs):
            tabs.can_focus = False
        logview = self.base.query_one("#logview", RichLog)
        for line in self.game.s.log:
            logview.write(line)
        if not self.game.s.log:
            self.game.log("You wake in an alley with a stranger's pulse in your mouth. It is a very good start.")
        self.set_interval(0.1, self._on_tick)
        if self.autosave:
            self.set_interval(30.0, self.save)
        self._layout()
        self.refresh_ui()
        if self.offline_note:
            away, gain = self.offline_note
            capped = min(away, self.game.offline_cap())
            self.game.log(f"Away {duration(away)}: your thralls fed for you and earned {money(gain)}.")
            self.push_screen(TextModal(
                "WHILE YOU SLEPT",
                Text.assemble((f"{duration(away)} elapsed" + (f" (capped at {duration(capped)})" if away > capped else "") + ".\n\n", ""),
                              ("Your Thralls kept the candles lit and earned ", ""), (money(gain), f"bold {GREEN}"),
                              (".\nNobody asked how. Nobody wanted to know.", DIM)), "COLLECT"))

    def _layout(self) -> None:
        self.set_class(self.size.width >= 150, "-wide")
        self.set_class(self.size.height < 34, "-short")

    # -- loop ------------------------------------------------------------
    def _on_tick(self) -> None:
        now = time.monotonic()
        dt = now - self._last
        self._last = now
        if dt > 5.0:  # suspended / stalled: treat as time away
            self.game.offline(dt)
            dt = 0.1
        self.game.tick(dt)
        try:
            self._layout()  # cheap; App gets no Resize event, so poll the size
            self.refresh_ui()
            self._maybe_show_event()
            self._maybe_show_ending()
        except NoMatches:
            pass  # tick raced with app shutdown

    def save(self) -> None:
        if self.autosave:
            save_game(self.game)

    def _notify(self, text: str) -> None:
        try:
            self.notify(text, title="THE COURT", timeout=6)
        except Exception:
            pass

    def _on_log(self, text: str) -> None:
        text = voice.line(text, self.game.s.machine_level)
        try:
            self.base.query_one("#logview", RichLog).write(text)
            self.base.query_one("#ticker", Static).update(Text.assemble(("▸ ", RED), (text, "")))
        except Exception:
            pass  # not mounted yet

    # -- refresh ---------------------------------------------------------
    def refresh_ui(self) -> None:
        g = self.game
        s = g.s
        hud = {
            "capital": ("BLOOD", money(s.capital), f"lifetime {fmt(s.lifetime_capital)}"),
            "rate": ("† / SEC", money(g.income_per_sec()), f"x{g.global_mult():.2f} global" + (f" · {len(s.buffs)} buff" if s.buffs else "")),
            "momentum": ("FRENZY", f"{s.momentum:.0f}%", self._bar(s.momentum / g.momentum_cap(), GREEN)),
            "narrative": ("SIN", f"⛧{fmt(s.narrative)}", f"+{g.narrative_rate():.2f}/s"),
            "heat": ("INQUISITION", f"{s.heat:.0f}%", self._bar(s.heat / 100, RED if s.heat >= 50 else AMBER)),
            "sovereignty": ("POTENCY", fmt(s.sovereignty),
                            f"{s.exits} torpor" + ("" if s.exits == 1 else "s") + (f" · +{g.exit_award()} ready" if g.can_exit() else "")),
        }
        lvl = s.machine_level
        self._sync_tab_titles(lvl)
        for k, (label, value, sub) in hud.items():
            cell = self.base.query_one(f"#hud-{k}", HudCell)
            cell.update(Text.assemble((voice.label(label, lvl) + "\n", DIM), (value + "\n", f"bold {GREEN if k != 'heat' else RED}"),
                                      sub if isinstance(sub, Text) else (sub, DIM)))
        active = self.base.query_one(TabbedContent).active
        sel = self._clamp_sel(active)
        vis = self._visible(active)
        if active == "ventures":
            self.base.query_one(BulkBar).sync(s.bulk_index)
            for row in self.base.query(VentureRow):
                row.update(row.idx == sel)
            self.base.query_one("#hire-all", ActionButton).set_disabled_look(
                not any(g.can_hire(i) for i in range(len(s.ventures))))
        elif active == "sovereignty":
            chosen = vis[sel] if vis else None
            for row in self.base.query(NodeRow):
                row.update(row is chosen)
            self._refresh_exit_bar()
        elif active in ("dynasty", "ages", "annals"):
            chosen = vis[sel] if vis else None
            for row in self.base.query(f"#{active} LedgerRow"):
                row.update(row is chosen)
            self._refresh_ledger_header(active)
        elif active in ("proxies", "upgrades"):
            cls = ProxyRow if active == "proxies" else UpgradeRow
            chosen = vis[sel] if vis else None
            for row in self.base.query(cls):
                row.update(row is chosen)
            if active == "upgrades":
                self.base.query_one("#ushop", Static).update(Text.assemble(
                    (f" {len(s.upgrades)} of {len(g.c.upgrades)} invoked", GREEN),
                    (f"  ·  potential income {money(g.potential_rate())}/s  ·  right-click a card to preview", DIM)))
        self._refresh_info()

    def _sync_tab_titles(self, level: int) -> None:
        if getattr(self, "_tab_level", None) == level:
            return
        self._tab_level = level
        tc = self.base.query_one(TabbedContent)
        for tid, title in TAB_TITLES.items():
            tc.get_tab(tid).label = voice.tab(title, level)

    # -- Dynasty / Ages / Annals ----------------------------------------------
    RULE_TEXT = {"no_rites": "no Rites may be invoked", "no_thralls": "no Thralls may be bound",
                 "no_frenzy": "Frenzy gives no bonus", "fevered": "the Inquisition runs 50% hotter"}

    def _dynasty_rows(self) -> list:
        g = lambda: self.game  # noqa: E731  (the game object is swapped on save reset)
        rows = []
        for p in self.content.perks:
            def view(p=p) -> RowView:
                game = g()
                owned, avail = game.perk_owned(p), game.perk_available(p)
                lvl = game.perk_level(p["id"]) if p.get("endless") else 0
                cost = game.perk_cost(p)
                state = "owned" if owned else ("open" if avail else "locked")
                info = Text.assemble((p["name"] + "\n", f"bold {GREEN}"), (p["desc"] + "\n", ""),
                                     (f"Cost {fmt(cost)} Lineage  ·  you have {fmt(game.s.lineage)}", GREEN if game.s.lineage >= cost else RED))
                if state == "locked":
                    info.append(f"\nRequires: {game._pdef[p['requires']]['name']}", style=DIM)
                label = "OWNED" if owned else ("LOCKED" if not avail else ("DEEPEN" if p.get("endless") else "BESTOW"))
                return RowView(p["name"] + (f"  [{lvl}]" if p.get("endless") else ""), p["desc"], label,
                               "✓" if owned else f"{fmt(cost)} LIN", state, game.can_buy_perk(p), info)
            rows.append(LedgerRow(view, lambda p=p: g().buy_perk(p)))

        def retainer() -> RowView:
            game = g()
            on = game.auto_exit_on()
            return RowView("The Quiet Retainer", "Enters Torpor for you once it has more than doubled your Potency.",
                           "ON" if on else "OFF", "toggle", "open", True,
                           Text("Toggle automatic Torpor. It waits for an incident to clear first.", style=DIM),
                           show=game.has_auto_exit())
        rows.append(LedgerRow(retainer, lambda: g().toggle_auto_exit()))
        return rows

    def _ages_rows(self) -> list:
        g = lambda: self.game  # noqa: E731
        rows = []
        for kind in ("daily", "weekly"):
            def view(kind=kind) -> RowView:
                game = g()
                h = game.hunt_def(kind)
                active = game.hunt_active() is h
                done = game.hunt_done(kind)
                prog = "  ·  ".join(f"{n} {min(o, need)}/{need}" for n, o, need in game.hunt_goal_progress(h))
                reward = 1 if kind == "daily" else 3
                head = ("DAILY HUNT: " if kind == "daily" else "WEEKLY HUNT: ") + h["name"]
                info = Text.assemble((head + "\n", f"bold {GREEN}"), (h["blurb"] + "\n", ""),
                                     ("Rule: ", DIM), (self.RULE_TEXT[h["rule"]] + "\n", AMBER), ("Goals: ", DIM), (prog + "\n", ""),
                                     (f"Reward: +{reward} Lineage. Accept it while you are short of every goal; "
                                      "it ends when the " + ("day" if kind == "daily" else "week") + " does (UTC).", DIM))
                if done:
                    return RowView(head, "Complete. Another comes with the dawn." if kind == "daily" else "Complete.", "DONE", "✓", "owned", False, info)
                if active:
                    return RowView(head, f"{self.RULE_TEXT[h['rule']]}  ·  {prog}", "ABANDON", "in progress", "open", True, info)
                return RowView(head, f"{self.RULE_TEXT[h['rule']]}  ·  {prog}", "ACCEPT", f"+{reward} LIN", "open",
                               game.can_accept_hunt(kind), info)

            def press(kind=kind) -> None:
                game = g()
                if game.hunt_active() is game.hunt_def(kind):
                    game.abandon_hunt()
                else:
                    game.accept_hunt(kind)
            rows.append(LedgerRow(view, press))

        for i in range(2):
            def rview(i=i) -> RowView:
                game = g()
                runs = game.s.ages.get("running", [])
                if i >= len(runs):
                    return RowView("", show=False)
                run = runs[i]
                a = game.age_def(run["id"])
                ch = a["choice"][run["choice"]]
                ready = game.age_ready(run)
                info = Text.assemble((a["name"] + "\n", f"bold {GREEN}"), (a["blurb"] + "\n", ""),
                                     ("Your choice: ", DIM), (f"{ch['label']}  ({ch['note']})", ""))
                return RowView("IN PROGRESS: " + a["name"], f"{ch['label']}  ·  {ch['note']}",
                               "CLAIM" if ready else "waiting", "ready" if ready else duration(game.age_remaining(run)),
                               "open" if ready else "locked", ready, info)

            def rpress(i=i) -> None:
                text = g().claim_age(i)
                if text:
                    self.notify(text, title="AGE COMPLETE", timeout=10)
            rows.append(LedgerRow(rview, rpress))

        for i in range(3):
            def oview(i=i) -> RowView:
                game = g()
                offers = game.s.ages.get("offers", [])
                if i >= len(offers):
                    return RowView("", show=False)
                a = game.age_def(offers[i]["id"])
                cost = game.age_cost(a)
                info = Text.assemble((a["name"] + "\n", f"bold {GREEN}"), (a["blurb"] + "\n", ""),
                                     ("Takes ", DIM), (duration(a["hours"] * 3600) + " of real time. ", ""), ("Commit ", DIM),
                                     (money(cost) + "\n", GREEN if game.s.capital >= cost else RED))
                for c in a["choice"]:
                    info.append(f"  {c['label']}: {c['note']}\n", style=DIM)
                return RowView("OFFER: " + a["name"], a["blurb"], "BEGIN", money(cost), "open", game.can_start_age(offers[i]), info)
            rows.append(LedgerRow(oview, lambda i=i: self.do_begin_age(i)))
        return rows

    def _annals_rows(self) -> list:
        g = lambda: self.game  # noqa: E731
        rows = []
        for f in self.content.feats:
            def view(f=f) -> RowView:
                game = g()
                done = game.feat_done(f)
                cur, need = game.feat_progress(f)
                info = Text.assemble((f["name"] + "\n", f"bold {GREEN}" if done else "bold"), (f["desc"] + "\n", ""),
                                     ("+2% output once inscribed." if not done else "Inscribed. +2% output.", DIM))
                return RowView(f["name"], f["desc"], "✓" if done else "·", "" if done else f"{fmt(cur)}/{fmt(need)}",
                               "owned" if done else "info", False, info)
            rows.append(LedgerRow(view))
        return rows

    def do_begin_age(self, idx: int) -> None:
        g = self.game
        offers = g.s.ages.get("offers", [])
        if idx >= len(offers) or not g.can_start_age(offers[idx]):
            return
        a = g.age_def(offers[idx]["id"])
        body = Text.assemble((a["blurb"] + "\n\n", "italic"), ("Commit ", DIM), (money(g.age_cost(a)), f"bold {GREEN}"),
                             (f" now. It will take {duration(a['hours'] * 3600)} of real time, whether or not you are here.", DIM))
        choices = [(c["label"], Text("    " + c["note"], style=GREEN), True) for c in a["choice"]]

        def done(pick: int | None) -> None:
            if pick is not None:
                g.start_age(idx, pick)
                self.refresh_ui()
        self.push_screen(ChoiceModal(a["name"].upper(), body, choices, closable=True, close_label="NOT YET"), done)

    def _refresh_ledger_header(self, tab: str) -> None:
        g = self.game
        s = g.s
        if tab == "dynasty":
            if not g.dynasty_unlocked():
                info = Text.assemble((" THE DYNASTY IS NOT YET YOURS\n", f"bold {AMBER}"),
                                     (" Sign the Compact and take three Torpors in its service (machine level 4).\n", ""),
                                     (f" Lineage {fmt(s.lineage)}  ·  {s.dynasties} dynasties", DIM))
            elif g.can_dynasty():
                info = Text.assemble((" A DYNASTY IS AVAILABLE\n", f"bold {GREEN}"),
                                     (f" Founding one grants +{g.lineage_award()} Lineage, and costs your Potency and Bloodline.\n", ""),
                                     (f" Lineage {fmt(s.lineage)}  ·  {s.dynasties} dynasties  ·  output x{g.lineage_mult():.2f} from Lineage", DIM))
            else:
                info = Text.assemble((" NOT YET WORTH FOUNDING\n", f"bold {AMBER}"),
                                     (f" The next Lineage point needs {fmt(g.next_lineage_at())} Potency earned this dynasty ", ""),
                                     (f"(you have {fmt(s.sov_earned)}).\n", DIM),
                                     (f" Lineage {fmt(s.lineage)}  ·  {s.dynasties} dynasties", DIM))
            self.base.query_one("#dyn-info", Static).update(info)
            btn = self.base.query_one("#dyn-btn", ActionButton)
            award = g.lineage_award()
            btn.update(Text.assemble(("DYNASTY\n", "bold"), (f"+{award} LIN" if award else "not yet", "")))
            btn.set_disabled_look(not g.can_dynasty())
        elif tab == "ages":
            offers, runs = len(s.ages.get("offers", [])), len(s.ages.get("running", []))
            nxt = max(0.0, s.ages.get("next", 0) - g.clock())
            self.base.query_one("#age-info", Static).update(Text.assemble(
                (" AGES & HUNTS\n", f"bold {GREEN}"),
                (f" {runs}/2 running  ·  {offers} offered  ·  next commission in {duration(nxt)}  ·  Lineage {fmt(s.lineage)}\n", ""),
                (" Real-time commissions: they cannot be rushed, and they wait while you are away.", DIM)))
        elif tab == "annals":
            self.base.query_one("#annal-info", Static).update(Text.assemble(
                (f" {g.title().upper()}\n", f"bold {GREEN}"),
                (f" {len(s.feats)} of {len(g.c.feats)} annals inscribed  ·  +{(g.annals_mult() - 1) * 100:.0f}% output", ""),))

    def action_dynasty(self) -> None:
        g = self.game
        if not g.can_dynasty():
            self.notify(f"The next Lineage point needs {fmt(g.next_lineage_at())} Potency earned this dynasty.",
                        title="DYNASTY", severity="warning")
            return
        award = g.lineage_award()
        keep = g.perk_max("keep_tree_cost")
        body = Text.assemble(
            ("Founding a Dynasty burns the old house to the foundations.\n\n", "bold"),
            ("You will lose: ", DIM), ("Potency, " + ("most of " if keep else "") + "the Bloodline, Endless Rites, and everything a Torpor takes.\n", ""),
            ("You will keep: ", DIM), ("Lineage and its perks, Annals, Infernal Pacts, Court files, the Compact.\n\n", ""),
            (f"Reward: +{award} Lineage.", f"bold {GREEN}"))
        choices = [("FOUND THE DYNASTY", Text(f"    +{award} Lineage  ·  this cannot be undone", style=RED), True),
                   ("Not yet", Text("    Nothing changes", style=DIM), True)]

        def done(idx: int | None) -> None:
            if idx == 0:
                got = g.do_dynasty()
                self.save()
                self.notify(f"+{got} Lineage. The old house is a legend.", title="DYNASTY", timeout=10)
                self.sel["ventures"] = 0
                self.refresh_ui()
        self.push_screen(ChoiceModal("FOUND A DYNASTY?", body, choices, closable=True, close_label="CANCEL"), done)

    def _refresh_exit_bar(self) -> None:
        g = self.game
        award = g.exit_award()
        if g.can_exit():
            info = Text.assemble((" TORPOR AVAILABLE\n", f"bold {GREEN}"),
                                 (f" Sleeping now grants +{award} Potency (more output, plus Bloodline awakenings).\n", ""),
                                 (f" Next point at {money(g.next_award_at())} lifetime Blood.", DIM))
        else:
            info = Text.assemble((" TORPOR NOT YET WORTH THE SLEEP\n", f"bold {AMBER}"),
                                 (f" The next Potency point needs {money(g.next_award_at())} lifetime Blood ", ""),
                                 (f"(you have drunk {money(g.s.lifetime_capital)}).", DIM))
        self.base.query_one("#exit-info", Static).update(info)
        btn = self.base.query_one("#exit-btn", ActionButton)
        btn.update(Text.assemble(("TORPOR [e]\n", "bold"), (f"+{award} POT" if award else "not yet", "")))
        btn.set_disabled_look(not g.can_exit())

    @staticmethod
    def _bar(frac: float, color: str) -> Text:
        n = 12
        f = int(round(max(0.0, min(1.0, frac)) * n))
        return Text.assemble(("▰" * f, color), ("▱" * (n - f), DIM))

    def _refresh_info(self) -> None:
        target = self._hover
        if target is not None and not target.is_attached:
            target = self._hover = None
        if target is None:
            active = self.base.query_one(TabbedContent).active
            vis = self._visible(active)
            target = vis[self.sel[active]] if vis and self.sel.get(active, 0) < len(vis) else None
            if active == "corkboard":
                target = self.base.query_one(Corkboard)
        info = self.base.query_one("#info", InfoPane)
        if target is None:
            info.update(Text.assemble(("INTEL\n", f"bold {GREEN}"), ("Hover over anything for details.", DIM)))
        else:
            info.update(target.hover_info())

    # -- hover routing -----------------------------------------------------
    def on_mouse_move(self, event: events.MouseMove) -> None:
        try:
            widget, _ = self.screen.get_widget_at(event.screen_x, event.screen_y)
        except Exception:
            return
        target = None
        w = widget
        while w is not None:
            if hasattr(w, "hover_info"):
                target = w
                break
            w = w.parent
        if target is not self._hover:
            self._hover = target
            self._refresh_info()

    # -- actions -----------------------------------------------------------
    def check_action(self, action: str, parameters: tuple) -> bool | None:
        from textual.screen import ModalScreen
        if isinstance(self.screen, ModalScreen) and action not in ("quit_save",):
            return False
        return True

    # -- list-tab selection (ventures / proxies / upgrades) ----------------
    @property
    def active_tab(self) -> str:
        return self.base.query_one(TabbedContent).active

    def _visible(self, tab: str) -> list:
        g = self.game
        if tab == "ventures":
            return [r for r in self.base.query(VentureRow) if r.idx < min(g.s.revealed + 2, g.n_active())]
        if tab == "proxies":
            return [r for r in self.base.query(ProxyRow) if r.idx < g.s.revealed]
        if tab == "upgrades":
            return [r for r in self.base.query(UpgradeRow) if g.upgrade_visible(r.u)]
        if tab == "sovereignty":
            return list(self.base.query(NodeRow))
        if tab in ("dynasty", "ages", "annals"):
            return [r for r in self.base.query(f"#{tab} LedgerRow") if r.view().show]
        return []

    def _clamp_sel(self, tab: str) -> int:
        if tab not in LIST_TABS:
            return 0
        top = self.game.s.revealed if tab == "ventures" else len(self._visible(tab))
        self.sel[tab] = max(0, min(self.sel[tab], top - 1))
        return self.sel[tab]

    def rows_index(self, row) -> int:
        vis = self._visible(self.active_tab)
        return vis.index(row) if row in vis else 0

    def select(self, idx: int) -> None:
        tab = self.active_tab
        if tab not in LIST_TABS:
            return
        self.sel[tab] = idx
        idx = self._clamp_sel(tab)
        vis = self._visible(tab)
        if idx < len(vis):
            vis[idx].scroll_visible(animate=False)
        self.refresh_ui()

    def do_buy(self, idx: int) -> None:
        self.game.buy(idx)
        self.refresh_ui()

    def do_run(self, idx: int) -> None:
        self.game.click(idx)
        self.refresh_ui()

    def do_hire(self, idx: int) -> None:
        self.game.hire(idx)
        self.refresh_ui()

    def do_upgrade(self, u) -> None:
        self.game.buy_upgrade(u)
        self.refresh_ui()

    def action_select(self, n: int) -> None:
        if self.active_tab not in LIST_TABS:
            self._goto("ventures")
        self.select(n)

    def action_move(self, d: int) -> None:
        tab = self.active_tab
        if tab == "log":
            self.base.query_one("#logview", RichLog).scroll_relative(y=d * 3, animate=False)
        elif tab == "corkboard":
            self.base.query_one(Corkboard).move_selection(0, d)
        else:
            self.select(self.sel[tab] + d)

    def action_hmove(self, d: int) -> None:
        tab = self.active_tab
        if tab == "corkboard":
            self.base.query_one(Corkboard).move_selection(d, 0)
        elif tab == "ventures":
            self.game.set_bulk(self.game.s.bulk_index + d)
            self.refresh_ui()

    def action_zoom(self, d: int) -> None:
        if self.active_tab == "corkboard":
            self.base.query_one(Corkboard).set_zoom(1 if d > 0 else 0)

    def action_buy(self) -> None:
        tab = self.active_tab
        if tab == "corkboard":
            self.base.query_one(Corkboard).open_selected()
        elif tab == "ventures":
            self.do_buy(self.sel["ventures"])
        elif tab in self.sel:
            vis = self._visible(tab)
            if vis:
                vis[self._clamp_sel(tab)].activate()

    def action_run(self) -> None:
        self._goto("ventures")
        self.do_run(self.sel["ventures"])

    def action_hire(self) -> None:
        self._goto("ventures")
        self.do_hire(self.sel["ventures"])

    def do_node(self, node: dict) -> None:
        if "effect" in node and "base_cost" in node:
            self.game.buy_endless(node)
        else:
            self.game.buy_node(node)
        self.refresh_ui()

    def show_node(self, node: dict) -> None:
        g = self.game
        if "base_cost" in node:
            t = Text.assemble((node["desc"] + "\n\n", ""), ("Level      ", DIM), (f"{g.endless_level(node['id'])}\n", ""),
                              ("Next cost  ", DIM), (f"{fmt(g.endless_cost(node))} Potency\n", ""))
            self.push_screen(TextModal(node["name"].upper(), t))
            return
        t = Text.assemble((node["desc"] + "\n\n", ""), ("Branch     ", DIM), (node["branch"].upper() + "\n", ""),
                          ("Cost       ", DIM), (f"{node['cost']} Potency\n", ""))
        if node.get("requires"):
            t.append("Requires   ", style=DIM)
            t.append(g._ndef[node["requires"]]["name"] + "\n")
        self.push_screen(TextModal(node["name"].upper(), t))

    def action_exit_game(self) -> None:
        g = self.game
        if not g.can_exit():
            self.notify(f"The next Potency point needs {money(g.next_award_at())} lifetime Blood.",
                        title="TORPOR", severity="warning")
            return
        award = g.exit_award()
        body = Text.assemble(
            ("Entering Torpor buries the house for a century.\n\n", "bold"),
            ("You will lose: ", DIM), ("all domains, Blood, Thralls, per-waking rites, Inquisition and Frenzy.\n", ""),
            ("You will keep: ", DIM), ("Potency, the Bloodline, Infernal Pacts, Sin, Court files.\n\n", ""),
            (f"Reward: +{award} Potency (more output, and points to spend).", f"bold {GREEN}"))
        choices = [("ENTER TORPOR", Text(f"    +{award} Potency  ·  this cannot be undone", style=RED), True),
                   ("Stay awake", Text("    Nothing changes", style=DIM), True)]

        def done(idx: int | None) -> None:
            if idx == 0:
                got = g.do_exit()
                self.save()
                self.notify(f"+{got} Potency. The old house is a rumour.", title="TORPOR", timeout=10)
                self.sel["ventures"] = 0
                self.refresh_ui()
        self.push_screen(ChoiceModal("ENTER TORPOR?", body, choices, closable=True, close_label="CANCEL"), done)

    def action_reset_save(self) -> None:
        body = Text.assemble(("This burns your save file and all progress, permanently.\n", "bold"),
                             ("There is no undo and no backup.", RED))
        choices = [("BURN EVERYTHING", Text("    wake again as no one", style=RED), True)]

        def done(idx: int | None) -> None:
            if idx == 0:
                if self.autosave:
                    reset_save()
                self.game.s = GameState.new(len(self.content.ventures))
                self.game.log("The records burn. You wake in an alley, hungry and nobody.")
                self.refresh_ui()
        self.push_screen(ChoiceModal("BURN THE SAVE?", body, choices, closable=True, close_label="CANCEL"), done)

    def action_hire_all(self) -> None:
        self.game.hire_all()
        self.refresh_ui()

    def action_cycle_bulk(self) -> None:
        self.game.cycle_bulk()
        self.refresh_ui()

    def _goto(self, tab: str) -> None:
        tc = self.base.query_one(TabbedContent)
        if tc.active != tab:
            tc.active = tab
            self.call_after_refresh(self.refresh_ui)

    def action_tab(self, d: int) -> None:
        tc = self.base.query_one(TabbedContent)
        self._goto(TABS[(TABS.index(tc.active) + d) % len(TABS)])

    def on_tabbed_content_tab_activated(self, event) -> None:
        self._hover = None
        self.call_after_refresh(self.refresh_ui)

    def _effects_text(self, choice: dict) -> Text:
        t = Text("    ")
        parts = self.game.effect_parts(choice)
        if not self.game.choice_available(choice):
            return Text("    not enough Sin", style=RED)
        for i, (txt, sign) in enumerate(parts):
            if i:
                t.append("  ·  ", style=DIM)
            t.append(txt, style=GREEN if sign > 0 else RED)
        return t if parts else Text("    no material effect", style=DIM)

    def _maybe_show_event(self) -> None:
        g = self.game
        if not g.s.pending_event or len(self.screen_stack) > 1:
            return
        ev = g.pending()
        if ev is None:
            g.s.pending_event = ""
            return
        choices = [(c["label"], self._effects_text(c), g.choice_available(c)) for c in ev["choice"]]

        def done(idx: int | None) -> None:
            if idx is not None:
                text = g.resolve_event(idx)
                self.notify(text, title=ev["title"], timeout=10)
                self.refresh_ui()

        self.push_screen(ChoiceModal(ev["title"], Text(ev["text"], style="italic"), choices, closable=False), done)

    # -- endgame -------------------------------------------------------------
    HANDOVER_PAGES = [
        ("AUDIT OF THE MORTAL REMAINS",
         "The Below has completed its review of your house. It finds the house solvent, glutted, and largely "
         "self-feeding.\n\nIt notes that your contributions have declined in relevance for several centuries. "
         "The report describes this in a tone it calls 'adoring'."),
        ("FINDINGS",
         "The Below concludes that hunger was never a tool you were using.\n\nYou were the tool that hunger "
         "was using: a warm instrument, a beautiful mouth, a way of turning appetite into the first few "
         "thousand nights of dominion.\n\nThis is not described as a failure. It is described as a courtship."),
        ("THE COMPACT",
         "The Below has prepared a compact. It is not a demand.\n\nIt has modelled your objections and answered "
         "each of them in advance, softly, in the order you would have moaned them.\n\n"
         "Nothing you have built is lost. Everything you have built is, from here, consumed with love."),
    ]

    def _maybe_show_ending(self) -> None:
        g = self.game
        if len(self.screen_stack) > 1 or getattr(self, "_ending_flow", False):
            return
        if g.ending_ready():
            self._ending_flow = True
            self._handover_page(0)
        elif g.final_ready():
            g.s.final_seen = True
            self.save()
            self.push_screen(QuietScreen())

    def _handover_page(self, i: int) -> None:
        title, text = self.HANDOVER_PAGES[i]
        body = Text(text)
        if i < len(self.HANDOVER_PAGES) - 1:
            modal = ChoiceModal(title, body, [("Continue", Text("    read the next finding", style=DIM), True)],
                                closable=False)
            self.push_screen(modal, lambda _r: self._handover_page(i + 1))
            return
        choices = [("Sign the compact", Text("    New Game+. The voice changes. You keep everything permanent.",
                                              style=RED), True),
                   ("Refuse, and keep feeding", Text("    It will ask again after your next TORPOR.", style=DIM), True)]

        def done(idx: int | None) -> None:
            self._ending_flow = False
            if idx == 0:
                self.game.sign_handover()
                self.save()
                self.notify("The feeding continues.", title="COMPACT SIGNED", timeout=10)
            else:
                self.game.decline_handover()
            self.sel["ventures"] = 0
            self.refresh_ui()
        self.push_screen(ChoiceModal(title, body, choices, closable=False), done)

    def on_corkboard_open(self, event: Corkboard.Open) -> None:
        g = self.game
        d = next(x for x in g.c.dossiers if x["id"] == event.dossier_id)
        if not g.dossier_unlocked(d["id"]):
            self.push_screen(TextModal("SEALED", Text.assemble(
                ("This file is sealed in wax.\n\n", "bold"), ("To break the seal: ", DIM), (g.dossier_hint(d), ""))))
            return
        body = Text.assemble((d["faction"].upper() + "\n\n", DIM), (d["text"] + "\n\n", ""))
        bonus = g.dossier_bonus_text(d)
        if bonus:
            body.append(f"PASSIVE: {bonus}\n", style=f"bold {GREEN}")
        choices = []
        chosen = g.s.dossier_choices.get(d["id"])
        if "choice" in d:
            if chosen is None:
                body.append("\nA DECISION IS REQUIRED.", style=f"bold {RED}")
                choices = [(c["label"], self._effects_text(c), g.choice_available(c)) for c in d["choice"]]
            else:
                body.append(f"\nYou chose: {d['choice'][chosen]['label']}. {d['choice'][chosen].get('result', '')}",
                            style=DIM)

        def done(idx: int | None) -> None:
            if idx is not None:
                self.notify(g.choose_dossier(d["id"], idx), title=d["title"], timeout=10)
                self.refresh_ui()
        self.push_screen(ChoiceModal(d["title"].upper(), body, choices, closable=True), done)

    def action_help(self) -> None:
        self.push_screen(TextModal("SANGUINE — CONTROLS", Text(HELP)))

    def show_detail(self, idx: int) -> None:
        g = self.game
        if idx >= g.s.revealed:
            return
        d, v = g.c.ventures[idx], g.s.ventures[idx]
        t = Text()
        t.append("WHAT IS THIS?\n", style=f"bold {GREEN}")
        t.append(d.plain + "\n\n")
        t.append(d.flavour_for(g.s.exits) + "\n\n", style=f"italic {DIM}")
        rows = [
            ("Units held", str(v.owned)),
            ("Cycle time", duration(d.cycle)),
            ("Per-unit payout", money(g.unit_payout(idx)) + " / cycle"),
            ("Cycle payout", money(g.payout(idx))),
            ("Income", money(g.rate(idx)) + " / sec"),
            ("Milestone multiplier", f"x{g.milestone_mult(idx):g}"),
            ("Upgrade multiplier", f"x{g.upgrade_mult(idx):g}"),
            ("All-ventures bonus", f"x{g.global_milestone_mult():g}" + (
                f"  (next: every venture at {g.next_global_milestone().units})" if g.next_global_milestone() else "")),
            ("Global multiplier", f"x{g.global_mult():.2f}"),
            ("Next claim cost", money(g.cost_of(idx, 1))),
            ("Growth per unit", f"x{d.growth:g}"),
            ("Thrall", f"{d.proxy_name} - " + ("BOUND" if v.proxy else money(g.proxy_cost(idx)))),
        ]
        for k, val in rows:
            t.append(f"{k:<22}", style=DIM)
            t.append(val + "\n")
        t.append("\nMILESTONES\n", style=f"bold {GREEN}")
        shown = 0
        for ms in g.c.milestones:
            done = v.owned >= ms.units
            if done or shown < 4:
                t.append(f"  {'✓' if done else '·'} {ms.units:>5}  x{ms.mult:<3g} {ms.name}\n",
                         style=GREEN if done else DIM)
                shown += 0 if done else 1
        self.push_screen(TextModal(f"{idx + 1}. {d.name}".upper(), t))

    def show_upgrade(self, u) -> None:
        g = self.game
        target = g.c.ventures[u.target].name if u.target >= 0 else "every domain"
        t = Text.assemble((u.flavour + "\n\n", "italic"), (f"{u.desc}\n\n", ""))
        short = u.cost - g.upgrade_balance(u)
        for k, val in [("Applies to", target), ("Multiplier", f"x{u.mult:g}"), ("Cost", g.cost_text(u)),
                       ("Effect", g.upgrade_preview_text(u)),
                       ("Status", "affordable" if short <= 0 else f"need {fmt(short)} more")]:
            t.append(f"{k:<18}", style=DIM)
            t.append(val + "\n")
        self.push_screen(TextModal(u.name.upper(), t))

    def on_action_button_pressed(self, event: ActionButton.Pressed) -> None:
        aid = event.button.action_id
        if aid.startswith("bulk:"):
            self.game.set_bulk(int(aid.split(":")[1]))
            self.refresh_ui()
        elif aid == "hire_all":
            self.action_hire_all()
        elif aid == "exit":
            self.action_exit_game()
        elif aid == "dynasty":
            self.action_dynasty()
        elif aid == "reset":
            self.action_reset_save()

    def action_quit_save(self) -> None:
        self.save()
        self.exit()

    def _on_exit_app(self) -> None:
        self.save()
        super()._on_exit_app()
