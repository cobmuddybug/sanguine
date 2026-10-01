"""Render a screenshot of the app to PNG for visual checks: python tools/shot.py out.png [W H] [tab] [setup-expr]"""
import asyncio, os, sys, tempfile, subprocess
sys.path.insert(0, ".")
os.environ["SANGUINE_HOME"] = tempfile.mkdtemp()
from sanguine.ui.app import SanguineApp

out = sys.argv[1]; w = int(sys.argv[2]) if len(sys.argv) > 2 else 100; h = int(sys.argv[3]) if len(sys.argv) > 3 else 30
tab = sys.argv[4] if len(sys.argv) > 4 else "ventures"; setup = sys.argv[5] if len(sys.argv) > 5 else ""

async def main():
    app = SanguineApp(autosave=False)
    async with app.run_test(size=(w, h)) as pilot:
        g = app.game
        exec(setup)
        await pilot.pause(0.2)
        for _ in range(__import__("sanguine.ui.app", fromlist=["TABS"]).TABS.index(tab)):
            await pilot.press("tab"); await pilot.pause(0.2)
        await pilot.pause(0.4)
        open(out + ".svg", "w").write(app.export_screenshot())
asyncio.run(main())
subprocess.run(["rsvg-convert", out + ".svg", "-o", out])
