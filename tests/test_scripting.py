"""Phase 4: event scripting — flags, triggers, the script command set,
trainer line-of-sight battles, the scripted rival fight, and interiors."""
import os

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pytest

pytest.importorskip("pygame")
pytest.importorskip("pytmx")

from pkmn.game.battle_scene import BattleScene      # noqa: E402
from pkmn.game.config import A, UP                  # noqa: E402
from pkmn.game.dialog import DialogScene            # noqa: E402
from pkmn.game.overworld import OverworldScene, Trainer  # noqa: E402
from pkmn.game.scene import Game                    # noqa: E402
from pkmn.game.script import DONE, ScriptRunner     # noqa: E402

pytestmark = pytest.mark.skipif(
    not os.path.exists("game/data/species"),
    reason="needs the generated full dataset")


@pytest.fixture
def game():
    g = Game(headless=True, seed=21)
    g.push(OverworldScene(g))
    g.state.party[0].level = 30          # rebind below for stat recalc
    g.state.party[0].current_hp = -1
    g.state.party[0].bind(g.state.data)
    yield g
    import pygame
    pygame.quit()


def press(g, key):
    g.input.press(key)
    g.tick()
    g.input.release(key)


def walk(g, direction, tiles):
    ow = g.scenes[0]
    moved = 0
    for _ in range(tiles * 80):
        if not isinstance(g.top, OverworldScene):
            return
        before = (g.state.map_id, g.state.tile)
        press(g, direction)
        if (g.state.map_id, g.state.tile) != before and not ow.moving:
            moved += 1
            if moved >= tiles:
                return


def mash_until(g, predicate, frames=6000):
    for _ in range(frames):
        if predicate():
            return True
        press(g, A)
        g.draw()
    return False


# ── script interpreter (no scenes needed) ────────────────────────────

def test_script_flags_items_money_conditionals(game):
    ow = game.scenes[0]
    st = game.state
    runner = ScriptRunner(game, ow, [
        {"set_flag": "met_prof"},
        {"give_item": {"item": "potion", "qty": 3}},
        {"give_money": 250},
        {"if_flag": "met_prof",
         "then": [{"set_flag": "branch_then"}],
         "else": [{"set_flag": "branch_else"}]},
        {"clear_flag": "met_prof"},
    ])
    assert runner.advance() == DONE
    assert "branch_then" in st.flags and "branch_else" not in st.flags
    assert "met_prof" not in st.flags
    assert st.bag["potion"] == 5 + 3
    assert st.money == 1500 + 250


def test_script_warp_command(game):
    ow = game.scenes[0]
    runner = ScriptRunner(game, ow, [
        {"warp": {"map": "house", "x": 4, "y": 4, "facing": "up"}}])
    assert runner.advance() == DONE
    assert game.state.map_id == "house" and game.state.tile == (4, 4)


# ── doors / interiors ────────────────────────────────────────────────

def test_door_into_house_and_back(game):
    game.state.tile = (6, 7)
    game.state.facing = "up"
    walk(game, "up", 1)
    assert game.state.map_id == "house"
    assert game.state.tile == (4, 4)
    walk(game, "down", 2)                # step onto the exit mat
    assert game.state.map_id == "town"
    assert game.state.tile == (6, 7)


def test_nurse_heals_via_script(game):
    ow = game.scenes[0]
    ow.load_map("house")
    game.state.party[0].current_hp = 3
    game.state.tile = (5, 2)             # beside Nurse Hazel at (4, 2)
    game.state.facing = "left"
    press(game, A)
    assert isinstance(game.top, DialogScene)
    assert mash_until(game, lambda: isinstance(game.top, OverworldScene)
                      and ow.script is None, 200)
    assert game.state.party[0].current_hp == game.state.party[0].max_hp


# ── trainer line-of-sight ────────────────────────────────────────────

def test_trainer_los_battle_flag_and_no_rebattle(game):
    ow = game.scenes[0]
    game.state.flags.add("beat_rival")   # keep the rival out of this test
    ow.load_map("route1")
    money = game.state.money
    game.state.tile = (18, 13)
    game.state.facing = "up"
    walk(game, "up", 1)                  # arrive (18,12): in Cole's sight
    assert ow.cutscene is not None       # "!" pause begins
    assert mash_until(game, lambda: isinstance(game.top, BattleScene), 600)
    b = game.top
    assert not b.eng.wild
    assert mash_until(game, lambda: isinstance(game.top, OverworldScene)
                      and ow.script is None)
    assert b.eng.winner == "p1"
    assert "beat_cole" in game.state.flags
    assert game.state.money == money + 300
    cole = next(n for n in ow.npcs if isinstance(n, Trainer))
    assert abs(cole.tile[1] - game.state.tile[1]) == 1   # walked adjacent
    # re-entering the sight line must not trigger again
    walk(game, "down", 1)
    walk(game, "up", 1)
    assert ow.cutscene is None and isinstance(game.top, OverworldScene)
    # interacting now gives the post-defeat line
    game.state.facing = "up"
    press(game, A)
    assert isinstance(game.top, DialogScene)
    mash_until(game, lambda: isinstance(game.top, OverworldScene), 100)


# ── the scripted rival battle (Phase 4 acceptance) ───────────────────

def test_rival_battle_pre_post_dialogue_gated_by_flags(game):
    ow = game.scenes[0]
    ow.load_map("route1")
    money = game.state.money
    potions = game.state.bag.get("potion", 0)
    game.state.tile = (11, 6)
    game.state.facing = "up"
    walk(game, "up", 1)                  # step onto the trigger tile
    assert isinstance(game.top, DialogScene)         # pre-battle dialogue
    assert mash_until(game, lambda: isinstance(game.top, BattleScene), 400)
    b = game.top
    assert not b.eng.wild
    assert b.eng.active("p2").state.species_id == "snivy"
    assert mash_until(game, lambda: isinstance(game.top, OverworldScene)
                      and ow.script is None)
    assert b.eng.winner == "p1"
    assert "beat_rival" in game.state.flags          # flag gate set
    assert game.state.money == money + 500
    assert game.state.bag["potion"] == potions + 2   # scripted reward
    # stepping on the trigger again is now gated off by the flag
    walk(game, "down", 1)
    walk(game, "up", 1)
    assert isinstance(game.top, OverworldScene) and ow.script is None
    # post dialogue on interaction, gated by the same flag
    hugh = ow.find_npc("Hugh")
    game.state.tile = (hugh.tile[0] - 1, hugh.tile[1])
    game.state.facing = "right"
    press(game, A)
    assert isinstance(game.top, DialogScene)
    mash_until(game, lambda: isinstance(game.top, OverworldScene), 100)
