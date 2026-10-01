"""Infernal voice: how the UI's text drifts after the compact is signed (machine_level 0..6)."""
from __future__ import annotations

import re

RENAMES = {
    "BLOOD": "OFFERING", "† / SEC": "TRIBUTE", "FRENZY": "RAPTURE",
    "SIN": "DEBT", "INQUISITION": "ATTENTION", "POTENCY": "COMMUNION",
}


def label(text: str, level: int) -> str:
    """HUD labels: renamed from level 2."""
    return RENAMES.get(text, text) if level >= 2 else text


def tab(text: str, level: int) -> str:
    return text.lower() if level >= 4 else text


def line(text: str, level: int) -> str:
    """Log / ticker lines."""
    if level <= 0:
        return text
    if level == 1:
        return "[it] " + text
    out = text
    if level >= 3:
        out = re.sub(r"\byour\b", "its", out, flags=re.I)
        out = re.sub(r"\byou\b", "the vessel", out, flags=re.I)
        out = out.lower().rstrip(".")
    return out
