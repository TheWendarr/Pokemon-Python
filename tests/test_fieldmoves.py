"""Field moves driven by tile flags + capability flags: surf (water),
one-way ledges (a two-tile hop), and cut (clearing an obstacle). Each is
gated by a `can_*` capability the manifest grants like an HM. Exercised
on the 'Vale' demo region, whose tileset declares surf water, a
ledge_down tile, and a cuttable bush, and which grants both capabilities.
"""
import os
from types import SimpleNamespace

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pytest

pytest.importorskip("pygame")
pytest.importorskip("pytmx")

from pkmn.game.config import A, DOWN, UP, RIGHT       # noqa: E402
from pkmn.game.overworld import OverworldScene         # noqa: E402
from pkmn.game.scene import Game                       # noqa: E402

pytestmark = pytest.mark.skipif(
    not os.path.exists("game/data/species"),
    reason="needs the generated dataset")

GAME = "examples/seamless"


@pytest.fixture
def ow():
    # a fresh game per test: cut writes a session override on the cached
    # map, so tests must not share a World
    g = Game(headless=True, seed=5, game_dir=GAME)
    o = OverworldScene(g)
    g.push(o)
    yield g, o
    import pygame
    pygame.quit()


def _place(o, g, mid, tile, facing):
    o.load_map(mid, tile)
    g.state.tile = tuple(tile)
    g.state.facing = facing


def _find(mp, pred):
    return next((x, y) for y in range(mp.height) for x in range(mp.width)
                if pred(mp, x, y))


def _step(o, g, key, n=80):
    start = g.state.tile
    inp = SimpleNamespace(held={key}, pressed=set())
    for _ in range(n):
        o.handle(inp)
        o.update()
        if g.state.tile != start and not o.moving and not o.jump:
            return
    # may legitimately not move (a blocked direction)


def _press_a(o, g):
    o.handle(SimpleNamespace(held=set(), pressed={A}))
    o.update()


def test_capabilities_come_from_the_manifest(ow):
    g, o = ow
    assert g.state.can_surf and g.state.can_cut


def test_surf_enters_water_and_returns_to_land(ow):
    g, o = ow
    _place(o, g, "glade", (1, 1), "down")
    wx, wy = _find(o.map, lambda m, x, y: m.is_surf(x, y))
    _place(o, g, "glade", (wx, wy - 1), "down")
    assert not o.surfing
    _step(o, g, DOWN)
    assert g.state.tile == (wx, wy) and o.surfing      # riding the water
    _step(o, g, UP)
    assert g.state.tile == (wx, wy - 1) and not o.surfing


def test_surf_is_blocked_without_capability(ow):
    g, o = ow
    g.state.flags.discard("can_surf")
    _place(o, g, "glade", (1, 1), "down")
    wx, wy = _find(o.map, lambda m, x, y: m.is_surf(x, y))
    _place(o, g, "glade", (wx, wy - 1), "down")
    _step(o, g, DOWN)
    assert g.state.tile == (wx, wy - 1) and not o.surfing


def test_ledge_is_a_one_way_two_tile_hop(ow):
    g, o = ow
    _place(o, g, "meadow", (1, 1), "down")
    lx, ly = _find(o.map, lambda m, x, y: m.has_ledge(x, y, "down"))
    # hop over it from above -> land two tiles down
    _place(o, g, "meadow", (lx, ly - 1), "down")
    _step(o, g, DOWN)
    assert g.state.tile == (lx, ly + 1)
    # cannot climb it from below
    _place(o, g, "meadow", (lx, ly + 1), "up")
    _step(o, g, UP)
    assert g.state.tile == (lx, ly + 1)


def test_cut_clears_an_obstacle_with_the_capability(ow):
    g, o = ow
    _place(o, g, "dell", (1, 1), "down")
    cx, cy = _find(o.map, lambda m, x, y: m.is_cuttable(x, y))
    assert o.map.blocked(cx, cy)
    _place(o, g, "dell", (cx - 1, cy), "right")
    _press_a(o, g)
    assert not o.map.blocked(cx, cy)                   # now walkable
    _step(o, g, RIGHT)
    assert g.state.tile == (cx, cy)


def test_cut_is_blocked_without_capability(ow):
    g, o = ow
    g.state.flags.discard("can_cut")
    _place(o, g, "dell", (1, 1), "down")
    cx, cy = _find(o.map, lambda m, x, y: m.is_cuttable(x, y))
    _place(o, g, "dell", (cx - 1, cy), "right")
    _press_a(o, g)
    assert o.map.blocked(cx, cy)                       # untouched
