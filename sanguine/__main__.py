"""Command line entry point: `sanguine` (game), `sanguine --waybar` (status JSON)."""
from __future__ import annotations

import argparse
import json
import os
import sys

from . import __version__


def waybar_status() -> dict:
    """Bar-module JSON from the save file. No UI, no network, never raises."""
    from .engine.bignum import fmt, money
    from .engine.content import load_content
    from .engine.persistence import load_game
    try:
        game, _, _ = load_game(load_content())
    except Exception:  # noqa: BLE001 - a status bar must not crash
        return {"text": "", "tooltip": "sanguine: no readable save"}
    s = game.s
    rate = game.income_per_sec()
    tip = "\n".join([
        "SANGUINE",
        f"Blood       {money(s.capital)}",
        f"Income      {money(rate)}/s",
        f"Inquisition {s.heat:.0f}%",
        f"Sin         {fmt(s.narrative)}",
        f"Potency     {fmt(s.sovereignty)}  ({s.exits} torpors)",
    ])
    cls = "hot" if s.heat >= 75 else ("ready" if game.can_exit() else "idle")
    return {"text": f"† {fmt(rate)}/s", "tooltip": tip, "class": cls,
            "alt": cls, "percentage": int(min(100, s.heat))}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="sanguine", description="Sanguine - a grimdark terminal idle game of infernal vampires.")
    ap.add_argument("--version", action="version", version=f"sanguine {__version__}")
    ap.add_argument("--waybar", action="store_true", help="print one line of bar-module JSON and exit")
    ap.add_argument("--theme", choices=["omarchy", "crimson"], default=None,
                    help="omarchy (default): follow the active Omarchy theme; crimson: built-in blood/ember palette")
    args = ap.parse_args(argv)
    if args.theme == "crimson":
        os.environ["SANGUINE_THEME"] = "crimson"
    if args.waybar:
        print(json.dumps(waybar_status(), ensure_ascii=False))
        return 0
    from .ui.app import SanguineApp
    SanguineApp().run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
