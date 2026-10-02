# SANGUINE

A terminal-native, grimdark idle game about an infernalist vampire court. Start with one whispered
"yes" in a dark alley, and feed, seduce, bind and bargain your way up to the Gate of Perdition,
through it, and into the Below, then found dynasties that outlast it.
Suggestive and edgy rather than explicit: velvet, wax, throats, confession booths and contracts
signed in something that isn't ink. Everything is fictional; all houses, orders and people are
invented, and every character is an adult and a willing party to their own ruin.

Same engine and UI as its sibling game *Hyperstition Inc.* (Adventure-Capitalist-style idle loop,
Textual TUI), with entirely new content, voice and palette.

- Offline and local-first. No network calls at runtime, no telemetry.
- Mouse-first and keyboard-complete.
- Follows your Omarchy theme (red becomes the blood accent); falls back to a built-in crimson palette.

## Install

Requires Python 3.11+, [pipx](https://pipx.pypa.io/) and [Textual](https://textual.textualize.io/)
(on Arch: `sudo pacman -S python-textual python-pipx`).

```bash
./install.sh               # puts `sanguine` on your PATH and adds a launcher entry
./install.sh --uninstall   # removes both (your save is kept)
```

Run `sanguine`, or search **Sanguine** in the Omarchy menu (Super+Space). Optional keybind for
`~/.config/hypr/bindings.lua`:

```lua
o.bind("SUPER + CTRL + ALT + S", "Sanguine", "omarchy-launch-tui --app-id=TUI.float sanguine")
```

Without installing: `python -m sanguine`. Options: `--theme crimson`, `--waybar`, `--version`.

## Saves

`~/.local/share/sanguine/save.json`, autosaved every 30 seconds and on quit. Your Thralls keep
feeding while the game is closed (capped at 8h, 50% efficiency, both raised by the Bloodline,
Endless Rites and Lineage perks). Ages and Hunts run on the real clock, so they also advance while you are away.
`SANGUINE_HOME` redirects the save directory; set it when testing.

## How to play

1. **Claim Domains.** Each feeds on a timed cycle and pays Blood (†). Click a bar to feed by hand.
2. **Bind Thralls** so a domain feeds by itself.
3. **Claim more units.** Milestones at 25, 50, 100, ... multiply a domain's output.
4. **Rites** multiply output. **Infernal Pacts** (bought with Sin, ⛧) are permanent.
5. Watch the **Inquisition**: it rises with your income. Above 75 output suffers; at 100 the
   Choir of the Wounded Lamb calls. Veils and glamours lower it.
6. **Incidents** interrupt every few minutes with a three-way choice (keys 1/2/3).
7. **The Court** pins the rival houses, hunters and cults watching you. Unseal files for passives.
8. **Torpor** buries the house for a century in exchange for permanent **Potency**, spent in the
   Bloodline: *The Long Sleep* (offline, automation), *Predation* (multipliers), *Perdition*
   (frenzy, discounts). Roughly 90+ minutes in, the first Torpor pays off. Leftover Potency goes
   into the **Endless Rites** at the bottom of the Bloodline: repeatable, ever-pricier upgrades.
9. After enough Torpors and a Gate of Perdition, the Below offers you **the Compact**. Sign it and
   the game's voice changes, and **Domains 21-30** (the Below) open. It is a chapter, not the end.
10. Three Torpors after the Compact (machine level 4) you can found a **Dynasty**: it resets
    Potency and the Bloodline in exchange for **Lineage**, which buys permanent perks (some keep
    your Bloodline, one automates Torpor) and lifts all output. Each Dynasty asks for ten times
    more Potency than the last, and Lineage scales with orders of magnitude, not raw size.
11. **Ages** are real-time commissions (12-72 hours) that cost a few hours of your income; you pick
    one of two rewards (Lineage, a permanent bonus, a buff, or Blood). A new one is offered about
    every 20 hours. **Hunts** are a daily and a weekly trial with a rule (no Rites, no Thralls, no
    Frenzy, or a hotter Inquisition) and unit goals. Accept one while you are short of its goals.
12. **Annals** are 45 achievements, each worth +2% output, with a title that climbs from Fledgling
    to Sovereign.

Tabs: Domains, Thralls, Rites, Court, Bloodline, Dynasty, Ages, Annals, Chronicle (the log).
Press `?` in-game for the full controls.

## Development

```bash
python -m unittest discover -s tests          # stdlib only
python tools/sim.py 120 0                     # greedy-bot balance sim (one run, a few Torpors)
python tools/sim_long.py 45 18                # daily-player sim over weeks: Compact, Dynasties, Ages, Hunts
NO_DYN=1 python tools/sim_long.py 30 18       # same, with Dynasties switched off
python tools/gen_ventures.py > sanguine/content/ventures.toml
python tools/gen_upgrades.py > sanguine/content/upgrades.toml
python tools/gen_annals.py > sanguine/content/annals.toml
python tools/shot.py out.png 130 36 corkboard "g.s.lifetime_capital=1e9"   # SVG->PNG screenshot
```

Engine field names (`capital`, `heat`, `narrative`, `sovereignty`, `proxy`, `exit`) are inherited
from the sibling game; the UI and content rename them (Blood, Inquisition, Sin, Potency, Thrall, Torpor).
Content lives in `sanguine/content/*.toml`. The long-game layers are engine mixins
(`engine/dynasty.py`, `ages.py`, `annals.py`); `Game(clock=...)` is injectable so wall-clock systems are testable.
Design notes and balance results are in [docs/DYNASTY.md](docs/DYNASTY.md).

## License

MIT, see [LICENSE](LICENSE). Content is fictional and intended for adults.
