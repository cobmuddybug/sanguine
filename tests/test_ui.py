"""UI smoke tests: drive the real app with simulated mouse and keys."""
import asyncio
import os
import tempfile
import unittest

os.environ["SANGUINE_HOME"] = tempfile.mkdtemp()

from sanguine.ui.app import SanguineApp, NodeRow, UpgradeRow, VentureRow  # noqa: E402
from sanguine.ui.corkboard import Corkboard  # noqa: E402
from sanguine.ui.modals import ChoiceModal, QuietScreen, TextModal  # noqa: E402
from sanguine.ui.widgets import ActionButton, CycleBar  # noqa: E402


def run(coro):
    return asyncio.run(coro)


class UI(unittest.TestCase):
    def test_mouse_click_bar_buy_bulk_and_proxy(self):
        async def go():
            app = SanguineApp(autosave=False)
            async with app.run_test(size=(100, 30)) as pilot:
                g = app.game
                g.s.capital = 1e6
                await pilot.pause()
                row0 = app.query(VentureRow).first()
                # click the progress bar -> cycle starts
                await pilot.click(row0.query_one(CycleBar))
                self.assertTrue(g.s.ventures[0].running)
                # bulk x10 via the segmented control, then BUY
                seg = [b for b in app.query(".seg") if b.action_id == "bulk:1"][0]
                await pilot.click(seg)
                self.assertEqual(g.s.bulk_index, 1)
                await pilot.click(row0.query_one(".v-buy"))
                self.assertEqual(g.s.ventures[0].owned, 11)
                # hire proxy
                await pilot.click(row0.query_one(".v-proxy"))
                self.assertTrue(g.s.ventures[0].proxy)
        run(go())

    def test_keyboard_only(self):
        async def go():
            app = SanguineApp(autosave=False)
            async with app.run_test(size=(100, 30)) as pilot:
                g = app.game
                g.s.capital = 1e6
                await pilot.press("2")
                self.assertEqual(app.sel["ventures"], 1)
                await pilot.press("enter")
                self.assertEqual(g.s.ventures[1].owned, 1)
                await pilot.press("b", "b")
                self.assertEqual(g.s.bulk_index, 2)
                await pilot.press("exclamation_mark")  # shift+1 -> venture 11 (locked)
                await pilot.press("p")
                await pilot.press("tab")
                self.assertEqual(app.query_one("TabbedContent").active, "proxies")
                await pilot.press("shift+tab")
                self.assertEqual(app.query_one("TabbedContent").active, "ventures")
                await pilot.press("question_mark")
                self.assertIsInstance(app.screen, TextModal)
                await pilot.press("escape")
                self.assertNotIsInstance(app.screen, TextModal)
        run(go())

    def test_right_click_detail_and_hover_info(self):
        async def go():
            app = SanguineApp(autosave=False)
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.hover(app.query(VentureRow)[2].query_one(".v-name"))
                await pilot.pause()
                self.assertIn("Confessional Booth", str(app.query_one("#info").render()))
                await pilot.click(app.query(VentureRow).first().query_one(".v-name"), button=3)
                self.assertIsInstance(app.screen, TextModal)
                await pilot.click("#modal-close")
                self.assertNotIsInstance(app.screen, TextModal)
        run(go())

    def test_upgrades_mouse_and_keyboard(self):
        async def go():
            app = SanguineApp(autosave=False)
            async with app.run_test(size=(100, 30)) as pilot:
                g = app.game
                g.s.capital = 1e9
                await pilot.press("tab", "tab")
                self.assertEqual(app.query_one("TabbedContent").active, "upgrades")
                await pilot.pause(0.2)
                visible = [r for r in app.query(UpgradeRow) if r.display and r.u.currency == 'capital']
                self.assertTrue(visible)
                first = visible[0]
                await pilot.click(first.query_one(".u-btn"))
                self.assertIn(first.u.id, g.s.upgrades)
                # keyboard: down then enter acquires the next visible one
                await pilot.pause(0.2)
                n = len(g.s.upgrades)
                await pilot.press("down")  # skip past any Narrative-priced rows above
                for _ in range(6):
                    if len(g.s.upgrades) > n:
                        break
                    await pilot.press("enter", "down")
                self.assertGreater(len(g.s.upgrades), n)
                # right-click previews without buying
                app.query_one('#ulist').scroll_home(animate=False)
                await pilot.pause(0.2)
                nxt = [r for r in app.query(UpgradeRow) if r.display][0]
                await pilot.click(nxt.query_one(".u-name"), button=3)
                self.assertIsInstance(app.screen, TextModal)
                self.assertGreater(len(g.s.upgrades), n)
        run(go())

    def test_event_modal_keys_and_mouse(self):
        async def go():
            app = SanguineApp(autosave=False)
            async with app.run_test(size=(100, 30)) as pilot:
                g = app.game
                g.s.capital = 1000
                g.s.pending_event = "letter_in_blood"
                await pilot.pause(0.4)
                self.assertIsInstance(app.screen, ChoiceModal)
                await pilot.press("escape")  # events can't be dismissed
                self.assertIsInstance(app.screen, ChoiceModal)
                await pilot.press("1")
                await pilot.pause(0.2)
                self.assertNotIsInstance(app.screen, ChoiceModal)
                self.assertEqual(g.s.pending_event, "")
                self.assertEqual(g.s.events_seen, 1)
                # second event, resolved with the mouse on the 2nd big button
                g.s.pending_event = "letter_in_blood"
                await pilot.pause(0.4)
                btns = list(app.screen.query(".choice-btn"))
                self.assertEqual(len(btns), 3)
                self.assertTrue(all(b.size.height >= 3 for b in btns))
                await pilot.click(btns[1])
                await pilot.pause(0.2)
                self.assertEqual(g.s.events_seen, 2)
        run(go())

    def test_corkboard_click_drag_zoom_keys(self):
        async def go():
            app = SanguineApp(autosave=False)
            async with app.run_test(size=(130, 40)) as pilot:
                g = app.game
                g.s.lifetime_capital = 200
                await pilot.press("tab", "tab", "tab")
                await pilot.pause(0.3)
                board = app.query_one(Corkboard)
                self.assertTrue(g.dossier_unlocked("d_founding"))
                # click the unlocked pin -> dossier opens
                x, y, w, h = board._rect(board._by_id("d_founding"))
                await pilot.click(board, offset=(x + 3, y + 2))
                await pilot.pause(0.2)
                self.assertIsInstance(app.screen, ChoiceModal)
                await pilot.press("escape")
                await pilot.pause(0.3)
                # click-drag pans the board without opening anything
                before = list(board.pan)
                await pilot.mouse_down(board, offset=(60, 20))
                await pilot.hover(board, offset=(40, 14))
                await pilot.mouse_up(board, offset=(40, 14))
                await pilot.pause(0.2)
                self.assertNotEqual(before, board.pan)
                self.assertNotIsInstance(app.screen, ChoiceModal)
                # zoom via keys, then arrow-key selection + enter
                await pilot.press("minus")
                self.assertEqual(board.zoom, 0)
                await pilot.press("plus")
                self.assertEqual(board.zoom, 1)
                board.sel = "d_founding"
                await pilot.press("right")
                self.assertNotEqual(board.sel, "d_founding")
                await pilot.press("enter")
                await pilot.pause(0.2)
                self.assertIsInstance(app.screen, TextModal if not g.dossier_unlocked(board.sel) else ChoiceModal)
        run(go())

    def test_exit_flow_mouse_confirm_and_tree(self):
        async def go():
            app = SanguineApp(autosave=False)
            async with app.run_test(size=(110, 34)) as pilot:
                g = app.game
                g.s.lifetime_capital = 100 * 1e20
                g.s.ventures[2].owned = 7
                await pilot.press("tab", "tab", "tab", "tab")
                await pilot.pause(0.3)
                self.assertEqual(app.query_one("TabbedContent").active, "sovereignty")
                # a stray click does nothing destructive: it only opens a confirmation
                await pilot.click("#exit-btn")
                await pilot.pause(0.2)
                self.assertIsInstance(app.screen, ChoiceModal)
                self.assertEqual(g.s.exits, 0)
                await pilot.press("escape")
                await pilot.pause(0.2)
                self.assertEqual(g.s.exits, 0)
                # keyboard: e -> 1 confirms
                await pilot.press("e")
                await pilot.pause(0.2)
                await pilot.press("1")
                await pilot.pause(0.3)
                self.assertEqual(g.s.exits, 1)
                self.assertEqual(g.s.ventures[2].owned, 0)
                self.assertEqual(g.s.sovereignty, 10)
                # tree: click the first node's button, then keyboard-buy the next
                rows = list(app.query(NodeRow))
                await pilot.click(rows[0].query_one(".n-btn"))
                self.assertTrue(g.node_owned(rows[0].n["id"]))
                await pilot.press("down")
                await pilot.press("enter")
                self.assertTrue(g.node_owned(rows[1].n["id"]))
        run(go())

    def test_reset_requires_confirmation(self):
        async def go():
            app = SanguineApp(autosave=False)
            async with app.run_test(size=(110, 34)) as pilot:
                g = app.game
                g.s.capital = 123
                await pilot.press("tab", "tab", "tab", "tab")
                await pilot.pause(0.3)
                await pilot.click("#reset-btn")
                await pilot.pause(0.2)
                self.assertIsInstance(app.screen, ChoiceModal)
                self.assertEqual(g.s.capital, 123)
                await pilot.press("escape")
                await pilot.pause(0.2)
                self.assertEqual(g.s.capital, 123)
                await pilot.click("#reset-btn")
                await pilot.pause(0.2)
                await pilot.press("1")
                await pilot.pause(0.3)
                self.assertEqual(app.game.s.capital, 0)
        run(go())

    def test_handover_flow_and_machine_voice(self):
        async def go():
            app = SanguineApp(autosave=False)
            async with app.run_test(size=(110, 34)) as pilot:
                g = app.game
                g.s.exits = 3
                g.s.ventures[19].owned = 1
                await pilot.pause(0.4)
                self.assertIsInstance(app.screen, ChoiceModal)   # page 1
                await pilot.press("escape")                       # cannot be skipped
                self.assertIsInstance(app.screen, ChoiceModal)
                await pilot.press("1")
                await pilot.pause(0.2)
                await pilot.press("1")                            # page 2 -> 3
                await pilot.pause(0.2)
                self.assertEqual(len(app.screen.query(".choice-btn")), 2)
                await pilot.press("2")                            # refuse
                await pilot.pause(0.3)
                self.assertFalse(g.s.posthuman)
                self.assertNotIsInstance(app.screen, ChoiceModal)
                g.s.exits = 4                                     # asks again after another EXIT
                await pilot.pause(0.4)
                self.assertIsInstance(app.screen, ChoiceModal)
                await pilot.press("1")
                await pilot.pause(0.2)
                await pilot.press("1")
                await pilot.pause(0.2)
                await pilot.press("1")                            # sign
                await pilot.pause(0.4)
                self.assertTrue(g.s.posthuman)
                g.s.machine_level = 2
                await pilot.pause(0.3)
                self.assertIn("OFFERING", str(app.query_one("#hud-capital").render()))
                g.s.machine_level = 4
                await pilot.pause(0.3)
                self.assertEqual(str(app.query_one("TabbedContent").get_tab("ventures").label), "domains")
                g.s.machine_level = 3
                g.log("You made your quota.")
                await pilot.pause(0.2)
                self.assertIn("the vessel made its quota", str(app.query_one("#ticker").render()))
        run(go())

    def test_final_screen_is_quiet_and_dismisses(self):
        async def go():
            app = SanguineApp(autosave=False)
            async with app.run_test(size=(110, 34)) as pilot:
                g = app.game
                g.s.posthuman = True
                g.s.machine_level = 4
                await pilot.pause(0.4)
                self.assertIsInstance(app.screen, QuietScreen)
                self.assertTrue(g.s.final_seen)
                await pilot.press("x")                            # too early: ignored
                self.assertIsInstance(app.screen, QuietScreen)
                app.screen._arm()
                await pilot.press("x")
                await pilot.pause(0.2)
                self.assertNotIsInstance(app.screen, QuietScreen)
                await pilot.pause(0.4)
                self.assertNotIsInstance(app.screen, QuietScreen)  # doesn't come back
        run(go())

    def test_tab_survives_modal(self):
        async def go():
            app = SanguineApp(autosave=False)
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.press("tab", "tab")
                await pilot.press("question_mark")
                await pilot.pause(0.2)
                await pilot.press("escape")
                await pilot.pause(0.3)
                self.assertEqual(app.query_one("TabbedContent").active, "upgrades")
        run(go())

    def test_resize_layouts(self):
        async def go():
            app = SanguineApp(autosave=False)
            async with app.run_test(size=(100, 30)) as pilot:
                self.assertFalse(app.has_class("-wide"))
                await pilot.resize_terminal(200, 50)
                await pilot.pause(0.3)
                self.assertTrue(app.has_class("-wide"))
                # a click after resize still lands on the right widget
                app.game.s.capital = 100
                await pilot.click(app.query(VentureRow).first().query_one(CycleBar))
                self.assertTrue(app.game.s.ventures[0].running)
        run(go())


if __name__ == "__main__":
    unittest.main()


class LongGameUI(unittest.TestCase):
    def test_dynasty_tab_buy_perk_and_found(self):
        from sanguine.ui.ledger import LedgerRow

        async def go():
            app = SanguineApp(autosave=False)
            async with app.run_test(size=(120, 40)) as pilot:
                g = app.game
                app._goto("dynasty")
                await pilot.pause(0.2)
                rows = list(app.query("#dynlist LedgerRow"))
                g.s.lineage = 10
                await pilot.pause(0.1)
                app.refresh_ui()
                await pilot.click(rows[0].query_one(".n-btn"))        # Heirloom Bloodline
                self.assertIn("p1", g.s.perks)
                self.assertEqual(g.s.lineage, 10 - g._pdef["p1"]["cost"])
                # the Dynasty button refuses until the Compact is signed
                await pilot.click(app.query_one("#dyn-btn"))
                await pilot.pause(0.2)
                self.assertEqual(g.s.dynasties, 0)
                g.s.posthuman, g.s.machine_level = True, 4
                g.s.sov_earned = g.s.sov_raw = g.dynasty_threshold() * 1e3
                app.refresh_ui()
                await pilot.click(app.query_one("#dyn-btn"))
                await pilot.pause(0.3)
                self.assertIsInstance(app.screen, ChoiceModal)
                await pilot.press("1")
                await pilot.pause(0.3)
                self.assertEqual(g.s.dynasties, 1)
                self.assertEqual(g.s.lineage, 10 - g._pdef["p1"]["cost"] + 9)
        run(go())

    def test_ages_and_hunts_tab(self):
        async def go():
            app = SanguineApp(autosave=False)
            async with app.run_test(size=(120, 40)) as pilot:
                g = app.game
                now = [1_700_000_000.0]
                g.clock = lambda: now[0]
                g._slow_tick()
                now[0] += 3 * 3600
                g._slow_tick()
                g.s.capital = 1e12
                app._goto("ages")
                await pilot.pause(0.2)
                app.refresh_ui()
                rows = list(app.query("#agelist LedgerRow"))
                vis = [r for r in rows if r.view().show]
                self.assertEqual(len(vis), 3)                       # daily, weekly, one offer
                await pilot.click(rows[0].query_one(".n-btn"))      # accept the daily hunt
                self.assertEqual(g.s.hunt["active"], "daily")
                await pilot.click(rows[4].query_one(".n-btn"))  # begin the offered Age (offer slot 0)
                await pilot.pause(0.3)
                self.assertIsInstance(app.screen, ChoiceModal)
                await pilot.press("1")
                await pilot.pause(0.3)
                self.assertEqual(len(g.s.ages["running"]), 1)
        run(go())

    def test_annals_tab_lists_every_feat(self):
        async def go():
            app = SanguineApp(autosave=False)
            async with app.run_test(size=(120, 40)) as pilot:
                app._goto("annals")
                await pilot.pause(0.2)
                self.assertEqual(len(list(app.query("#annallist LedgerRow"))), len(app.game.c.feats))
                await pilot.press("tab", "shift+tab")
        run(go())
