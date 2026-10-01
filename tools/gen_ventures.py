"""Generate sanguine/content/ventures.toml.

Numbers live here so balance can be retuned in one place; text lives here so
the TOML stays a flat, hand-editable artefact afterwards.  Run:

    python tools/gen_ventures.py > sanguine/content/ventures.toml
"""
import math

# name, cycle seconds, hook, [variant after 1 TORPOR, variant after 2+ TORPORs], thrall name, thrall blurb
V = [
 ("Alley Kiss", 1, "A stranger, a brick wall, a whispered yes.",
  ["The wall remembers you. So do the strangers, in dreams they cannot explain.",
   "They no longer need to be asked. They queue, and call it fate."],
  "Lookout Moth", "Watches the corners and keeps the blushing ones coming."),
 ("Velvet Rope Club", 3, "Everyone on the list wants to be on the menu.",
  ["The bouncer checks pulses, not IDs. The bassline is tuned to a heartbeat.",
   "The queue goes round the block and into the next century. Nobody remembers arriving."],
  "Doorman of Sighs", "Lets in the willing, and the very willing."),
 ("Confessional Booth", 6, "Absolution, priced per sin.",
  ["Absolution, priced per sin. The priest is hungry too.",
   "The grille has learned to forgive. It bills accordingly, and breathes."],
  "Fallen Curate", "Hears them out, then sends them your way, trembling and grateful."),
 ("Bathhouse of Sighs", 10, "Steam, silk, and a pulse at every wrist.",
  ["Steam, silk, and a pulse at every wrist. Towels are complimentary; the rest is a donation.",
   "The water is warm because of what is in it. Regulars are called 'the flushed'."],
  "Silk Attendant", "Oils the way, loosens the wrists, asks no questions."),
 ("Night-Shift Blood Bank", 15, "Cold, clean, and nobody has to say yes.",
  ["Cold, clean, and nobody has to say yes. Some of the donors still ask to be thanked.",
   "The fridges hum a hymn. Stock is labelled by sin, not by type."],
  "Devoted Phlebotomist", "Draws the pints, forgets the names, keeps the receipts warm."),
 ("Black Mass Salon", 25, "Mass, but the wine is what is in the wine.",
  ["The hymns are the same. The kneeling is different.",
   "The altar is always warm. Nobody has asked whose."],
  "Deacon of Lace", "Swings the censer and lowers the lights."),
 ("Sommelier's Cellar", 40, "Vintages catalogued by sin, aged by scandal.",
  ["Vintages catalogued by sin. Notes of regret, finish of surrender.",
   "The oldest bottles bear names you almost recognise. The cellar tells you when to drink."],
  "Cellar Sommelier", "Decants the devoted with a flourish."),
 ("House of Debts", 60, "Everyone owes. Everyone pays in kind.",
  ["The ledger accepts only the currencies of the body. Interest is charged nightly.",
   "The debts have started collecting each other, the way lovers do."],
  "Velvet Bailiff", "Collects what is owed, tenderly, after hours."),
 ("Fleshpit Cult", 90, "A congregation that begs to be tithed.",
  ["A congregation that begs to be tithed, and weeps when the plate passes them by.",
   "Membership is a wound that never closes. They wear the scars like jewellery."],
  "High Acolyte", "Speaks in your cadence and kneels on your behalf."),
 ("Funeral Parlour After Hours", 120, "The dead are quiet. The mourners, less so.",
  ["The dead are quiet. The mourners, less so, once the lights go down.",
   "Fewer arrive in coffins than leave in them. The flowers are fresher than they should be."],
  "Widow in Black", "Prepares the bodies, and the bereaved."),
 ("The Fever Ward", 180, "Fever as foreplay; contagion as courtship.",
  ["Sickbeds tended by lovers who chose to catch it.",
   "The ward is full, and the patients have stopped asking for cures."],
  "Sister of Sorrows", "Bandages the willing and fans the flames."),
 ("Diabolist Law Firm", 240, "Contracts drafted in the dark, sealed in wet ink.",
  ["Every clause is a lock. Every signature is a taste.",
   "The firm has never lost a case. The clients have never won a soul back."],
  "Counsel of Nine Clauses", "Reads the fine print aloud, in a voice that is not quite theirs."),
 ("The Endless Masquerade", 360, "Every guest a mask; every mask a menu.",
  ["Every guest is a mask, every mask a lie, every lie a vein.",
   "The ball has not ended in three hundred years. The musicians stopped being alive some time ago."],
  "Master of Masks", "Knows who is under every face, and who is next."),
 ("Bought Magistracy", 480, "Justice, with a bite.",
  ["Justice, with a bite. Sentences are commuted to service.",
   "The gavel is a cufflink of yours. Verdicts arrive pre-signed, and warm."],
  "Bailiff-Consort", "Keeps the docket full and the defendants grateful."),
 ("Ossuary Bank", 720, "Deposits of the dead; interest on the living.",
  ["The vault is lined with bone and lit by wax. Interest is paid in years.",
   "Depositors no longer remember opening accounts. Their descendants still pay."],
  "Teller of Bones", "Counts the dead twice, for luck."),
 ("Coven of Nine Brides", 1080, "Nine wives; none of them agree on the husband.",
  ["Nine wives, each convinced she is the favourite. The bed is very large.",
   "There are now more brides than the house can hold. The house has agreed to make room."],
  "First Bride", "Wears your ring, resents it beautifully."),
 ("Infernal Embassy", 1500, "Diplomatic immunity from God.",
  ["Diplomatic immunity from God. Visas are written in ash.",
   "The ambassador has stopped returning to Hell. Hell has started returning to the embassy."],
  "Attache of Ash", "Carries messages nobody should read."),
 ("The Blood Moon Engine", 2400, "Turn the moon. The tides obey.",
  ["Turn the moon; the tides, and the pulses, obey.",
   "The engine no longer needs turning. The moon is on its knees."],
  "Orrery Keeper", "Winds the moon like a watch."),
 ("Throne of a Thousand Sighs", 3600, "Every sigh a tithe; every tithe a promise.",
  ["A throne with no armrests, because nobody has ever wanted you to let go.",
   "The throne is warm. It has been warm for a while. It is difficult to say who is sitting on whom."],
  "Herald of Sighs", "Announces you in a voice that makes the candles shiver."),
 ("The Gate of Perdition", 7200, "Hell, opening from the inside.",
  ["Hell, opening. It seems to know you. It smiles the way you do.",
   "It has stopped waiting for you to choose. It has begun choosing for you, tenderly."],
  "The Reflection", "Wears your face while you rest, and has begun to enjoy it."),
]

N = len(V)
import os
PAYBACK_R = float(os.environ.get("PAYBACK_R", "1.45"))
SLOWDOWN = float(os.environ.get("SLOWDOWN", "3.0"))   # uniform stretch of the whole timeline
PLAIN = [
 "The humblest hunt: a lonely bite in a dark alley. Small, quick, and just risky enough to be thrilling.",
 "A nightclub where the dancefloor is a hunting ground. Music, sweat and low light make mortals careless with their necks.",
 "You sit behind the lattice where the guilty whisper their sins, and feed on shame as much as on blood. Guilt makes an excellent appetiser.",
 "A luxurious bathhouse where guests shed their inhibitions with their clothes. Flushed skin, bare shoulders, slow bites.",
 "A hospital's blood supply, raided nightly. Efficient and impersonal: the vampire equivalent of a warehouse store, minus the eye contact.",
 "A weekly ritual where the faithful, in various states of undress, offer blood at an altar. Part church, part orgy, all subscription.",
 "A private cellar where blood is sorted, aged and served like fine wine. Prices climb with how scandalous the source.",
 "A brothel-cum-loan office where clients trade favours for cash and cash for bites. Owe the House enough and you belong to it.",
 "A cult of devoted followers who live for the honour of feeding you. They do the recruiting; you do the draining.",
 "A funeral home used as cover. Grief makes mortals vulnerable, and mourning dress makes a fine disguise.",
 "A hospice where the dying offer themselves gladly. Desperation has a flavour, and you are a connoisseur.",
 "A law firm that writes deals with Hell on behalf of mortals, signed in blood. You take a cut of every soul that changes hands.",
 "A never-ending ball for the powerful, where you feed on aristocrats and politicians under the cover of costume.",
 "A corrupt court system you own. Convicts and inconvenient witnesses come to you, and are made to feel welcome.",
 "A bank whose vaults are built from human remains. It lends against the future lives of the borrower's family.",
 "A harem-coven of devoted brides who channel strength and blood to you. They quarrel, scheme, and love you in equal measure.",
 "Your official mission to the underworld: trade deals, tribute, and an occasional demon at dinner.",
 "A great clockwork orrery that bends the lunar cycle, dragging blood to the surface of an entire city.",
 "You rule a city by night. Each subject owes a small ritual offering of blood, attention and desire.",
 "The last door: a real gateway to Hell. It runs itself, it is hungry, and it looks a lot like you.",
]

MILESTONES = [
 (25, 2, "First Blood"), (50, 2, "A Taste for It"), (100, 2, "Bloodlust"),
 (200, 2, "Rite of Frenzy"), (300, 3, "Coven Sanction"), (400, 3, "Sacred Excess"),
 (500, 3, "Vermilion Tide"), (600, 3, "Unhallowed Ground"), (700, 3, "The Red Hour"),
 (800, 3, "Sanctified by Sin"), (900, 3, "Beyond Absolution"), (1000, 4, "A Thousand Kneelings"),
 (1250, 4, "Terminal Craving"), (1500, 4, "The Long Feast"), (1750, 4, "Chorus of Hunger"),
 (2000, 5, "The Cup Never Empties"), (2500, 5, "Beyond Satiety"), (3000, 5, "No One Left to Beg"),
]


GLOBAL_MILESTONES = [
 (25, 2, "Full Household"), (50, 2, "Every Room Is Yours"), (100, 3, "Total Dominion"),
 (200, 3, "The Whole City Kneels"), (300, 3, "Every Door Is Your Door"), (400, 3, "Lord of Every Night"),
 (500, 3, "Nothing Left Outside the Court"),
]


def sig(x, n=3):
    if x == 0:
        return 0
    return float(f"{x:.{n - 1}e}")


def main():
    out = ["# Generated by tools/gen_ventures.py -- safe to hand-edit afterwards.", ""]
    out.append("[economy]")
    out.append("proxy_cost_factor = 250.0")
    out.append("")
    for (u, m, name) in MILESTONES:
        out += ["[[milestone]]", f"units = {u}", f"mult = {m}", f'name = "{name}"', ""]
    for (u, m, name) in GLOBAL_MILESTONES:
        out += ["[[global_milestone]]", f"units = {u}", f"mult = {m}", f'name = "{name}"', ""]
    for i, (name, cyc, hook, variants, pname, pblurb) in enumerate(V):
        cost = sig(4 * 12.5 ** i)
        payback = 4 * PAYBACK_R ** i          # seconds for a single unit to repay itself
        slow = 1 + (SLOWDOWN - 1) * min(1.0, i / 4)   # opening tiers stay snappy
        payout = sig(cost * cyc / payback / slow)
        growth = round(1.07 + 0.08 * i / (N - 1), 4)
        out += [
            "[[venture]]",
            f'id = "v{i + 1:02d}"',
            f'name = "{name}"',
            f"cycle = {float(cyc)}",
            f"base_cost = {cost!r}",
            f"growth = {growth}",
            f"base_payout = {payout!r}",
            f'proxy_name = "{pname}"',
            f'proxy_blurb = "{pblurb}"',
            f'plain = "{PLAIN[i].replace(chr(34), chr(39))}"',
            "flavour = [",
            f'  "{hook}",',
            f'  "{variants[0]}",',
            f'  "{variants[1]}",',
            "]",
            "",
        ]
    print("\n".join(out))


if __name__ == "__main__":
    main()
