"""Balance simulator: a greedy 'active player' bot. Usage: python tools/sim.py [minutes] [exits]

Every step the bot clicks idle ventures, resolves events, and buys whatever has the best
payback (cost / gain in potential income). It is deliberately faster than a typical human,
so real first-EXIT time should be longer than what this prints.
"""
import random
import sys

sys.path.insert(0, ".")
from sanguine.engine.bignum import fmt  # noqa: E402
from sanguine.engine.content import load_content  # noqa: E402
from sanguine.engine.game import Game  # noqa: E402

C = load_content()


def best_purchase(g: Game):
    """Best cost/gain purchase. Gain is measured on the affected venture only (cheap)."""
    best = None
    s = g.s
    for i in range(min(s.revealed, len(s.ventures))):
        v = s.ventures[i]
        cost = g.cost_of(i, 1)
        before = g.rate(i)
        v.owned += 1
        gain = g.rate(i) - before
        v.owned -= 1
        if gain > 0 and (best is None or cost / gain < best[0]):
            best = (cost / gain, cost, ("unit", i))
    for u in C.upgrades:
        if u.currency != "capital" or u.kind == "heat" or not g.upgrade_visible(u):
            continue
        if u.kind == "venture":
            i = u.target
            before = g.rate(i)
            s.upgrades.append(u.id)
            gain = g.rate(i) - before
            s.upgrades.pop()
        else:
            now, after = g.upgrade_preview(u)
            gain = after - now
        if gain > 0 and (best is None or u.cost / gain < best[0]):
            best = (u.cost / gain, u.cost, ("upg", u))
    return best


def buy_tree(g: Game) -> None:
    """Greedy: cheapest available node first."""
    while True:
        opts = [n for n in C.nodes if g.can_buy_node(n)]
        if not opts:
            return
        g.buy_node(min(opts, key=lambda n: n["cost"]))


def step_bot(g: Game, step: float) -> None:
    s = g.s
    for i, v in enumerate(s.ventures):
        if v.owned and not v.proxy:
            g.click(i)
    if s.pending_event:
        ev = g.pending()
        for k, ch in enumerate(ev["choice"]):
            if g.choice_available(ch):
                g.resolve_event(k)
                break
    for i in range(len(s.ventures)):
        if g.can_hire(i) and g.proxy_cost(i) < s.capital * 0.5:
            g.hire(i)
    for u in C.upgrades:
        if u.currency == "narrative" and g.can_buy_upgrade(u):
            g.buy_upgrade(u)
    for _ in range(50):
        b = best_purchase(g)
        if not b or b[1] > s.capital:
            break
        kind, obj = b[2]
        if kind == "unit":
            g.buy(obj)
        else:
            g.buy_upgrade(obj)
    g.tick(step)


def run(minutes: float, exits: int = 0, step: float = 2.0, verbose: bool = True, seed: int = 1):
    """Play up to `minutes` per run, EXITing (when award >= max(10, half of all earned)) up to `exits` times."""
    g = Game(C, rng=random.Random(seed))
    t = run_t = 0.0
    next_report = 10.0
    while t < minutes * 60:
        step_bot(g, step)
        t += step
        run_t += step
        s = g.s
        if s.exits < exits and g.exit_award() >= max(10, 0.5 * s.sov_earned) and run_t > 20 * 60:
            award = g.do_exit()
            buy_tree(g)
            if verbose:
                print(f"  EXIT #{s.exits} at {t/60:.0f}m (run lasted {run_t/60:.0f}m): +{award} sov, "
                      f"total {int(s.sov_earned)}, tree {len(s.tree)} nodes")
            run_t = 0.0
            next_report = t / 60 + 10
        if verbose and t / 60 >= next_report:
            top = max((i for i, v in enumerate(s.ventures) if v.owned), default=0) + 1
            print(f"{t/60:5.0f}m  run {fmt(s.run_capital):>8}  rate {fmt(g.potential_rate()):>8}/s  "
                  f"top tier {top:2d}  heat {s.heat:3.0f}  narr {fmt(s.narrative):>6}  award {g.exit_award()}")
            next_report += 10.0
    return g


if __name__ == "__main__":
    run(float(sys.argv[1]) if len(sys.argv) > 1 else 90, int(sys.argv[2]) if len(sys.argv) > 2 else 0)
