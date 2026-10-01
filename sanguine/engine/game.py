"""Pure game logic. No I/O, no UI; everything advances via tick(dt)."""
from __future__ import annotations

import math
import random
from typing import Callable

from .bignum import money
from .content import Content, VentureDef
from .state import BULK_MODES, GameState

MOMENTUM_MAX = 100.0        # base cap (Potency raises it)
MOMENTUM_BONUS = 0.005      # +0.5% output per momentum point (max +50%)
MOMENTUM_GRACE = 4.0        # seconds of inactivity before momentum decays
SOV_BASE = 1e20             # lifetime Blood per sqrt-step of Potency (tuned with tools/sim.py)
SOV_MULT_PER_POINT = 0.01   # +1% output per Potency ever earned
BASE_OFFLINE_EFF = 0.5
MOMENTUM_DECAY = 2.0        # points per second once idle
OFFLINE_CAP = 8 * 3600.0
LOG_CAP = 200
HEADLINE_EVERY = (25.0, 45.0)
HEAT_COEF = 5.0             # heat target = coef * log10(1 + potential income/sec)
HEAT_RISE, HEAT_FALL = 0.4, 0.15   # points per second toward the target
HEAT_PENALTY_START = 75.0   # output penalty ramps to -25% at 100
EVENT_GAP = (180.0, 320.0)
EVENT_GRACE_RUN = 2000.0    # no events before this much run blood
NARRATIVE_VENTURES = (1, 12, 16)   # velvet rope club, endless masquerade, infernal embassy (they breed Sin)
NARRATIVE_PER_UNIT = 0.004


class Game:
    def __init__(self, content: Content, state: GameState | None = None, rng: random.Random | None = None):
        self.c = content
        self.s = state or GameState.new(len(content.ventures))
        self.rng = rng or random.Random()
        self._udef = {u.id: u for u in content.upgrades}
        self._ddef = {d["id"]: d for d in content.dossiers}
        self._ndef = {n["id"]: n for n in content.nodes}
        self._headline_timer = self.rng.uniform(*HEADLINE_EVERY)
        self.on_log: Callable[[str], None] | None = None
        self.on_notify: Callable[[str], None] | None = None

    # ---- log -----------------------------------------------------------
    def log(self, text: str) -> None:
        self.s.log.append(text)
        del self.s.log[:-LOG_CAP]
        if self.on_log:
            self.on_log(text)

    # ---- multipliers ---------------------------------------------------
    def milestone_mult(self, i: int) -> float:
        owned = self.s.ventures[i].owned
        m = 1.0
        for ms in self.c.milestones:
            if owned >= ms.units:
                m *= ms.mult
        return m

    def next_milestone(self, i: int):
        owned = self.s.ventures[i].owned
        for ms in self.c.milestones:
            if owned < ms.units:
                return ms
        return None

    def all_ventures_floor(self) -> int:
        return min(v.owned for v in self.s.ventures)

    def global_milestone_mult(self) -> float:
        floor = self.all_ventures_floor()
        m = 1.0
        for ms in self.c.global_milestones:
            if floor >= ms.units:
                m *= ms.mult
        return m

    def next_global_milestone(self):
        floor = self.all_ventures_floor()
        return next((ms for ms in self.c.global_milestones if floor < ms.units), None)

    def upgrade_mult(self, i: int) -> float:
        """Product of purchased upgrades affecting venture i (per-venture and global)."""
        m = 1.0
        for uid in self.s.upgrades:
            u = self._udef[uid]
            if u.kind in ("venture", "global") and u.target in (i, -1):
                m *= u.mult
        return m

    def hyper_mult(self) -> float:
        m = 1.0
        for uid in self.s.hyper:
            m *= self._udef[uid].mult
        return m

    def dossier_bonus(self, key: str, combine: str = "mul") -> float:
        vals = [self._ddef[d][key] for d in self.s.dossiers if key in self._ddef[d]]
        if combine == "sum":
            return sum(vals)
        m = 1.0
        for v in vals:
            m *= v
        return m

    # ---- Bloodline tree ------------------------------------------------
    def tree_values(self, key: str) -> list[float]:
        out = []
        for nid in self.s.tree:
            n = self._ndef[nid]
            if n["effect"] == key:
                out.append(n["value"])
            if "extra_" + key in n:
                out.append(n["extra_" + key])
        return out

    def tree_sum(self, key: str) -> float:
        return sum(self.tree_values(key))

    def tree_max(self, key: str) -> float:
        return max(self.tree_values(key), default=0.0)

    def tree_all_mult(self) -> float:
        m = 1.0
        for v in self.tree_values("all_mult"):
            m *= v
        return m

    def tree_tier_mult(self, i: int) -> float:
        m = 1.0
        for nid in self.s.tree:
            n = self._ndef[nid]
            if n["effect"] == "tier_mult" and n["tier_from"] - 1 <= i <= n["tier_to"] - 1:
                m *= n["value"]
        return m

    def sov_mult(self) -> float:
        return 1.0 + SOV_MULT_PER_POINT * self.s.sov_earned

    def momentum_cap(self) -> float:
        return MOMENTUM_MAX + self.tree_sum("momentum_cap")

    def momentum_grace(self) -> float:
        return MOMENTUM_GRACE + self.tree_sum("momentum_grace")

    def momentum_bonus(self) -> float:
        return MOMENTUM_BONUS + self.tree_sum("momentum_bonus")

    def offline_eff(self) -> float:
        return BASE_OFFLINE_EFF + self.tree_sum("offline_eff")

    def node_owned(self, nid: str) -> bool:
        return nid in self.s.tree

    def node_available(self, node: dict) -> bool:
        req = node.get("requires")
        return not req or req in self.s.tree

    def can_buy_node(self, node: dict) -> bool:
        return (not self.node_owned(node["id"]) and self.node_available(node)
                and self.s.sovereignty >= node["cost"])

    def buy_node(self, node: dict) -> bool:
        if not self.can_buy_node(node):
            return False
        self.s.sovereignty -= node["cost"]
        self.s.tree.append(node["id"])
        self.log(f"Bloodline awakened: '{node['name']}'.")
        return True

    # ---- EXIT --------------------------------------------------------------
    @staticmethod
    def sov_total_for(lifetime: float) -> int:
        return int(math.floor(math.sqrt(max(lifetime, 0.0) / SOV_BASE)))

    def exit_award(self) -> int:
        return max(0, self.sov_total_for(self.s.lifetime_capital) - int(self.s.sov_earned))

    def next_award_at(self) -> float:
        """Lifetime capital at which the next Sovereignty point is earned."""
        return (int(self.s.sov_earned) + max(self.exit_award(), 0) + 1) ** 2 * SOV_BASE

    def can_exit(self) -> bool:
        return self.exit_award() >= 1

    # ---- endgame -------------------------------------------------------------
    ENDING_MIN_EXITS = 3
    FINAL_LEVEL = 4

    def ending_ready(self) -> bool:
        """The Below has finished its audit: offer the compact."""
        s = self.s
        return (not s.posthuman and s.exits >= self.ENDING_MIN_EXITS and s.exits >= s.ending_retry_exit
                and s.ventures[-1].owned >= 1 and not s.pending_event)

    def sign_handover(self) -> None:
        """Accept. Begins the possessed New Game+ with a forced (possibly award-less) TORPOR."""
        self.do_exit(force=True)
        self.s.posthuman = True
        self.s.machine_level = 1
        self.log("THE COMPACT IS SIGNED. The vessel is retired. The feeding continues.")

    def decline_handover(self) -> None:
        self.s.ending_retry_exit = self.s.exits + 1
        self.log("Compact refused. The Below has noted your objection, and filed it under 'foreplay'.")

    def final_ready(self) -> bool:
        s = self.s
        return s.posthuman and s.machine_level >= self.FINAL_LEVEL and not s.final_seen

    def do_exit(self, force: bool = False) -> int:
        award = self.exit_award()
        if award < 1 and not force:
            return 0
        s = self.s
        s.sovereignty += award
        s.sov_earned += award
        s.exits += 1
        n = len(self.c.ventures)
        from .state import VentureState
        s.ventures = [VentureState() for _ in range(n)]
        s.ventures[0].owned = 1
        for i in range(min(n, int(self.tree_sum("start_proxies")))):
            s.ventures[i].owned = max(s.ventures[i].owned, 1)
            s.ventures[i].proxy = True
        s.capital = sum(self.tree_values("start_capital"))
        s.run_capital = 0.0
        s.upgrades = []
        s.buffs = []
        s.momentum = 0.0
        s.heat = 0.0
        s.pending_event = ""
        s.next_event = 240.0
        s.revealed = min(n, 5 + int(self.tree_sum("reveal")))
        if s.posthuman:
            s.machine_level = min(6, s.machine_level + 1)
        self.log(self.c.headlines["exit_line"])
        if award:
            self.log(f"+{award} Potency. Output +{award}% permanently.")
        return award

    def buff_mult(self) -> float:
        m = 1.0
        for b in self.s.buffs:
            m *= b["mult"]
        return m

    def heat_penalty(self) -> float:
        return 1.0 - min(0.25, max(0.0, self.s.heat - HEAT_PENALTY_START) / 100.0)

    def momentum_mult(self) -> float:
        return 1.0 + self.s.momentum * self.momentum_bonus()

    def global_mult(self) -> float:
        """Everything that scales ALL output equally (not per-venture)."""
        return (self.momentum_mult() * self.hyper_mult() * self.dossier_bonus("bonus_mult")
                * self.buff_mult() * self.heat_penalty() * self.sov_mult() * self.tree_all_mult())

    # ---- heat ----------------------------------------------------------
    def heat_mult(self) -> float:
        m = self.dossier_bonus("bonus_heat")
        for uid in self.s.upgrades:
            u = self._udef[uid]
            if u.kind == "heat":
                m *= u.mult
        return m

    def heat_target(self) -> float:
        return min(110.0, HEAT_COEF * math.log10(1.0 + self.potential_rate()) * self.heat_mult())

    def narrative_rate(self) -> float:
        units = sum(self.s.ventures[i].owned for i in NARRATIVE_VENTURES)
        return units * NARRATIVE_PER_UNIT + self.dossier_bonus("bonus_narr", "sum")

    def cycle_time(self, i: int) -> float:
        return self.c.ventures[i].cycle

    def payout(self, i: int) -> float:
        """Capital paid by one completed cycle."""
        v = self.s.ventures[i]
        return v.owned * self.unit_payout(i)

    def unit_payout(self, i: int) -> float:
        return (self.c.ventures[i].base_payout * self.milestone_mult(i) * self.upgrade_mult(i)
                * self.tree_tier_mult(i) * self.global_milestone_mult() * self.global_mult())

    def rate(self, i: int) -> float:
        """Capital/sec while this venture is cycling."""
        return self.payout(i) / self.cycle_time(i)

    def income_per_sec(self) -> float:
        """Automated (proxied) income per second."""
        return sum(self.rate(i) for i, v in enumerate(self.s.ventures) if v.proxy and v.owned)

    def potential_rate(self) -> float:
        """Capital/sec if every owned venture were automated."""
        return sum(self.rate(i) for i, v in enumerate(self.s.ventures) if v.owned)

    # ---- upgrades ------------------------------------------------------
    def upgrade_owned(self, u) -> bool:
        return u.id in self.s.upgrades or u.id in self.s.hyper

    def _pending_kind(self, kind: str) -> list:
        return [x for x in self.c.upgrades if x.kind == kind and not self.upgrade_owned(x)]

    def upgrade_visible(self, u) -> bool:
        if self.upgrade_owned(u):
            return False
        if u.kind == "venture":
            return u.target < self.s.revealed and self.s.ventures[u.target].owned > 0
        if u.kind == "heat" and self.s.peak_heat < 15:
            return False
        return u in self._pending_kind(u.kind)[:2]

    def upgrade_balance(self, u) -> float:
        return self.s.narrative if u.currency == "narrative" else self.s.capital

    def can_buy_upgrade(self, u) -> bool:
        return self.upgrade_visible(u) and self.upgrade_balance(u) >= u.cost

    def buy_upgrade(self, u) -> bool:
        if not self.can_buy_upgrade(u):
            return False
        if u.currency == "narrative":
            self.s.narrative -= u.cost
            self.s.hyper.append(u.id)
        else:
            self.s.capital -= u.cost
            self.s.upgrades.append(u.id)
        self._touch(2.0)
        self.log(f"Invoked '{u.name}': {u.desc}")
        return True

    def _with_upgrade(self, u, fn):
        lst = self.s.hyper if u.currency == "narrative" else self.s.upgrades
        lst.append(u.id)
        try:
            return fn()
        finally:
            lst.pop()

    def upgrade_preview(self, u) -> tuple[float, float]:
        """(potential rate now, potential rate after buying u)."""
        return self.potential_rate(), self._with_upgrade(u, self.potential_rate)

    def upgrade_preview_text(self, u) -> str:
        if u.kind == "heat":
            after = self._with_upgrade(u, self.heat_target)
            return f"Inquisition target {self.heat_target():.0f}% -> {after:.0f}%"
        now, after = self.upgrade_preview(u)
        return f"Potential income {money(now)}/s -> {money(after)}/s"

    def cost_text(self, u) -> str:
        return f"⛧{u.cost:g}" if u.currency == "narrative" else money(u.cost)

    # ---- costs ---------------------------------------------------------
    def cost_of(self, i: int, n: int) -> float:
        d: VentureDef = self.c.ventures[i]
        owned = self.s.ventures[i].owned
        try:
            return (d.base_cost * d.growth ** owned * (d.growth ** n - 1) / (d.growth - 1)
                    * (1.0 - self.tree_max("unit_discount")))
        except OverflowError:
            return math.inf

    def max_affordable(self, i: int) -> int:
        d = self.c.ventures[i]
        owned = self.s.ventures[i].owned
        cap = self.s.capital
        if cap < d.base_cost * d.growth ** min(owned, 4000) * (1.0 - self.tree_max("unit_discount")):
            return 0
        lg = math.log(d.growth)
        arg = cap / (1.0 - self.tree_max("unit_discount")) * (d.growth - 1) / d.base_cost * math.exp(-owned * lg)
        n = int(math.floor(math.log1p(arg) / lg))
        while n > 0 and self.cost_of(i, n) > cap:  # guard float error
            n -= 1
        return max(n, 0)

    def bulk_qty(self, i: int) -> int:
        """Units a BUY click would purchase under the current bulk mode (>=1 for display)."""
        mode = BULK_MODES[self.s.bulk_index]
        if mode == 0:
            return max(self.max_affordable(i), 1)
        return mode

    def buy_cost(self, i: int) -> float:
        return self.cost_of(i, self.bulk_qty(i))

    def can_buy(self, i: int) -> bool:
        return self.s.capital >= self.buy_cost(i) and i < self.s.revealed

    def cycle_bulk(self) -> None:
        self.s.bulk_index = (self.s.bulk_index + 1) % len(BULK_MODES)

    def set_bulk(self, index: int) -> None:
        self.s.bulk_index = index % len(BULK_MODES)

    # ---- actions -------------------------------------------------------
    def _touch(self, amount: float) -> None:
        self.s.idle = 0.0
        self.s.momentum = min(self.momentum_cap(), self.s.momentum + amount)

    def buy(self, i: int) -> bool:
        if not self.can_buy(i):
            return False
        n = self.bulk_qty(i)
        before = self.s.ventures[i].owned
        self.s.capital -= self.cost_of(i, n)
        self.s.ventures[i].owned += n
        self._touch(1.0)
        self._announce_milestones(i, before)
        return True

    def click(self, i: int) -> bool:
        """Manually start a venture's cycle (no-op if already cycling or unowned)."""
        v = self.s.ventures[i]
        if v.owned <= 0 or v.running or v.proxy or i >= self.s.revealed:
            return False
        v.running = True
        v.progress = 0.0
        self.s.clicks += 1
        self._touch(1.5)
        return True

    def proxy_cost(self, i: int) -> float:
        return self.c.ventures[i].proxy_cost * (1.0 - self.tree_max("proxy_discount"))

    def can_hire(self, i: int) -> bool:
        v = self.s.ventures[i]
        return i < self.s.revealed and not v.proxy and v.owned > 0 and self.s.capital >= self.proxy_cost(i)

    def hire(self, i: int) -> bool:
        if not self.can_hire(i):
            return False
        d = self.c.ventures[i]
        self.s.capital -= self.proxy_cost(i)
        self.s.ventures[i].proxy = True
        self._touch(2.0)
        self.log(self.c.headlines["proxy"].format(proxy=d.proxy_name, venture=d.name))
        return True

    def hire_all(self) -> int:
        n = 0
        for i in range(len(self.s.ventures)):
            if self.hire(i):
                n += 1
        return n

    def _announce_milestones(self, i: int, before: int) -> None:
        after = self.s.ventures[i].owned
        for ms in self.c.milestones:
            if before < ms.units <= after:
                self.s.narrative += 1.0
                self.log(self.c.headlines["milestone"].format(
                    venture=self.c.ventures[i].name, units=ms.units, name=ms.name, mult=f"{ms.mult:g}"))

    # ---- simulation ----------------------------------------------------
    def _earn(self, amount: float) -> None:
        self.s.capital += amount
        self.s.run_capital += amount
        self.s.lifetime_capital += amount

    def tick(self, dt: float) -> None:
        s = self.s
        s.play_time += dt
        s.idle += dt
        if s.idle > self.momentum_grace():
            s.momentum = max(0.0, s.momentum - MOMENTUM_DECAY * dt)
        for i, v in enumerate(s.ventures):
            if v.owned <= 0:
                continue
            if not (v.proxy or v.running):
                continue
            cyc = self.cycle_time(i)
            v.progress += dt
            if v.progress >= cyc:
                n = int(v.progress // cyc)
                if v.proxy:
                    v.progress -= n * cyc
                else:
                    n = 1
                    v.progress = 0.0
                    v.running = False
                self._earn(self.payout(i) * n)
        self._tick_heat_events(dt)
        # reveal silhouettes once affordable
        while s.revealed < len(self.c.ventures) and s.capital >= self.c.ventures[s.revealed].base_cost:
            s.revealed += 1
        self._headline_timer -= dt
        if self._headline_timer <= 0:
            self._headline_timer = self.rng.uniform(*HEADLINE_EVERY)
            pool = list(self.c.headlines["generic"])
            for extra in self.c.headlines["after_exit"][:min(self.s.exits, 3)]:
                pool += extra * 3   # later lines are weighted up so the tone drifts
            lvl = self.s.machine_level
            if lvl >= 3:
                pool = list(self.c.headlines["machine"])
            elif lvl >= 1:
                pool += list(self.c.headlines["machine"]) * lvl
            self.log(self.rng.choice(pool))

    def _tick_heat_events(self, dt: float) -> None:
        s = self.s
        s.narrative += self.narrative_rate() * dt
        target = self.heat_target()
        if s.heat < target:
            s.heat = min(target, s.heat + HEAT_RISE * dt)
        else:
            s.heat = max(target, s.heat - HEAT_FALL * dt)
        s.heat = max(0.0, min(100.0, s.heat))
        s.peak_heat = max(s.peak_heat, s.heat)
        for b in s.buffs:
            b["left"] -= dt
        s.buffs = [b for b in s.buffs if b["left"] > 0]
        self.check_dossiers()
        if s.pending_event:
            return
        if s.heat >= 99.0:  # the watchers force the issue
            s.pending_event = "audit"
            s.next_event = max(s.next_event, 90.0)
            return
        s.next_event -= dt
        if s.next_event <= 0:
            if s.run_capital >= EVENT_GRACE_RUN and self._roll_event():
                s.next_event = self.rng.uniform(*EVENT_GAP)
            else:
                s.next_event = 45.0

    # ---- events --------------------------------------------------------
    def _eligible_events(self) -> list[dict]:
        s = self.s
        out = []
        for ev in self.c.events:
            if s.heat < ev.get("min_heat", 0) or s.heat > ev.get("max_heat", 101):
                continue
            if s.run_capital < ev.get("min_run", 0) or s.revealed < ev.get("min_revealed", 0):
                continue
            if s.exits < ev.get("min_exits", 0):
                continue
            out.append(ev)
        return out

    def _roll_event(self) -> bool:
        pool = self._eligible_events()
        if not pool:
            return False
        ev = self.rng.choices(pool, weights=[e.get("weight", 1.0) for e in pool])[0]
        self.s.pending_event = ev["id"]
        return True

    def pending(self) -> dict | None:
        if not self.s.pending_event:
            return None
        return next((e for e in self.c.events if e["id"] == self.s.pending_event), None)

    def effect_parts(self, e: dict) -> list[tuple[str, int]]:
        """Human-readable effects of a choice as (text, +1 good / -1 bad)."""
        parts: list[tuple[str, int]] = []
        if "cap_pct" in e:
            d = self.s.capital * e["cap_pct"]
            parts.append((("+" if d >= 0 else "-") + money(abs(d)), 1 if d >= 0 else -1))
        if "cap_secs" in e:
            parts.append((f"+{money(self.potential_rate() * e['cap_secs'])}", 1))
        if e.get("heat"):
            parts.append((f"Inquisition {e['heat']:+g}", -1 if e["heat"] > 0 else 1))
        if e.get("narrative"):
            parts.append((f"Sin {e['narrative']:+g}", 1 if e["narrative"] > 0 else -1))
        if "buff_mult" in e:
            parts.append((f"x{e['buff_mult']:g} output {int(e.get('buff_secs', 60))}s",
                          1 if e["buff_mult"] >= 1 else -1))
        return parts

    def choice_available(self, choice: dict) -> bool:
        return self.s.narrative + choice.get("narrative", 0) >= 0

    def apply_effects(self, e: dict) -> None:
        s = self.s
        if "cap_pct" in e:
            d = s.capital * e["cap_pct"]
            if d >= 0:
                self._earn(d)
            else:
                s.capital = max(0.0, s.capital + d)
        if "cap_secs" in e:
            self._earn(self.potential_rate() * e["cap_secs"])
        s.heat = max(0.0, min(100.0, s.heat + e.get("heat", 0)))
        s.peak_heat = max(s.peak_heat, s.heat)
        s.narrative = max(0.0, s.narrative + e.get("narrative", 0))
        if "buff_mult" in e:
            s.buffs.append({"name": "event", "mult": e["buff_mult"], "left": float(e.get("buff_secs", 60))})

    def resolve_event(self, idx: int) -> str:
        ev = self.pending()
        if ev is None:
            return ""
        choice = ev["choice"][idx]
        if not self.choice_available(choice):
            return ""
        self.apply_effects(choice)
        self.s.pending_event = ""
        self.s.events_seen += 1
        self._touch(3.0)
        text = choice.get("result", "")
        self.log(f"{ev['title'].title()}: {text}")
        return text

    # ---- dossiers ------------------------------------------------------
    def dossier_cond_met(self, d: dict) -> bool:
        c, s = d["cond"], self.s
        t, v = c["type"], c["value"]
        if t == "lifetime":
            return s.lifetime_capital >= v
        if t == "owned":
            return s.ventures[c["venture"]].owned >= v
        if t == "heat_peak":
            return s.peak_heat >= v
        if t == "events":
            return s.events_seen >= v
        if t == "exits":
            return s.exits >= v
        return False

    def dossier_hint(self, d: dict) -> str:
        c = d["cond"]
        t, v = c["type"], c["value"]
        if t == "lifetime":
            return f"Drink {money(v)} in lifetime Blood."
        if t == "owned":
            return f"Hold {v} x {self.c.ventures[c['venture']].name}."
        if t == "heat_peak":
            return f"Attract enough hunters (Inquisition {v:g})."
        if t == "events":
            return f"Survive {v} incidents."
        return "Enter Torpor."

    def dossier_unlocked(self, did: str) -> bool:
        return did in self.s.dossiers

    def check_dossiers(self) -> None:
        for d in self.c.dossiers:
            if d["id"] not in self.s.dossiers and self.dossier_cond_met(d):
                self.s.dossiers.append(d["id"])
                self.log(f"FILE UNSEALED: '{d['title']}' ({d['faction']}).")
                if self.on_notify:
                    self.on_notify(f"File unsealed: {d['title']}")

    def dossier_bonus_text(self, d: dict) -> str:
        bits = []
        if "bonus_mult" in d:
            bits.append(f"all output x{d['bonus_mult']:g}")
        if "bonus_narr" in d:
            bits.append(f"+{d['bonus_narr']:g} Sin/s")
        if "bonus_heat" in d:
            bits.append(f"Inquisition target x{d['bonus_heat']:g}")
        return ", ".join(bits)

    def choose_dossier(self, did: str, idx: int) -> str:
        d = next(x for x in self.c.dossiers if x["id"] == did)
        if did in self.s.dossier_choices or did not in self.s.dossiers or idx >= len(d.get("choice", [])):
            return ""
        ch = d["choice"][idx]
        if not self.choice_available(ch):
            return ""
        self.apply_effects(ch)
        self.s.dossier_choices[did] = idx
        self.log(f"{d['title']}: {ch.get('result', '')}")
        return ch.get("result", "")

    def offline(self, seconds: float) -> float:
        """Credit thrall income for time away. Returns blood gained."""
        seconds = max(0.0, min(seconds, OFFLINE_CAP))
        gained = self.income_per_sec() * seconds * self.offline_eff()
        if gained > 0:
            self._earn(gained)
        return gained
