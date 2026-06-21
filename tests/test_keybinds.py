"""Configurable input: defaults, persistence, key resolution, and the
in-game rebinding menu."""
import os

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import json                                                # noqa: E402

import pytest                                              # noqa: E402

pytest.importorskip("pygame")

import pygame                                              # noqa: E402

pygame.init()

from pkmn.game import keybinds                             # noqa: E402
from pkmn.game.config import A, B, START, UP               # noqa: E402

_REAL = os.path.exists("game/data/species")


def _read(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def test_default_bindings_cover_all_actions():
    b = keybinds.default_bindings()
    assert set(b) == set(keybinds.ACTION_IDS)
    assert keybinds.label(A) == "Confirm"
    assert keybinds.label(B) == "Cancel"
    assert "Select" in dict(keybinds.ACTIONS).values()


def test_normalize_merges_and_cleans():
    merged = keybinds.normalize({A: ["k"], "bogus": ["q"], UP: []})
    assert merged[A] == ["k"]                       # override kept
    assert "bogus" not in merged                    # unknown action dropped
    assert merged[UP] == []                         # present-but-empty: unbound
    assert merged[START] == keybinds.DEFAULT_BINDINGS[START]   # missing -> default


def test_save_load_roundtrip(tmp_path):
    path = str(tmp_path / "controls.json")
    keybinds.save(keybinds.rebind(keybinds.default_bindings(), A, "enter"), path)
    assert keybinds.load(path)[A] == ["enter"]
    # a missing file falls back to defaults
    assert keybinds.load(str(tmp_path / "nope.json")) == keybinds.default_bindings()


def test_resolve_maps_keycodes():
    km = keybinds.resolve(keybinds.default_bindings())
    assert km[pygame.K_z] == A
    assert km[pygame.K_RETURN] == START
    assert km[pygame.K_w] == UP


def test_resolve_skips_unknown_key_names():
    km = keybinds.resolve({A: ["space", "definitely-not-a-key"]})
    assert km[pygame.K_SPACE] == A
    assert all(isinstance(k, int) for k in km)      # bad name didn't crash


def test_rebind_steals_key_from_others():
    out = keybinds.rebind(keybinds.default_bindings(), A, "w")  # 'w' was Up
    assert out[A] == ["w"]
    assert "w" not in out[UP]


@pytest.mark.skipif(not _REAL, reason="needs full game data + region")
def test_game_apply_bindings_persists(tmp_path):
    from pkmn.game.scene import Game
    path = str(tmp_path / "controls.json")
    g = Game(headless=True, seed=1, controls_path=path)
    g.apply_bindings(keybinds.rebind(g.bindings, A, "return"))
    assert g.keymap[pygame.K_RETURN] == A            # live keymap updated
    assert _read(path)[A] == ["return"]              # written to disk
    pygame.quit()


@pytest.mark.skipif(not _REAL, reason="needs full game data + region")
def test_controls_scene_rebind_and_abort(tmp_path):
    from pkmn.game.menus import ControlsScene
    from pkmn.game.scene import Game

    def inp(pressed=(), raw=()):
        return type("I", (), {"pressed": set(pressed), "held": set(),
                              "raw": set(raw)})()

    path = str(tmp_path / "controls.json")
    g = Game(headless=True, seed=1, controls_path=path)
    sc = ControlsScene(g)
    g.push(sc)
    sc.cursor = keybinds.ACTION_IDS.index(A)

    sc.handle(inp(pressed={A}))                       # Confirm -> binding mode
    assert sc.binding
    sc.handle(inp(raw={pygame.key.key_code("k")}))    # press 'k' -> binds
    assert not sc.binding
    assert g.bindings[A] == ["k"]
    assert g.keymap[pygame.key.key_code("k")] == A
    assert _read(path)[A] == ["k"]                   # saved

    sc.handle(inp(pressed={A}))                       # rebind again...
    assert sc.binding
    sc.handle(inp(raw={pygame.key.key_code("escape")}))   # ...Esc aborts
    assert not sc.binding
    assert g.bindings[A] == ["k"]                     # unchanged

    reset = sc.rows.index("__reset__")
    sc.cursor = reset
    sc.handle(inp(pressed={A}))                       # Reset row
    assert g.bindings == keybinds.default_bindings()
    pygame.quit()
