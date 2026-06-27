"""Phase 8 integration: the eventlab demo exercised through the real
overworld -- deferred spawn autorun, a parallel move-route, and multi-page
event resolution. Needs the dataset (Game loads GameData)."""
import os

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pytest

pytest.importorskip("pygame")
pytest.importorskip("pytmx")

from pkmn.game.overworld import OverworldScene           # noqa: E402
from pkmn.game.scene import Game                          # noqa: E402
from pkmn.game.script import resolve_script               # noqa: E402

pytestmark = pytest.mark.skipif(
    not os.path.exists("game/data/species"),
    reason="needs the generated full dataset")

LAB = "examples/eventlab"


@pytest.fixture
def ow():
    g = Game(headless=True, seed=3, game_dir=LAB)
    o = OverworldScene(g)
    g.push(o)
    yield g, o
    import pygame
    pygame.quit()


def test_parallel_move_route_walks_npc(ow):
    g, o = ow
    walker = o.find_npc("Walker")
    assert walker is not None
    # the parallel `wander` trigger fired on load and enqueued a route
    assert walker.path, "parallel move_route did not start the NPC walking"


def test_spawn_autorun_is_deferred_then_fires(ow):
    g, o = ow
    # autorun on the spawn map is deferred until the scene is active...
    assert o._pending_entry is not None
    assert o.script is None
    o.update()                                   # first active frame
    # ...now it has fired (its first `say` is on screen, script is running)
    assert o._pending_entry is None
    assert o.script is not None
    assert "intro_seen" not in g.state.flags      # set only after the dialog


def test_prof_multipage_gives_starter_once(ow):
    g, o = ow
    defn = o.scripts["prof"]
    key = "lab:npc:Prof. Birch"
    first = resolve_script(defn, g.state, key)
    assert any("give_pokemon" in s for s in first)   # page 0: hand out starter
    g.state.self_switches.add(f"{key}:A")            # as the script would
    again = resolve_script(defn, g.state, key)
    assert not any("give_pokemon" in s for s in again)  # page 1: just chat
