"""Slow-clock layer: Ages (long real-time commissions) and Hunts (daily/weekly trials). Wall-clock driven."""
from __future__ import annotations

HOUR = 3600.0
DAY = 86400.0
AGE_OFFER_EVERY = 20 * HOUR     # a new commission arrives this often
AGE_FIRST_OFFER = 2 * HOUR
AGE_OFFER_LIFE = 7 * DAY        # an unclaimed offer lapses
AGE_MAX_OFFERS = 3
AGE_MAX_RUNNING = 2
DAILY_LINEAGE = 1
WEEKLY_LINEAGE = 3
BUFF_CAP_NOTE = "play-time"


def _day(now: float) -> int:
    return int(now // DAY)


def _week(now: float) -> int:
    return (_day(now) + 3) // 7      # weeks roll on Monday UTC (epoch day 0 was a Thursday)


class AgesMixin:
    # ---- ages ----------------------------------------------------------
    def age_def(self, aid: str) -> dict:
        return next(a for a in self.c.ages if a["id"] == aid)

    def age_cost(self, a: dict) -> float:
        basis = max(self.income_per_sec(), 0.1 * self.potential_rate())   # what you actually bank, not what you could
        return max(100.0, a["cost_hours"] * HOUR * basis)

    def age_remaining(self, run: dict) -> float:
        return max(0.0, run["ends"] - self.clock())

    def age_ready(self, run: dict) -> bool:
        return self.clock() >= run["ends"]

    def can_start_age(self, offer: dict) -> bool:
        a = self.age_def(offer["id"])
        return len(self.s.ages["running"]) < AGE_MAX_RUNNING and self.s.capital >= self.age_cost(a)

    def start_age(self, offer_idx: int, choice_idx: int) -> bool:
        ages = self.s.ages
        if not (0 <= offer_idx < len(ages["offers"])):
            return False
        offer = ages["offers"][offer_idx]
        a = self.age_def(offer["id"])
        if not (0 <= choice_idx < len(a["choice"])) or not self.can_start_age(offer):
            return False
        self.s.capital -= self.age_cost(a)
        ages["offers"].pop(offer_idx)
        ages["running"].append({"id": a["id"], "choice": choice_idx, "ends": self.clock() + a["hours"] * HOUR})
        self.log(f"Age begun: '{a['name']}'. It will not be rushed.")
        return True

    def claim_age(self, run_idx: int) -> str:
        ages = self.s.ages
        if not (0 <= run_idx < len(ages["running"])):
            return ""
        run = ages["running"][run_idx]
        if not self.age_ready(run):
            return ""
        a = self.age_def(run["id"])
        ch = a["choice"][run["choice"]]
        ages["running"].pop(run_idx)
        ages["done"] = ages.get("done", 0) + 1
        self.s.ages_done += 1
        text = self._grant(ch, a["name"])
        self.log(f"Age complete: '{a['name']}'. {text}")
        return text

    def _grant(self, ch: dict, name: str) -> str:
        kind, v = ch["kind"], ch["value"]
        if kind == "lineage":
            self.s.lineage += v
            self.s.lineage_earned += v
            return f"+{v:g} Lineage."
        if kind == "legacy":
            self.s.legacy += v
            return f"Legacy +{v * 100:g}% output, permanently."
        if kind == "buff":
            hrs = ch.get("hours", 4)
            self.s.buffs.append({"name": name, "mult": float(v), "left": hrs * HOUR})
            return f"x{v:g} output for {hrs:g} hours of play."
        if kind == "blood":
            gain = v * HOUR * self.potential_rate()
            self._earn(gain)
            return f"{v:g} hours of income, paid in Blood."
        return ""

    def _ages_tick(self) -> None:
        now = self.clock()
        ages = self.s.ages
        if not ages:
            ages.update({"next": now + AGE_FIRST_OFFER, "seq": 0, "offers": [], "running": [], "done": 0})
        ages["offers"] = [o for o in ages["offers"] if o["expires"] > now]
        if now >= ages["next"]:
            if len(ages["offers"]) < AGE_MAX_OFFERS:
                taken = {o["id"] for o in ages["offers"]} | {r["id"] for r in ages["running"]}
                for _ in range(len(self.c.ages)):
                    a = self.c.ages[ages["seq"] % len(self.c.ages)]
                    ages["seq"] += 1
                    if a["id"] not in taken:
                        ages["offers"].append({"id": a["id"], "expires": now + AGE_OFFER_LIFE})
                        self.log(f"A commission arrives: '{a['name']}'.")
                        if self.on_notify:
                            self.on_notify(f"A new Age is offered: {a['name']}")
                        break
            ages["next"] = now + AGE_OFFER_EVERY

    # ---- hunts -----------------------------------------------------------
    def _hunt_state(self) -> dict:
        now = self.clock()
        h = self.s.hunt
        if not h:
            h.update({"day": _day(now), "week": _week(now), "active": "", "daily_done": False, "weekly_done": False})
        if h["day"] != _day(now):
            h["day"] = _day(now)
            h["daily_done"] = False
            if h["active"] == "daily":
                h["active"] = ""
        if h["week"] != _week(now):
            h["week"] = _week(now)
            h["weekly_done"] = False
            if h["active"] == "weekly":
                h["active"] = ""
        return h

    def hunt_def(self, kind: str) -> dict:
        h = self._hunt_state()
        if kind == "daily":
            return self.c.hunts[(h["day"] * 5 + 1) % len(self.c.hunts)]
        return self.c.weeklies[h["week"] % len(self.c.weeklies)]

    def hunt_active(self) -> dict | None:
        h = self._hunt_state()
        return self.hunt_def(h["active"]) if h["active"] else None

    def hunt_rule(self) -> str:
        a = self.hunt_active()
        return a["rule"] if a else ""

    def hunt_goal_progress(self, hdef: dict) -> list[tuple[str, int, int]]:
        out = []
        for g in hdef["goals"]:
            i = g["venture"] - 1
            out.append((self.c.ventures[i].name, self.s.ventures[i].owned, g["units"]))
        return out

    def hunt_goals_met(self, hdef: dict) -> bool:
        return all(owned >= need for _, owned, need in self.hunt_goal_progress(hdef))

    def hunt_done(self, kind: str) -> bool:
        return bool(self._hunt_state()[kind + "_done"])

    def can_accept_hunt(self, kind: str) -> bool:
        h = self._hunt_state()
        if h["active"] or h[kind + "_done"]:
            return False
        # a trial only counts if you are still short of every goal: take Torpor first, then hunt
        return all(owned < need for _, owned, need in self.hunt_goal_progress(self.hunt_def(kind)))

    def accept_hunt(self, kind: str) -> bool:
        if not self.can_accept_hunt(kind):
            return False
        self._hunt_state()["active"] = kind
        self.log(f"Hunt accepted: '{self.hunt_def(kind)['name']}'.")
        return True

    def abandon_hunt(self) -> None:
        self._hunt_state()["active"] = ""

    def _hunts_tick(self) -> None:
        h = self._hunt_state()
        kind = h["active"]
        if not kind:
            return
        d = self.hunt_def(kind)
        if self.hunt_goals_met(d):
            reward = DAILY_LINEAGE if kind == "daily" else WEEKLY_LINEAGE
            self.s.lineage += reward
            self.s.lineage_earned += reward
            self.s.hunts_done += 1
            h[kind + "_done"] = True
            h["active"] = ""
            self.log(f"Hunt complete: '{d['name']}'. +{reward} Lineage.")
            if self.on_notify:
                self.on_notify(f"Hunt complete: {d['name']} (+{reward} Lineage)")
