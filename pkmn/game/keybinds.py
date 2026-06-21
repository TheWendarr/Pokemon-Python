"""Configurable input.

The engine talks in *logical actions* (short strings like ``"a"``, ``"up"``)
so nothing downstream cares which physical key was pressed. This module owns
the mapping from keyboard keys to those actions: sensible defaults, a JSON
file the player can edit, and small helpers the in-game rebinding menu uses.
Player-facing names (Confirm / Cancel / ...) live here too; the internal
action ids are left untouched for backwards compatibility.

Bindings are stored by pygame *key name* (e.g. ``"space"``, ``"left shift"``)
rather than numeric keycodes, so the config file is human-readable and
portable.
"""
from __future__ import annotations

import json
import os

import pygame

from .config import A, B, DOWN, LEFT, RIGHT, START, UP

SELECT = "select"

# Display order + player-facing label for every logical action.
ACTIONS = [
    (UP, "Up"), (DOWN, "Down"), (LEFT, "Left"), (RIGHT, "Right"),
    (A, "Confirm"), (B, "Cancel"), (START, "Start"), (SELECT, "Select"),
]
ACTION_IDS = [a for a, _ in ACTIONS]
_LABELS = dict(ACTIONS)

# Default key names per action (pygame key names; more than one is allowed).
DEFAULT_BINDINGS = {
    UP:     ["up", "w"],
    DOWN:   ["down", "s"],
    LEFT:   ["left", "a"],
    RIGHT:  ["right", "d"],
    A:      ["z", "space"],
    B:      ["x", "backspace", "escape"],
    START:  ["return"],
    SELECT: ["right shift"],
}

# Keys the engine keeps for itself and never offers for rebinding.
RESERVED = {"f11"}


def label(action: str) -> str:
    return _LABELS.get(action, action.title())


def default_bindings() -> dict:
    return {a: list(keys) for a, keys in DEFAULT_BINDINGS.items()}


def normalize(bindings: dict | None) -> dict:
    """Merge a partial/loaded mapping over the defaults, keeping only known
    actions and non-empty, lower-cased key-name lists."""
    out = default_bindings()
    for action, keys in (bindings or {}).items():
        if action in out and isinstance(keys, (list, tuple)):
            out[action] = [str(k).lower() for k in keys if str(k).strip()]
    return out


def load(path: str | None) -> dict:
    if path and os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return normalize(json.load(f))
        except (OSError, ValueError):
            pass
    return default_bindings()


def save(bindings: dict, path: str | None) -> None:
    if not path:
        return
    with open(path, "w", encoding="utf-8") as f:
        json.dump(bindings, f, indent=2, sort_keys=True)


def resolve(bindings: dict) -> dict:
    """Build the ``{keycode: action}`` map the event pump consumes. Unknown
    key names are skipped rather than raising."""
    keymap = {}
    for action, keys in bindings.items():
        for name in keys:
            try:
                keymap[pygame.key.key_code(name)] = action
            except (ValueError, TypeError):
                continue
    return keymap


def key_name(code: int) -> str:
    try:
        return pygame.key.name(code)
    except Exception:
        return "?"


def keys_label(bindings: dict, action: str) -> str:
    return " / ".join(bindings.get(action, [])) or "(unbound)"


def rebind(bindings: dict, action: str, new_key: str) -> dict:
    """Bind ``action`` to a single key, removing that key from every other
    action so two actions never collide."""
    name = new_key.lower()
    out = {a: [k for k in keys if k != name] for a, keys in bindings.items()}
    out[action] = [name]
    return out
