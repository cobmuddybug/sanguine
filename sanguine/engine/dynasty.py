"""Dynasty: the second prestige layer. Resets Potency and the Bloodline; awards Lineage, which buys permanent perks."""
from __future__ import annotations

import math

DYN_D0 = 1e12           # Potency earned this Dynasty at which the Lineage ladder starts
DYN_GROWTH = 10.0       # each further Dynasty needs this many times more Potency
LIN_PER_DECADE = 3.0    # Lineage awarded per power of ten of Potency above the threshold (log scale: Potency explodes)
LINEAGE_MULT = 0.10     # +10% output per Lineage ever earned
DYN_MIN_LEVEL = 4       # machine level required (three Torpors after the Compact)


class DynastyMixin:
    # ---- perk effects --------------------------------------------------
    def perk_level(self, pid: str) -> int:
        p = self._pdef[pid]
        if p.get("endless"):
            return int(self.s.perk_levels.get(pid, 0))
        return 1 if pid in self.s.perks else 0

    def perk_values(self, effect: str) -> list[float]:
        out = []
        for p in self.c.perks:
            if p["effect"] == effect:
                n = self.perk_level(p["id"])
                if n:
                    out.append((p["value"], n))
        return [(v, n) for v, n in out]

    def perk_sum(self, effect: str) -> float:
        return sum(v * n for v, n in self.perk_values(effect))

    def perk_max(self, effect: str) -> float:
        return max((v for v, _ in self.perk_values(effect)), default=0.0)

    def perk_mult(self, effect: str) -> float:
        m = 1.0
        for v, n in self.perk_values(effect):
            m *= v ** n
        return m

    def perk_tier_mult(self, i: int) -> float:
        m = 1.0
        for p in self.c.perks:
            if p["effect"] == "tier_mult" and p["tier_from"] - 1 <= i <= p["tier_to"] - 1:
                m *= p["value"] ** self.perk_level(p["id"])
        return m

    def lineage_mult(self) -> float:
        return (1.0 + LINEAGE_MULT * self.s.lineage_earned) * self.perk_mult("all_mult")

    # ---- buying perks ----------------------------------------------------
    def perk_cost(self, p: dict) -> float:
        if p.get("endless"):
            return float(math.ceil(p["cost"] * p["growth"] ** self.perk_level(p["id"])))
        return float(p["cost"])

    def perk_available(self, p: dict) -> bool:
        req = p.get("requires")
        return not req or req in self.s.perks

    def perk_owned(self, p: dict) -> bool:
        return not p.get("endless") and p["id"] in self.s.perks

    def can_buy_perk(self, p: dict) -> bool:
        return (not self.perk_owned(p) and self.perk_available(p) and self.s.lineage >= self.perk_cost(p))

    def buy_perk(self, p: dict) -> bool:
        if not self.can_buy_perk(p):
            return False
        self.s.lineage -= self.perk_cost(p)
        if p.get("endless"):
            self.s.perk_levels[p["id"]] = self.perk_level(p["id"]) + 1
        else:
            self.s.perks.append(p["id"])
        self.log(f"Lineage perk: '{p['name']}'.")
        return True

    def has_auto_exit(self) -> bool:
        return self.perk_sum("auto_exit") > 0

    def auto_exit_on(self) -> bool:
        return self.has_auto_exit() and bool(self.s.settings.get("auto_exit"))

    def toggle_auto_exit(self) -> bool:
        if not self.has_auto_exit():
            return False
        self.s.settings["auto_exit"] = not self.s.settings.get("auto_exit")
        return True

    # ---- the Dynasty itself ------------------------------------------------
    def dynasty_unlocked(self) -> bool:
        return self.s.posthuman and self.s.machine_level >= DYN_MIN_LEVEL

    def dynasty_threshold(self) -> float:
        return DYN_D0 * DYN_GROWTH ** self.s.dynasties

    def lineage_award(self) -> int:
        if not self.dynasty_unlocked():
            return 0
        ratio = self.s.sov_earned / self.dynasty_threshold()
        raw = math.floor(LIN_PER_DECADE * math.log10(ratio)) if ratio >= 1.0 else 0
        return int(max(0, raw) * (1.0 + self.perk_sum("lineage_gain")))

    def next_lineage_at(self) -> float:
        """Potency earned this Dynasty at which the next base Lineage point lands."""
        ratio = self.s.sov_earned / self.dynasty_threshold()
        base = max(0, math.floor(LIN_PER_DECADE * math.log10(ratio))) if ratio >= 1.0 else 0
        return self.dynasty_threshold() * 10.0 ** ((base + 1) / LIN_PER_DECADE)

    def can_dynasty(self) -> bool:
        return self.lineage_award() >= 1

    def do_dynasty(self) -> int:
        award = self.lineage_award()
        if award < 1:
            return 0
        s = self.s
        s.lineage += award
        s.lineage_earned += award
        s.dynasties += 1
        keep = self.perk_max("keep_tree_cost")
        s.tree = [nid for nid in s.tree if self._ndef[nid]["cost"] <= keep]
        s.endless = {}
        s.sovereignty = s.sov_earned = s.sov_raw = 0.0
        s.lifetime_capital = 0.0
        self.do_exit(force=True)       # the run itself resets exactly as a Torpor would
        self.log(f"A new Dynasty is founded. +{award} Lineage. The old house is a rumour, and a very good one.")
        return award
