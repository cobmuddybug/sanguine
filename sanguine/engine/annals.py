"""Annals: achievements. Each feat earned adds +2% to all output; the count sets your title."""
from __future__ import annotations

import math

FEAT_BONUS = 0.02


class AnnalsMixin:
    def annals_mult(self) -> float:
        return 1.0 + FEAT_BONUS * len(self.s.feats)

    def title(self) -> str:
        n = len(self.s.feats)
        name = self.c.titles[0]["name"]
        for t in self.c.titles:
            if n >= t["at"]:
                name = t["name"]
        return name

    def _bump(self, key: str, value: float) -> float:
        st = self.s.stats
        if value > st.get(key, 0):
            st[key] = value
        return st.get(key, 0)

    def annal_stat(self, stat: str) -> float:
        s = self.s
        if stat == "exits":
            return s.exits
        if stat == "play_hours":
            return s.play_time / 3600.0
        if stat == "clicks":
            return s.clicks
        if stat == "maxlog":
            return self._bump("maxlog", math.log10(max(s.lifetime_capital, 1.0)))
        if stat == "tier":
            return self._bump("tier", max((i + 1 for i, v in enumerate(s.ventures) if v.owned), default=0))
        if stat == "units_total":
            return self._bump("units_total", sum(v.owned for v in s.ventures))
        if stat == "dossiers":
            return len(s.dossiers)
        if stat == "events_seen":
            return s.events_seen
        if stat == "machine_level":
            return s.machine_level
        if stat == "endless_levels":
            return self._bump("endless_levels", sum(s.endless.values()))
        if stat == "dynasties":
            return s.dynasties
        if stat == "lineage_earned":
            return s.lineage_earned
        if stat == "ages_done":
            return s.ages_done
        if stat == "hunts_done":
            return s.hunts_done
        return 0

    def feat_done(self, f: dict) -> bool:
        return f["id"] in self.s.feats

    def feat_progress(self, f: dict) -> tuple[float, float]:
        return min(self.annal_stat(f["stat"]), f["at"]), f["at"]

    def _annals_tick(self) -> None:
        for f in self.c.feats:
            if f["id"] not in self.s.feats and self.annal_stat(f["stat"]) >= f["at"]:
                self.s.feats.append(f["id"])
                self.log(f"Annal inscribed: '{f['name']}'. (+{FEAT_BONUS * 100:g}% output)")
                if self.on_notify:
                    self.on_notify(f"Annal: {f['name']}")
