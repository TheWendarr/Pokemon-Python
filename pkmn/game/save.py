"""Whole-game save/load: one JSON file holding the GameState."""
from __future__ import annotations

import json
import os

from ..data.repository import GameData
from .state import GameState

DEFAULT_PATH = "save.json"


def save_game(state: GameState, path: str = DEFAULT_PATH) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state.to_dict(), f, indent=1)
    os.replace(tmp, path)


def load_game(data: GameData, path: str = DEFAULT_PATH) -> GameState | None:
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return GameState.from_dict(data, json.load(f))
