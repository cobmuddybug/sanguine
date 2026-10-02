# Sanguine: long-form progression design (draft)

Goal: weeks of engagement at about an hour of active play a day plus overnight idle.

## 0. Re-baseline the economy (partly done)

Problem: a 9.8h save sat at 1.8e37 lifetime Blood with 432,612,260 Potency pending, because output was
`1 + 0.01 * earned` and the award is `floor(sqrt(lifetime / 1e20))`, so one Torpor was a ~4e6x jump.

Done: output is now `1 + earned^0.25` (`SOV_MULT_COEF/EXP` in `engine/game.py`). Sim (greedy bot, ~7x faster
than a human): Torpor 1 at 63m, then 23m / 26m / 20m / 20m per run, with awards in the 1e5-1e6 range
and a multiplier that creeps (29x at 7e5 Potency) instead of exploding.

Still open: after Torpor 2 each run is only ~20 bot-minutes, because the tree's free Thralls and ~540x tier
multipliers hit the tier-20 plateau fast, and awards plateau with it. Lengthening runs needs more road
past the plateau (Domains 21-30, section 2) and a Dynasty gate (section 3), not more tuning of this curve.

## 1. Layer 1: Endless Rites (implemented)

Four repeatable Potency sinks (`[[endless]]` in `content/sovereignty.toml`): Dynastic Appetite (x1.10),
The Long Coffin (+1h offline cap), Blood Tithe (+3% Torpor award), Fevered Dynasty (+10 momentum cap).
Costs are `base * growth^level`. Needs retuning after step 0.

## 2. The Compact becomes mid-game (done: Domains 21-30)

The Compact stays at 3 Torpors and a Gate of Perdition, but is chapter two, not the ending.
- Machine level keeps rising to 6 and gates content instead of just changing the voice.
- Post-Compact unlocks Domains 21-30 ("Below" tiers), costed against the new economy.
- The Quiet screen reads "yet", and is the hand-off into the Dynasty layer.

## 3. Dynasty (second prestige layer)

- Trigger: available after the Compact and machine level >= 4.
- Resets: Potency, the Bloodline tree, endless levels. Keeps: Lineage, Chronicle, dossiers.
- Awards **Lineage** = `floor((sov_earned / D0)^(1/3))`, D0 tuned so the first Dynasty is ~1 week in.
- Lineage buys a permanent perk tree: automation (auto-Torpor with a threshold), new Domain slots, bigger Tithe.
- Each Dynasty needs ~3x the previous run time, so the loop slows by design.

## 4. Slow-clock layer (real time)

- **Ages**: long timers (24-72h) that need Blood and a decision to resolve, paying Lineage or unique dossiers.
- **Hunt**: a daily/weekly challenge modifier ("no Rites this run", "no Thralls") with a fixed goal.
- **Chronicle**: 100+ achievements, each a small permanent bonus, plus titles and cosmetic themes.
- Offline progress stays capped (raised only by The Long Coffin), so waiting is the reward, not a loophole.

## Order of work
1. Re-baseline (0) and retune Endless. 2. Compact copy and Domains 21-30. 3. Dynasty. 4. Ages/Hunt/Chronicle.

## Status: Domains 21-30 (implemented)
Ten "Below" domains (Hellmouth Tithe Office .. The Consummation) with 30 new Rites and 3 late global Rites.
They stay veiled until the Compact is signed, and the global-milestone floor still counts only the first 20.
Sim (greedy bot, ~7x faster than a human): tier 21 about 9m after the Compact, tier 30 about 238m after, i.e.
roughly 4 bot-hours (~25-30 human hours) of new road. Hotkeys stop at 20; use j/k for the Below.
Still to do at that point: the Dynasty layer (section 3) and the slow-clock layer (section 4); both are now implemented, see below.

## Status: Dynasty, Ages, Hunts, Annals (implemented)
- **Dynasty** (`engine/dynasty.py`, `content/dynasty.toml`): unlocks at machine level 4 (the Quiet screen). Award is
  `floor((Potency earned this dynasty / (2e6 * 3^dynasties))^(1/3))` Lineage. Resets Potency, Bloodline and Endless
  Rites (Heirloom perks keep the cheap or all nodes) and keeps Lineage, perks, Annals, Pacts, dossiers and the Compact.
  Each Lineage ever earned gives +10% output; nine perks plus one endless; the Retainer perk automates Torpor.
- **Ages** (`engine/ages.py`, `content/ages.toml`): wall-clock commissions. One offer every 20h (max 3 held, 7-day
  life, 2 running). Cost is hours of your income, so it scales. Rewards: Lineage, permanent Legacy %, timed buff, Blood.
- **Hunts** (`content/hunts.toml`): one daily (+1 Lineage) and one weekly (+3) trial with a rule (no Rites, no Thralls,
  no Frenzy, fevered). You can only accept while short of every goal, so the trial starts after a Torpor.
- **Annals** (`engine/annals.py`, `tools/gen_annals.py`): 45 feats, each +2% output, plus titles.
- Passive Lineage income is about 4-5 a day if you take every Age and Hunt; the perk tree costs about 90, so
  roughly three weeks of slow-clock play, alongside the Dynasty itself.


## Balance pass (long-horizon sim, `tools/sim_long.py`)
Model: a daily player, 18 bot-minutes of play (~2 human hours; the bot is ~7x faster) then offline for the rest of
the day on a simulated wall clock, claiming Ages and Hunts at login. `NO_DYN=1` turns Dynasties off.

Findings and fixes:
- Potency exploded (7e6 on day 7, 1e9 on day 8) because Endless multipliers outran their cost curves. Now
  x1.04 (all) and x1.06 (Below) per level at growth 1.5, so they scale as a mild power of Potency.
- Cube-root Lineage inflated (45, 298, 761 per Dynasty). Now logarithmic: 3 Lineage per power of ten of Potency
  above the threshold, with the threshold x10 per Dynasty. A million-fold bigger run is only twice the Lineage.
- Ages could never be afforded (cost used potential income, which includes unbound domains); now based on income
  you actually bank, with a 10% floor from potential.
- Torpor alone saturates (~1e16 Potency by day 22), so Dynasties are what keep the loop alive.
- The sim bot only spent Potency after its own Torpors, missing the Retainer's automatic ones; fixed.

Resulting timeline for that player: Compact day 4, Below opens day 5, tier 30 on day 11, Dynasty #1 on day 14
(+16 Lineage), Dynasty #2 on day 22, perk tree ~8 of 9 by day 20, roughly 27 Ages and 28 Hunts by day 32.
A heavier player runs faster in proportion; the Ages and Hunts clocks do not move.
Known limits: the bot has no judgement (it takes every Age, always picks Lineage), content before the Compact
(about 4 days) is still the fastest part.
