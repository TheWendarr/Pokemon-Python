"""Headless client tests (SDL dummy drivers). These drive the real Game
object frame by frame through the Input abstraction — no window needed."""
import itertools
import os
import random

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pytest

pytest.importorskip("pygame")
pytest.importorskip("pytmx")

from pkmn.core.pokemon import PokemonState          # noqa: E402
from pkmn.game.battle_scene import BattleScene      # noqa: E402
from pkmn.game.config import A, DOWN, RIGHT, UP     # noqa: E402
from pkmn.game.dialog import DialogScene            # noqa: E402
from pkmn.game.overworld import OverworldScene      # noqa: E402
from pkmn.game.scene import Game                    # noqa: E402

pytestmark = pytest.mark.skipif(
    not os.path.exists("game/data/species"),
    reason="needs the generated full dataset (run pkmn.datagen.fetch)")


@pytest.fixture
def game():
    g = Game(headless=True, seed=11)
    g.push(OverworldScene(g))
    yield g
    import pygame
    pygame.quit()


def walk(g, direction, tiles):
    """Hold a direction until `tiles` grid arrivals happen (or a battle
    interrupts / the way is blocked). Counts arrivals instead of frames
    so turn-in-place and full-tile commitment don't skew the math."""
    ow = g.scenes[0]
    moved = 0
    for _ in range(tiles * 80):
        if isinstance(g.top, BattleScene):
            return
        before = (g.state.map_id, g.state.tile)
        g.input.press(direction)
        g.tick()
        g.input.release(direction)
        if (g.state.map_id, g.state.tile) != before and not ow.moving:
            moved += 1
            if moved >= tiles:
                return


def press(g, key):
    g.input.press(key)
    g.tick()
    g.input.release(key)


# ── world ────────────────────────────────────────────────────────────

def test_map_loads_with_queries_and_objects(game):
    ow = game.top
    assert ow.map.id == "town"
    assert game.state.tile == (11, 13)          # spawn object honored
    assert ow.map.blocked(0, 0)                 # border tree
    assert not ow.map.blocked(11, 12)           # path
    assert len(ow.map.npcs) == 2
    assert (11, 0) in ow.map.warps


def test_collision_blocks_movement(game):
    game.state.tile = (1, 1)                    # next to the tree border
    walk(game, UP, 1)
    assert game.state.tile == (1, 1)            # tree said no


def test_warp_transitions_between_maps(game):
    walk(game, UP, 14)
    assert game.state.map_id == "route1"
    walk(game, DOWN, 3)
    assert game.state.map_id == "town"          # and back again


def test_grass_encounter_pushes_battle(game):
    ow = game.top
    assert ow.map.id == "town"
    walk(game, UP, 14)
    walk(game, UP, 11)                          # row ~3-5, beside tall grass
    for i in itertools.count():
        if isinstance(game.top, BattleScene):
            break
        assert i < 6000, "no encounter after extensive pacing"
        d = "left" if (i // 40) % 2 == 0 else "right"
        press(game, d)
    b = game.top
    assert b.eng.wild
    assert b.eng.active("p2").level >= 3


# ── battle UI ────────────────────────────────────────────────────────

def _wild_battle(game, species="patrat", level=3):
    wild = PokemonState.generate(game.state.data, species, level,
                                 rng=game.state.rng)
    scene = BattleScene(game, [wild], wild=True)
    game.push(scene)
    return scene


def test_battle_mash_fight_to_victory(game):
    b = _wild_battle(game, "patrat", 2)
    for i in range(4000):
        if not isinstance(game.top, BattleScene):
            break
        press(game, A)                           # msg -> FIGHT -> move 1
        game.draw()                              # exercise every render mode
    assert b.eng.over and b.eng.winner == "p1"
    assert isinstance(game.top, OverworldScene)


class _CatchRig(random.Random):
    """Force every catch shake check to pass; leave the rest alone."""
    def randint(self, a, b):
        if (a, b) == (0, 65535):
            return 0
        return super().randint(a, b)


def test_catching_adds_to_party(game):
    game.state.rng = _CatchRig(3)
    b = _wild_battle(game, "patrat", 3)
    for i in range(600):
        if not isinstance(game.top, BattleScene):
            break
        if b.mode == "menu":
            if b.cursor == 0:
                press(game, RIGHT)               # FIGHT -> BAG
            else:
                press(game, A)
        else:
            press(game, A)                       # bag: poke-ball is first
    assert b.eng.winner == "caught"
    assert len(game.state.party) == 2
    assert game.state.party[1].species_id == "patrat"
    assert game.state.bag["poke-ball"] == 9


def test_whiteout_heals_and_returns_home(game):
    starter = game.state.party[0]
    starter.current_hp = 1
    b = _wild_battle(game, "patrat", 40)         # hopeless matchup
    for i in range(4000):
        if not isinstance(game.top, BattleScene):
            break
        press(game, A)
    assert b.eng.winner == "p2"
    assert game.state.map_id == "town"
    assert starter.current_hp == starter.max_hp  # healed on whiteout


# ── dialog / NPCs ────────────────────────────────────────────────────

def test_npc_dialog_and_nurse_heal(game):
    ow = game.top
    game.state.party[0].current_hp = 3
    nurse = next(n for n in ow.npcs if n.heal)
    game.state.tile = (nurse.tile[0], nurse.tile[1] + 1)
    game.state.facing = "up"
    press(game, A)
    assert isinstance(game.top, DialogScene)
    assert nurse.facing == "down"                # turned to face the player
    for _ in range(10):
        if not isinstance(game.top, DialogScene):
            break
        press(game, A)
        game.draw()
    assert isinstance(game.top, OverworldScene)
    assert game.state.party[0].current_hp == game.state.party[0].max_hp


def test_sign_reads(game):
    game.state.tile = (9, 9)
    game.state.facing = "up"
    press(game, A)                               # sign at (9, 8)
    assert isinstance(game.top, DialogScene)


# ── grid-movement contract ───────────────────────────────────────────

def test_tap_turns_in_place_without_stepping(game):
    game.state.tile = (11, 11)
    game.state.facing = "down"
    press(game, UP)                              # single tap, new direction
    for _ in range(20):
        game.tick()
    assert game.state.facing == "up"
    assert game.state.tile == (11, 11)           # turned, did not step


def test_step_commits_to_full_tile(game):
    ow = game.top
    game.state.tile = (11, 11)
    game.state.facing = "up"                     # already facing: tap = step
    press(game, UP)
    assert ow.moving                             # step began on the tap
    for _ in range(3):                           # release + contrary input
        press(game, DOWN)
    for _ in range(20):
        game.tick()
    assert game.state.tile == (11, 10)           # full tile, no partials
    assert ow.move_px == 0 and not ow.moving


def test_hold_walks_tile_by_tile(game):
    game.state.tile = (11, 11)
    game.state.facing = "up"
    for _ in range(8 * 3 + 2):
        game.input.press(UP)
        game.tick()
        game.input.release(UP)
    assert game.state.tile[1] <= 8               # several clean tiles north
    assert game.state.tile[0] == 11              # no lateral drift
