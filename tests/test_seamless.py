"""Seamless overworld: per-edge connections + offsets and the recursive
World.resolve() primitive stitch separate maps into one continuous world
(the headline lift from the Gen 1 map-data video). Driven on the 'Vale'
demo region, whose maps have open grass seams."""
import os
from types import SimpleNamespace

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pytest

pytest.importorskip("pygame")
pytest.importorskip("pytmx")

from pkmn.game.config import DOWN, RIGHT          # noqa: E402
from pkmn.game.overworld import OverworldScene     # noqa: E402
from pkmn.game.scene import Game                   # noqa: E402

pytestmark = pytest.mark.skipif(
    not os.path.exists("game/data/species"),
    reason="needs the generated dataset")

GAME = "examples/seamless"


@pytest.fixture
def ow():
    g = Game(headless=True, seed=3, game_dir=GAME)
    o = OverworldScene(g)
    g.push(o)
    yield g, o
    import pygame
    pygame.quit()


def _hold(o, g, key, stop, limit=1000):
    inp = SimpleNamespace(held={key}, pressed=set())
    for _ in range(limit):
        o.handle(inp)
        o.update()
        if stop(g):
            return True
    return False


def test_maps_declare_connections(ow):
    g, o = ow
    assert o.map.is_seamless
    assert o.map.connections["south"] == ("glade", 0)


def test_resolve_stitches_neighbours_and_borders(ow):
    g, o = ow
    w = o.world
    meadow, glade, dell = w.get("meadow"), w.get("glade"), w.get("dell")
    # north/south align (same width, offset 0)
    assert w.resolve("meadow", 10, meadow.height) == (glade, 10, 0)
    assert w.resolve("glade", 7, -1) == (meadow, 7, meadow.height - 1)
    # east/west carry a vertical offset of +1 / -1 and are reciprocal
    assert w.resolve("glade", glade.width, 5) == (dell, 0, 4)
    assert w.resolve("dell", -1, 4) == (glade, glade.width - 1, 5)
    # an unconnected edge resolves to nothing -> treated as a wall
    assert w.resolve("meadow", -1, 5) is None
    assert w.blocked("meadow", -1, 5)
    # corners chain through two recursions without blowing up
    assert w.resolve("meadow", -1, -1) is None


def test_walking_off_an_edge_crosses_into_the_neighbour(ow):
    g, o = ow
    assert g.state.map_id == "meadow"
    assert _hold(o, g, DOWN, lambda g: g.state.map_id == "glade")
    assert g.state.tile[1] <= 1               # landed at glade's top edge
    assert o.map.id == "glade"                # current map switched


def test_offset_seam_crossing_is_seamless(ow):
    g, o = ow
    # cross into glade and stay in its top rows (above the encounter band)
    # so the walk is deterministic, then cross the offset east seam to dell
    assert _hold(o, g, DOWN, lambda g: g.state.map_id == "glade")
    assert _hold(o, g, DOWN, lambda g: g.state.tile[1] >= 3)
    assert _hold(o, g, RIGHT, lambda g: g.state.map_id == "dell")
    assert o.map.id == "dell"


def test_discrete_region_is_not_seamless():
    # a warp-linked region keeps the clamped single-map path
    g = Game(headless=True, seed=1, game_dir="examples/triad")
    o = OverworldScene(g)
    g.push(o)
    assert not o.map.is_seamless
    import pygame
    pygame.quit()
