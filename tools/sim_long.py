"""Long-horizon balance sim: a daily player over weeks. Usage: python tools/sim_long.py [days] [session_bot_minutes]

The greedy bot in sim.py is ~7x faster than a human, so 18 bot-minutes ~ 2 human hours. Each day: one active
session, then the rest of the day offline (capped, reduced efficiency), on a simulated wall clock so Ages and
Hunts run in real time. Prints a milestone log and a per-day table.
"""
import os
import random
import sys

sys.path.insert(0, ".")
from tools import sim  # noqa: E402
from sanguine.engine.bignum import fmt  # noqa: E402
from sanguine.engine.game import Game  # noqa: E402

DAY = 86400.0


def spend_permanent(g: Game) -> None:
    """Greedy: cheapest Bloodline node, then Lineage perks, then Endless Rites (cheapest first)."""
    sim.buy_tree(g)
    while True:
        opts = [p for p in g.c.perks if g.can_buy_perk(p)]
        if not opts:
            break
        g.buy_perk(min(opts, key=g.perk_cost))
    while True:
        opts = [e for e in g.c.endless if g.can_buy_endless(e)]
        if not opts:
            break
        g.buy_endless(min(opts, key=g.endless_cost))


def slow_chores(g: Game) -> None:
    """What a daily player does on login: claim Ages, start offers, accept Hunts."""
    for i in reversed(range(len(g.s.ages.get("running", [])))):
        g.claim_age(i)
    for i in range(len(g.s.ages.get("offers", []))):
        offers = g.s.ages["offers"]
        if i >= len(offers):
            break
        a = g.age_def(offers[i]["id"])
        pick = next((k for k, c in enumerate(a["choice"]) if c["kind"] == "lineage"), 0)
        g.start_age(i, pick)
    for kind in ("weekly", "daily"):
        g.accept_hunt(kind)
    spend_permanent(g)


def run(days: int = 40, session_min: float = 18.0, seed: int = 1, verbose: bool = True):
    wall = [1_700_000_000.0]
    g = Game(sim.C, rng=random.Random(seed), clock=lambda: wall[0])
    g.s.settings["auto_exit"] = True
    s = g.s
    log = []
    seen = set()
    run_t = 0.0
    last_exits = 0

    def mark(tag, day):
        if tag not in seen:
            seen.add(tag)
            log.append((day, tag))
            if verbose:
                print(f"  day {day:5.1f}: {tag}", flush=True)

    for day in range(days):
        slow_chores(g)
        t = 0.0
        while t < session_min * 60:
            sim.step_bot(g, 2.0)
            wall[0] += 2.0
            t += 2.0
            run_t += 2.0
            d = day + t / (session_min * 60) * (session_min / 60 / 24)
            if s.exits != last_exits:        # includes the Retainer's automatic Torpors
                last_exits = s.exits
                spend_permanent(g)
            if g.ending_ready():
                g.sign_handover(); last_exits = s.exits; spend_permanent(g); run_t = 0; mark("COMPACT", d)
            elif s.exits < 400 and run_t > 8 * 60 and g.exit_award() >= max(10, 0.5 * s.sov_earned):
                g.do_exit(); last_exits = s.exits; spend_permanent(g); run_t = 0
            if not os.environ.get("NO_DYN") and g.can_dynasty() and g.lineage_award() >= 8 and run_t > 8 * 60:
                n = g.do_dynasty(); last_exits = s.exits; spend_permanent(g); run_t = 0
                mark(f"DYNASTY #{s.dynasties} (+{n} Lineage)", d)
            top = max((i for i, v in enumerate(s.ventures) if v.owned), default=-1) + 1
            for tier in (21, 25, 30):
                if top >= tier:
                    mark(f"tier {tier}", d)
        # the rest of the day: offline income at the capped, reduced rate, clock moves on
        away = DAY - t
        for _ in range(int(away // 3600)):
            wall[0] += 3600.0
            g.offline(3600.0)
            g._slow_tick()
        if verbose:
            top = max((i for i, v in enumerate(s.ventures) if v.owned), default=-1) + 1
            print(f"day {day + 1:3d}  exits {s.exits:3d}  tier {top:2d}  compact {int(s.posthuman)}  mach {s.machine_level}  "
                  f"dyn {s.dynasties}  lin {s.lineage_earned:5.0f}  perks {len(s.perks)}  endless {sum(s.endless.values()):3d}  "
                  f"feats {len(s.feats):2d}  ages {s.ages_done:2d}  hunts {s.hunts_done:2d}  sov {fmt(s.sov_earned)}", flush=True)
    return g, log


if __name__ == "__main__":
    run(int(sys.argv[1]) if len(sys.argv) > 1 else 40, float(sys.argv[2]) if len(sys.argv) > 2 else 18.0)
