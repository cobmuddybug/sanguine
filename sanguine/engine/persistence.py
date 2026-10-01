"""Save/load. Atomic writes; a corrupt save is kept as .bak rather than lost."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

from .content import Content
from .game import Game
from .state import GameState


def data_dir() -> Path:
    base = os.environ.get("SANGUINE_HOME") or os.path.join(
        os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share"), "sanguine")
    return Path(base)


def save_path() -> Path:
    return data_dir() / "save.json"


def save_game(game: Game, path: Path | None = None) -> None:
    path = path or save_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    game.s.last_saved = time.time()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(game.s.to_dict()))
    os.replace(tmp, path)


def load_game(content: Content, path: Path | None = None) -> tuple[Game, float, float]:
    """Return (game, offline_seconds, offline_gain). Fresh game if no/corrupt save."""
    path = path or save_path()
    n = len(content.ventures)
    if path.exists():
        try:
            state = GameState.from_dict(json.loads(path.read_text()), n)
        except (ValueError, TypeError, KeyError):
            path.replace(path.with_suffix(".bak"))
        else:
            game = Game(content, state)
            away = max(0.0, time.time() - state.last_saved) if state.last_saved else 0.0
            gain = game.offline(away) if away > 30 else 0.0
            return game, away, gain
    return Game(content), 0.0, 0.0


def reset_save(path: Path | None = None) -> None:
    path = path or save_path()
    if path.exists():
        path.unlink()
