"""Loads game content (ventures, milestones, headlines) from TOML data files."""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

CONTENT_DIR = Path(__file__).resolve().parent.parent / "content"


@dataclass(frozen=True)
class VentureDef:
    idx: int
    id: str
    name: str
    cycle: float
    base_cost: float
    growth: float
    base_payout: float
    proxy_name: str
    proxy_blurb: str
    proxy_cost: float
    flavour: tuple[str, ...]
    plain: str = ""   # layman explanation of what this venture is

    def flavour_for(self, exits: int) -> str:
        return self.flavour[min(exits, len(self.flavour) - 1)]


@dataclass(frozen=True)
class Milestone:
    units: int
    mult: float
    name: str


@dataclass(frozen=True)
class UpgradeDef:
    id: str
    name: str
    kind: str       # "venture" | "global" | "heat" | "hyper"
    target: int     # venture index, -1 for global
    mult: float
    cost: float
    desc: str
    flavour: str
    currency: str = "capital"   # "capital" | "narrative"


@dataclass
class Content:
    ventures: list[VentureDef]
    milestones: list[Milestone]
    global_milestones: list[Milestone] = field(default_factory=list)
    upgrades: list[UpgradeDef] = field(default_factory=list)
    events: list[dict] = field(default_factory=list)
    dossiers: list[dict] = field(default_factory=list)
    branches: list[dict] = field(default_factory=list)
    nodes: list[dict] = field(default_factory=list)
    endless: list[dict] = field(default_factory=list)
    perks: list[dict] = field(default_factory=list)
    ages: list[dict] = field(default_factory=list)
    hunts: list[dict] = field(default_factory=list)
    weeklies: list[dict] = field(default_factory=list)
    feats: list[dict] = field(default_factory=list)
    titles: list[dict] = field(default_factory=list)
    headlines: dict = field(default_factory=dict)
    extra: dict = field(default_factory=dict)  # other loaded tables, keyed by file stem


def _load(name: str) -> dict:
    with open(CONTENT_DIR / name, "rb") as f:
        return tomllib.load(f)


def load_content() -> Content:
    v = _load("ventures.toml")
    factor = v.get("economy", {}).get("proxy_cost_factor", 250.0)
    ventures = [
        VentureDef(
            idx=i, id=d["id"], name=d["name"], cycle=float(d["cycle"]),
            base_cost=float(d["base_cost"]), growth=float(d["growth"]),
            base_payout=float(d["base_payout"]), proxy_name=d["proxy_name"],
            proxy_blurb=d["proxy_blurb"],
            proxy_cost=float(d.get("proxy_cost", d["base_cost"] * factor)),
            flavour=tuple(d["flavour"]), plain=d.get("plain", ""),
        )
        for i, d in enumerate(v["venture"])
    ]
    milestones = [Milestone(m["units"], float(m["mult"]), m["name"]) for m in v["milestone"]]
    gms = [Milestone(m["units"], float(m["mult"]), m["name"]) for m in v.get("global_milestone", [])]
    ups = [UpgradeDef(u["id"], u["name"], u["kind"], int(u["target"]), float(u["mult"]), float(u["cost"]),
                      u["desc"], u["flavour"], u.get("currency", "capital")) for u in _load("upgrades.toml")["upgrade"]]
    content = Content(ventures, milestones, gms, ups, headlines=_load("headlines.toml"))
    content.events = _load("events.toml")["event"]
    content.dossiers = _load("dossiers.toml")["dossier"]
    tree = _load("sovereignty.toml")
    content.branches, content.nodes = tree["branch"], tree["node"]
    content.endless = tree.get("endless", [])
    content.perks = _load("dynasty.toml")["perk"]
    content.ages = _load("ages.toml")["age"]
    hunts = _load("hunts.toml")
    content.hunts, content.weeklies = hunts["hunt"], hunts["weekly"]
    annals = _load("annals.toml")
    content.feats, content.titles = annals["feat"], annals["title"]
    return content
