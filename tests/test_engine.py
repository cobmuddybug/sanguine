import math
import random
import tempfile
import time
import unittest
from pathlib import Path

from sanguine.engine.bignum import fmt
from sanguine.engine.content import load_content
from sanguine.engine.game import Game
from sanguine.engine.persistence import load_game, save_game

C = load_content()


def fresh() -> Game:
    return Game(C, rng=random.Random(1))


class Bignum(unittest.TestCase):
    def test_fmt(self):
        self.assertEqual(fmt(0), "0")
        self.assertEqual(fmt(999), "999")
        self.assertEqual(fmt(1500), "1.50K")
        self.assertEqual(fmt(999_999), "1.00M")
        self.assertEqual(fmt(2.5e12), "2.50T")
        self.assertEqual(fmt(1e70), "1.00e70")


class Economy(unittest.TestCase):
    def test_twenty_ventures(self):
        self.assertEqual(len(C.ventures), 20)
        self.assertTrue(all(len(v.flavour) == 3 for v in C.ventures))

    def test_bulk_cost_matches_repeated_buys(self):
        g = fresh()
        g.s.capital = 1e6
        expected = 0.0
        for _ in range(10):
            expected += g.cost_of(0, 1)
            g.s.ventures[0].owned += 1
        g.s.ventures[0].owned = 1
        self.assertAlmostEqual(g.cost_of(0, 10), expected, places=6)

    def test_max_affordable_is_tight(self):
        g = fresh()
        for cap in (10, 500, 1e4, 3.3e7):
            g.s.capital = cap
            n = g.max_affordable(0)
            self.assertLessEqual(g.cost_of(0, n), cap)
            self.assertGreater(g.cost_of(0, n + 1), cap)

    def test_click_pays_once(self):
        g = fresh()
        self.assertTrue(g.click(0))
        self.assertFalse(g.click(0))  # already running
        g.tick(1.05)
        self.assertGreater(g.s.capital, 0.3)
        self.assertFalse(g.s.ventures[0].running)

    def test_proxy_automates_and_catches_up_multiple_cycles(self):
        g = fresh()
        g.s.capital = 1000
        self.assertTrue(g.hire(0))
        g.s.momentum = 0
        g.tick(3.0)
        self.assertGreater(g.s.capital, 2.9 * g.unit_payout(0))

    def test_milestone_multiplier(self):
        g = fresh()
        g.s.ventures[0].owned = 25
        self.assertEqual(g.milestone_mult(0), 2.0)
        g.s.ventures[0].owned = 100
        self.assertEqual(g.milestone_mult(0), 8.0)

    def test_silhouettes_reveal_when_affordable(self):
        g = fresh()
        self.assertEqual(g.s.revealed, 5)
        g.s.capital = C.ventures[5].base_cost
        g.tick(0.1)
        self.assertEqual(g.s.revealed, 6)
        self.assertFalse(g.can_buy(10))

    def test_momentum_decays_when_idle(self):
        g = fresh()
        g.s.momentum = 50
        g.tick(10)
        self.assertLess(g.s.momentum, 50)

    def test_offline_cap(self):
        g = fresh()
        g.s.capital = 1e3
        g.hire(0)
        g.s.capital = 0
        gain = g.offline(100 * 3600)
        self.assertAlmostEqual(gain, g.income_per_sec() * 8 * 3600 * g.offline_eff())


class Upgrades(unittest.TestCase):
    def test_venture_upgrade_multiplies_only_its_target(self):
        g = fresh()
        g.s.ventures[1].owned = 1
        base0, base1 = g.unit_payout(0), g.unit_payout(1)
        u = next(x for x in C.upgrades if x.kind == "venture" and x.target == 0)
        g.s.capital = u.cost
        self.assertTrue(g.buy_upgrade(u))
        self.assertAlmostEqual(g.unit_payout(0) / base0, u.mult, places=1)  # momentum drifts slightly
        self.assertAlmostEqual(g.unit_payout(1) / base1, 1.0, places=1)
        self.assertFalse(g.buy_upgrade(u))  # can't buy twice

    def test_global_upgrade_and_visibility(self):
        g = fresh()
        globals_ = [u for u in C.upgrades if u.kind == "global"]
        self.assertEqual(sum(g.upgrade_visible(u) for u in globals_), 2)
        g.s.capital = globals_[0].cost
        g.buy_upgrade(globals_[0])
        self.assertTrue(g.upgrade_visible(globals_[2]))
        self.assertAlmostEqual(g.upgrade_mult(5), globals_[0].mult)

    def test_all_ventures_milestone(self):
        g = fresh()
        self.assertEqual(g.global_milestone_mult(), 1.0)
        for v in g.s.ventures:
            v.owned = 25
        self.assertEqual(g.global_milestone_mult(), 2.0)
        self.assertEqual(g.next_global_milestone().units, 50)

    def test_preview_does_not_mutate(self):
        g = fresh()
        u = C.upgrades[0]
        now, after = g.upgrade_preview(u)
        self.assertEqual(g.s.upgrades, [])
        self.assertGreaterEqual(after, now)


class HeatEventsDossiers(unittest.TestCase):
    def test_heat_rises_with_income_and_launder_lowers_target(self):
        g = fresh()
        g.s.ventures[5].owned = 50
        g.s.ventures[5].proxy = True
        g.s.next_event = 1e9
        t0 = g.heat_target()
        self.assertGreater(t0, 10)
        for _ in range(600):
            g.tick(0.1)
        self.assertGreater(g.s.heat, 5)
        u = next(x for x in C.upgrades if x.kind == "heat")
        g.s.peak_heat = 20
        g.s.capital = u.cost
        self.assertTrue(g.buy_upgrade(u))
        self.assertAlmostEqual(g.heat_target(), t0 * u.mult, delta=t0 * 0.1)

    def test_heat_penalty_applies_above_threshold(self):
        g = fresh()
        g.s.heat = 60
        self.assertEqual(g.heat_penalty(), 1.0)
        g.s.heat = 100
        self.assertAlmostEqual(g.heat_penalty(), 0.75)

    def test_forced_audit_at_max_heat(self):
        g = fresh()
        g.s.heat = 100
        g.tick(0.1)
        self.assertEqual(g.s.pending_event, "audit")
        self.assertIsNotNone(g.pending())

    def test_event_resolution_applies_effects_once(self):
        g = fresh()
        g.s.capital = 1000
        g.s.pending_event = "audit"
        g.s.heat = 50
        g.s.peak_heat = 50
        text = g.resolve_event(0)  # cooperate: -10% capital, heat -20
        self.assertTrue(text)
        self.assertAlmostEqual(g.s.capital, 900, delta=1)
        self.assertAlmostEqual(g.s.heat, 30, delta=1)
        self.assertEqual(g.s.pending_event, "")
        self.assertEqual(g.resolve_event(0), "")  # nothing pending now

    def test_events_are_scheduled_after_grace(self):
        g = fresh()
        g.s.run_capital = 1e5
        g.s.next_event = 0.05
        g.tick(0.1)
        self.assertTrue(g.s.pending_event)

    def test_no_event_before_grace(self):
        g = fresh()
        g.s.next_event = 0.05
        g.tick(0.1)
        self.assertEqual(g.s.pending_event, "")

    def test_narrative_choice_gated(self):
        g = fresh()
        ev = next(e for e in C.events if e["id"] == "tithe_of_faith")
        pay_conviction = ev["choice"][1]
        g.s.narrative = 0
        self.assertFalse(g.choice_available(pay_conviction))
        g.s.narrative = 5
        self.assertTrue(g.choice_available(pay_conviction))

    def test_buff_expires(self):
        g = fresh()
        g.apply_effects({"buff_mult": 2.0, "buff_secs": 1.0})
        self.assertEqual(g.buff_mult(), 2.0)
        g.tick(1.2)
        self.assertEqual(g.buff_mult(), 1.0)

    def test_dossier_unlock_bonus_and_decision(self):
        g = fresh()
        notes = []
        g.on_notify = notes.append
        g.s.lifetime_capital = 150
        g.tick(0.1)
        self.assertIn("d_founding", g.s.dossiers)
        self.assertEqual(len(notes), 1)
        self.assertAlmostEqual(g.dossier_bonus("bonus_mult"), 1.03)
        g.s.dossiers.append("d_choir")
        g.s.heat = 30
        self.assertTrue(g.choose_dossier("d_choir", 0))
        self.assertEqual(g.choose_dossier("d_choir", 1), "")  # decision is final

    def test_hyper_upgrade_costs_narrative_and_persists_in_own_list(self):
        g = fresh()
        u = next(x for x in C.upgrades if x.kind == "hyper")
        g.s.narrative = u.cost
        self.assertTrue(g.buy_upgrade(u))
        self.assertIn(u.id, g.s.hyper)
        self.assertNotIn(u.id, g.s.upgrades)
        self.assertAlmostEqual(g.hyper_mult(), u.mult)

    def test_milestone_grants_narrative(self):
        g = fresh()
        g.s.capital = 1e9
        g.s.ventures[0].owned = 24
        before = g.s.narrative
        g.buy(0)
        self.assertGreater(g.s.narrative, before)

    def test_all_dossier_links_resolve(self):
        ids = {d["id"] for d in C.dossiers}
        for d in C.dossiers:
            self.assertTrue(set(d["links"]) <= ids, d["id"])


class ExitAndTree(unittest.TestCase):
    def test_no_award_before_threshold(self):
        g = fresh()
        g.s.lifetime_capital = 1e19
        self.assertFalse(g.can_exit())
        self.assertEqual(g.do_exit(), 0)
        self.assertEqual(g.s.exits, 0)

    def test_award_follows_sqrt_of_lifetime(self):
        g = fresh()
        g.s.lifetime_capital = 100 * 1e20
        self.assertEqual(g.exit_award(), 10)
        g.s.lifetime_capital = 400 * 1e20
        self.assertEqual(g.exit_award(), 20)

    def test_exit_resets_run_keeps_permanent(self):
        g = fresh()
        g.s.lifetime_capital = g.s.run_capital = 100 * 1e20
        g.s.capital = 5e30
        g.s.ventures[3].owned = 99
        g.s.upgrades.append(C.upgrades[-1].id if C.upgrades[-1].currency == "capital" else "u01_1")
        g.s.hyper.append("uy_1")
        g.s.dossiers.append("d_founding")
        g.s.narrative = 42
        g.s.heat = 80
        self.assertEqual(g.do_exit(), 10)
        s = g.s
        self.assertEqual(s.exits, 1)
        self.assertEqual(s.sovereignty, 10)
        self.assertEqual(s.ventures[3].owned, 0)
        self.assertEqual(s.ventures[0].owned, 1)
        self.assertEqual((s.capital, s.run_capital, s.heat, s.upgrades), (0, 0, 0, []))
        self.assertEqual((s.hyper, s.dossiers, s.narrative), (["uy_1"], ["d_founding"], 42))
        self.assertEqual(s.lifetime_capital, 100 * 1e20)
        self.assertFalse(g.can_exit())          # can't farm the same lifetime twice
        self.assertAlmostEqual(g.sov_mult(), 1.10)

    def test_tree_chain_and_effects(self):
        g = fresh()
        e1, e2 = g._ndef["e1"], g._ndef["e2"]
        g.s.sovereignty = 100
        self.assertFalse(g.can_buy_node(e2))     # needs e1
        self.assertTrue(g.buy_node(e1))
        self.assertTrue(g.buy_node(g._ndef["e2"]))
        self.assertEqual(g.offline_eff(), 0.75)
        self.assertFalse(g.buy_node(e1))         # already owned
        g.buy_node(g._ndef["v1"])
        self.assertEqual(g.tree_all_mult(), 2.0)
        g.buy_node(g._ndef["v2"])
        self.assertEqual(g.tree_tier_mult(0), 3.0)
        self.assertEqual(g.tree_tier_mult(9), 1.0)
        self.assertEqual(g.s.sovereignty, 100 - 1 - 3 - 1 - 3)

    def test_start_bonuses_apply_after_exit(self):
        g = fresh()
        g.s.tree += ["e1", "e2", "e3", "e4", "a3", "a4"]
        g.s.lifetime_capital = 100 * 1e20
        g.do_exit()
        self.assertTrue(all(g.s.ventures[i].proxy for i in range(4)))
        self.assertFalse(g.s.ventures[4].proxy)
        self.assertEqual(g.s.capital, 5000)
        self.assertEqual(g.s.revealed, 7)
        self.assertAlmostEqual(g.proxy_cost(0), C.ventures[0].proxy_cost * 0.5)

    def test_all_nodes_have_valid_requirements(self):
        ids = {n["id"] for n in C.nodes}
        for n in C.nodes:
            self.assertTrue(not n.get("requires") or n["requires"] in ids)


class Persistence(unittest.TestCase):
    def test_roundtrip_and_offline(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "save.json"
            g = fresh()
            g.s.capital = 1e3
            g.hire(0)
            g.s.ventures[0].owned = 7
            save_game(g, p)
            # pretend an hour passed
            import json
            data = json.loads(p.read_text())
            data["last_saved"] = time.time() - 3600
            p.write_text(json.dumps(data))
            g2, away, gain = load_game(C, p)
            self.assertEqual(g2.s.ventures[0].owned, 7)
            self.assertTrue(g2.s.ventures[0].proxy)
            self.assertGreater(gain, 0)
            self.assertAlmostEqual(away, 3600, delta=5)

    def test_corrupt_save_falls_back(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "save.json"
            p.write_text("{not json")
            g, away, gain = load_game(C, p)
            self.assertEqual(g.s.ventures[0].owned, 1)
            self.assertTrue(p.with_suffix(".bak").exists())


if __name__ == "__main__":
    unittest.main()


class Endgame(unittest.TestCase):
    def ready_game(self):
        g = fresh()
        g.s.exits = 3
        g.s.ventures[-1].owned = 1
        return g

    def test_handover_gated_on_exits_and_final_venture(self):
        g = fresh()
        self.assertFalse(g.ending_ready())
        g.s.exits = 3
        self.assertFalse(g.ending_ready())          # no Gate of Perdition yet
        g.s.ventures[-1].owned = 1
        self.assertTrue(g.ending_ready())
        g.s.pending_event = "audit"
        self.assertFalse(g.ending_ready())          # never mid-event

    def test_decline_defers_until_next_exit(self):
        g = self.ready_game()
        g.decline_handover()
        self.assertFalse(g.ending_ready())
        g.s.exits = 4
        self.assertTrue(g.ending_ready())

    def test_sign_starts_new_game_plus_without_award(self):
        g = self.ready_game()
        g.s.tree.append("v1")
        g.s.hyper.append("uy_1")
        exits_before = g.s.exits
        g.sign_handover()
        self.assertTrue(g.s.posthuman)
        self.assertEqual(g.s.machine_level, 1)
        self.assertEqual(g.s.exits, exits_before + 1)
        self.assertEqual(g.s.ventures[-1].owned, 0)  # run was reset
        self.assertEqual((g.s.tree, g.s.hyper), (["v1"], ["uy_1"]))  # permanents kept
        self.assertFalse(g.ending_ready())

    def test_machine_level_escalates_to_final(self):
        g = self.ready_game()
        g.sign_handover()
        self.assertFalse(g.final_ready())
        for _ in range(3):
            g.s.lifetime_capital = (int(g.s.sov_earned) + 1) ** 2 * 1e20 * 1.01
            g.do_exit()
        self.assertGreaterEqual(g.s.machine_level, g.FINAL_LEVEL)
        self.assertTrue(g.final_ready())
        g.s.final_seen = True
        self.assertFalse(g.final_ready())

    def test_ticker_drifts_to_machine_lines(self):
        g = fresh()
        g.s.machine_level = 3
        seen = []
        g.on_log = seen.append
        g.rng.seed(3)
        for _ in range(40):
            g._headline_timer = 0
            g.tick(0.1)
        machine = set(C.headlines["machine"])
        self.assertTrue(seen and all(x in machine for x in seen))
