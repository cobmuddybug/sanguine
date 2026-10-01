# SANGUINE

A terminal-native, grimdark idle game about an infernalist vampire court. Start with one whispered
"yes" in a dark alley, and feed, seduce, bind and bargain your way up to the Gate of Perdition.
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
feeding while the game is closed (capped at 8h, 50% efficiency, raised by the Bloodline).
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
   (frenzy, discounts). Roughly 90+ minutes in, the first Torpor pays off.
9. After enough Torpors and a Gate of Perdition, the Below offers you **the Compact**. Sign it
   and the game's voice changes.

Press `?` in-game for the full controls.

## Development

```bash
python -m unittest discover -s tests          # stdlib only
python tools/sim.py 120 0                     # greedy-bot balance sim
python tools/gen_ventures.py > sanguine/content/ventures.toml
python tools/gen_upgrades.py > sanguine/content/upgrades.toml
python tools/shot.py out.png 130 36 corkboard "g.s.lifetime_capital=1e9"   # SVG->PNG screenshot
```

Engine field names (`capital`, `heat`, `narrative`, `sovereignty`, `proxy`, `exit`) are inherited
from the sibling game; the UI and content rename them (Blood, Inquisition, Sin, Potency, Thrall, Torpor).
Content lives in `sanguine/content/*.toml`.
