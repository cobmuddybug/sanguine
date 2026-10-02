"""Serializable game state. Plain data, no logic."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict

SAVE_VERSION = 1
BULK_MODES = (1, 10, 100, 0)  # 0 == MAX


@dataclass
class VentureState:
    owned: int = 0
    proxy: bool = False
    progress: float = 0.0   # seconds into current cycle
    running: bool = False


@dataclass
class GameState:
    ventures: list[VentureState] = field(default_factory=list)
    capital: float = 0.0
    run_capital: float = 0.0        # earned this run (since last EXIT)
    lifetime_capital: float = 0.0   # earned across all runs
    momentum: float = 0.0
    heat: float = 0.0
    narrative: float = 0.0
    sovereignty: float = 0.0
    exits: int = 0
    upgrades: list[str] = field(default_factory=list)  # purchased upgrade ids (this run)
    hyper: list[str] = field(default_factory=list)     # Infernal Pacts (permanent)
    tree: list[str] = field(default_factory=list)      # Bloodline nodes owned (permanent)
    sov_earned: float = 0.0                            # total Sovereignty ever awarded
    sov_raw: float = 0.0                               # base Potency points claimed (before Tithe bonus)
    endless: dict = field(default_factory=dict)        # repeatable Bloodline levels {id: n}
    posthuman: bool = False        # signed the handover: New Game+
    machine_level: int = 0         # how far the voice has drifted (0 = human)
    ending_retry_exit: int = 0     # don't re-offer the compact before this many TORPORs
    final_seen: bool = False
    lineage: float = 0.0           # Dynasty currency (spendable)
    lineage_earned: float = 0.0    # total Lineage ever earned (also lifts output)
    dynasties: int = 0
    perks: list[str] = field(default_factory=list)       # Lineage perks owned (permanent)
    perk_levels: dict = field(default_factory=dict)      # repeatable perk levels
    legacy: float = 0.0            # permanent +fraction to all output, earned from Ages
    feats: list[str] = field(default_factory=list)       # Annals earned
    stats: dict = field(default_factory=dict)            # lifetime peaks the Annals watch
    ages: dict = field(default_factory=dict)             # {"next","seq","offers":[...],"running":[...],"done"}
    hunt: dict = field(default_factory=dict)             # {"day","week","active","daily_done","weekly_done"}
    ages_done: int = 0
    hunts_done: int = 0
    settings: dict = field(default_factory=dict)         # e.g. {"auto_exit": True}
    peak_heat: float = 0.0
    next_event: float = 240.0
    pending_event: str = ""         # id of an event awaiting a choice
    events_seen: int = 0
    buffs: list[dict] = field(default_factory=list)    # {"name", "mult", "left"}
    dossiers: list[str] = field(default_factory=list)  # unlocked
    dossier_choices: dict = field(default_factory=dict)
    bulk_index: int = 0
    revealed: int = 5               # ventures shown (rest are silhouettes)
    idle: float = 0.0               # seconds since last player action
    play_time: float = 0.0
    clicks: int = 0
    log: list[str] = field(default_factory=list)
    last_saved: float = 0.0         # unix time
    version: int = SAVE_VERSION
    extra: dict = field(default_factory=dict)  # later-milestone state (upgrades, dossiers, ...)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict, n_ventures: int) -> "GameState":
        s = cls()
        for k, v in d.items():
            if k == "ventures":
                s.ventures = [VentureState(**{f: x for f, x in vs.items() if f in VentureState.__dataclass_fields__})
                              for vs in v]
            elif k in cls.__dataclass_fields__:
                setattr(s, k, v)
        if "sov_raw" not in d:
            s.sov_raw = s.sov_earned   # pre-endless saves: every point was base
        while len(s.ventures) < n_ventures:
            s.ventures.append(VentureState())
        del s.ventures[n_ventures:]
        return s

    @classmethod
    def new(cls, n_ventures: int) -> "GameState":
        s = cls(ventures=[VentureState() for _ in range(n_ventures)])
        s.ventures[0].owned = 1
        return s
