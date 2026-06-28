"""Acceptance tests for A1: TitleScene (new-game / continue shell)."""
import json
import os
import tempfile

import pytest

from pkmn.game.overworld import OverworldScene
from pkmn.game.scene import Game
from pkmn.game.title import TitleScene
from pkmn.game.config import A, START


def _make_game(**kw):
    defaults = dict(headless=True, seed=7, game_dir="examples/triad")
    defaults.update(kw)
    return Game(**defaults)


# ── startup ──────────────────────────────────────────────────────────

def test_title_scene_is_pushed_by_play():
    """play.py pushes TitleScene; the scene stack starts there."""
    g = _make_game()
    g.push(TitleScene(g))
    assert isinstance(g.top, TitleScene)


def test_title_scene_draws():
    g = _make_game()
    g.push(TitleScene(g))
    g.draw()  # must not raise


# ── press START -> menu ───────────────────────────────────────────────

def test_press_start_reveals_menu():
    g = _make_game()
    g.push(TitleScene(g))
    title = g.top
    assert title._phase == "start"
    g.input.press(START)
    g.tick()
    assert title._phase == "menu"


def test_press_a_reveals_menu():
    g = _make_game()
    g.push(TitleScene(g))
    title = g.top
    g.input.press(A)
    g.tick()
    assert title._phase == "menu"


# ── new game ─────────────────────────────────────────────────────────

def test_new_game_lands_in_overworld():
    g = _make_game()
    g.push(TitleScene(g))
    # press START to open menu
    g.input.press(START)
    g.tick()
    # cursor is on "NEW GAME"; press A
    g.input.press(A)
    g.tick()
    assert isinstance(g.top, OverworldScene)


def test_new_game_resets_party():
    """Selecting NEW GAME rebuilds a fresh GameState (fresh party)."""
    g = _make_game()
    original_party = list(g.state.party)
    g.state.party.clear()           # simulate a modified state
    g.push(TitleScene(g))
    g.input.press(START)
    g.tick()
    g.input.press(A)
    g.tick()
    # party rebuilt from manifest
    assert len(g.state.party) == len(original_party)


# ── continue ─────────────────────────────────────────────────────────

def test_continue_option_absent_without_save():
    g = _make_game()  # no save_path set → no save exists
    g.push(TitleScene(g))
    title = g.top
    assert "CONTINUE" not in title._options


def test_continue_option_present_with_save():
    with tempfile.TemporaryDirectory() as td:
        save_path = os.path.join(td, "save.json")
        # create a save by booting and saving
        g0 = _make_game(save_path=save_path)
        from pkmn.game.save import save_game
        save_game(g0.state, save_path)

        g = _make_game(save_path=save_path)
        g.push(TitleScene(g))
        title = g.top
        assert "CONTINUE" in title._options


def test_continue_resumes_saved_location():
    """Continue after saving: map_id and party are restored."""
    with tempfile.TemporaryDirectory() as td:
        save_path = os.path.join(td, "save.json")
        g0 = _make_game(save_path=save_path)
        # advance into the overworld so map_id is set
        from pkmn.game.overworld import OverworldScene
        g0.push(OverworldScene(g0))
        for _ in range(3):
            g0.tick()
        saved_map = g0.state.map_id
        from pkmn.game.save import save_game
        save_game(g0.state, save_path)

        # reload via TitleScene -> CONTINUE
        g = _make_game(save_path=save_path)
        g.push(TitleScene(g))
        g.input.press(START)
        g.tick()
        # navigate to CONTINUE (it's index 1 if present)
        title = g.top
        from pkmn.game.config import DOWN
        if title._cursor != title._options.index("CONTINUE"):
            g.input.press(DOWN)
            g.tick()
        g.input.press(A)
        g.tick()
        assert isinstance(g.top, OverworldScene)
        assert g.state.map_id == saved_map
