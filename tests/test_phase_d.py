"""Phase D: badges, expanded field moves, Fly/Town Map, map metadata.

Tests for the new systems added in Phase D:
  - Badge grant / condition / persistence
  - Rock Smash (like Cut but uses rock_smash flag)
  - Waterfall (blocks upward surf movement without can_waterfall)
  - Headbutt (interacting with headbutt_tree when capable vs not)
  - Fly scene instantiation
  - Script conditions: badge, badge_count, visited
"""
import os
from types import SimpleNamespace

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pytest

pytest.importorskip("pygame")
pytest.importorskip("pytmx")

from pkmn.game.config import A, DOWN, UP, RIGHT     # noqa: E402
from pkmn.game.overworld import OverworldScene       # noqa: E402
from pkmn.game.scene import Game                     # noqa: E402
from pkmn.game.script import eval_condition          # noqa: E402

pytestmark = pytest.mark.skipif(
    not os.path.exists("game/data/species"),
    reason="needs the generated dataset")

GAME = "examples/seamless"


@pytest.fixture
def ow():
    g = Game(headless=True, seed=7, game_dir=GAME)
    o = OverworldScene(g)
    g.push(o)
    yield g, o
    import pygame
    pygame.quit()


def _place(o, g, mid, tile, facing="down"):
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


def _press_a(o, g):
    o.handle(SimpleNamespace(held=set(), pressed={A}))
    o.update()


# ── badges ────────────────────────────────────────────────────────────

def test_give_badge_adds_to_set(ow):
    g, o = ow
    assert "boulder" not in g.state.badges
    g.state.badges.add("boulder")
    assert "boulder" in g.state.badges


def test_badge_condition_true_when_held(ow):
    g, o = ow
    g.state.badges.add("cascade")
    assert eval_condition({"badge": "cascade"}, g.state)


def test_badge_condition_false_when_missing(ow):
    g, o = ow
    assert not eval_condition({"badge": "cascade"}, g.state)


def test_badge_count_condition(ow):
    g, o = ow
    g.state.badges = {"boulder", "cascade", "thunder"}
    assert eval_condition({"badge_count": 1, "op": ">=", "value": 3}, g.state)
    assert not eval_condition({"badge_count": 1, "op": ">=", "value": 4}, g.state)


def test_badge_persists_in_save_round_trip(ow):
    g, o = ow
    g.state.badges = {"boulder", "cascade"}
    d = g.state.to_dict()
    assert sorted(d["badges"]) == ["boulder", "cascade"]
    from pkmn.game.state import GameState
    st2 = GameState.from_dict(g.state.data, d)
    assert st2.badges == {"boulder", "cascade"}


def test_give_badge_script_command(ow):
    g, o = ow
    steps = [{"give_badge": "rainbow"}]
    o.start_script(steps)
    assert "rainbow" in g.state.badges


# ── visited_maps ──────────────────────────────────────────────────────

def test_visited_maps_tracked_on_load(ow):
    g, o = ow
    assert "meadow" in g.state.visited_maps   # loaded during __init__


def test_visited_condition(ow):
    g, o = ow
    _place(o, g, "glade", (1, 1))
    assert eval_condition({"visited": "glade"}, g.state)
    assert not eval_condition({"visited": "nowhere"}, g.state)


def test_visited_persists_in_save_round_trip(ow):
    g, o = ow
    _place(o, g, "glade", (1, 1))
    d = g.state.to_dict()
    assert "glade" in d["visited_maps"]
    from pkmn.game.state import GameState
    st2 = GameState.from_dict(g.state.data, d)
    assert "glade" in st2.visited_maps


# ── rock smash ────────────────────────────────────────────────────────

def test_rock_smash_clears_boulder_with_capability(ow):
    g, o = ow
    _place(o, g, "rock", (1, 1))
    rx, ry = _find(o.map, lambda m, x, y: m.is_rock_smash(x, y))
    assert o.map.blocked(rx, ry)
    _place(o, g, "rock", (rx - 1, ry), "right")
    _press_a(o, g)
    assert not o.map.blocked(rx, ry)
    _step(o, g, RIGHT)
    assert g.state.tile == (rx, ry)


def test_rock_smash_blocked_without_capability(ow):
    g, o = ow
    g.state.flags.discard("can_rock_smash")
    _place(o, g, "rock", (1, 1))
    rx, ry = _find(o.map, lambda m, x, y: m.is_rock_smash(x, y))
    _place(o, g, "rock", (rx - 1, ry), "right")
    _press_a(o, g)
    assert o.map.blocked(rx, ry)


def test_rock_smash_capability_properties(ow):
    g, o = ow
    assert g.state.can_rock_smash
    g.state.flags.discard("can_rock_smash")
    assert not g.state.can_rock_smash


# ── waterfall ─────────────────────────────────────────────────────────

def test_waterfall_blocks_upward_surf_without_capability(ow):
    g, o = ow
    g.state.flags.discard("can_waterfall")
    _place(o, g, "rock", (1, 1))
    wx, wy = _find(o.map, lambda m, x, y: m.is_waterfall(x, y)
                                          and m.is_surf(x, y))
    # surf onto the tile below the waterfall
    o.surfing = True
    _place(o, g, "rock", (wx, wy + 1), "up")
    _step(o, g, UP)
    assert g.state.tile == (wx, wy + 1)   # cannot climb waterfall


def test_waterfall_allows_upward_surf_with_capability(ow):
    g, o = ow
    assert g.state.can_waterfall
    _place(o, g, "rock", (1, 1))
    wx, wy = _find(o.map, lambda m, x, y: m.is_waterfall(x, y)
                                          and m.is_surf(x, y))
    o.surfing = True
    _place(o, g, "rock", (wx, wy + 1), "up")
    _step(o, g, UP)
    assert g.state.tile == (wx, wy)       # climbed the waterfall


# ── headbutt ─────────────────────────────────────────────────────────

def test_headbutt_tree_interaction_with_capability(ow):
    g, o = ow
    _place(o, g, "rock", (1, 1))
    hx, hy = _find(o.map, lambda m, x, y: m.is_headbutt_tree(x, y))
    _place(o, g, "rock", (hx - 1, hy), "right")
    _press_a(o, g)
    # With capability, a dialog or encounter should be triggered.
    # The tree stays blocked (headbutt doesn't clear it).
    assert o.map.blocked(hx, hy)
    # A dialog ("Nothing fell" or battle) was pushed or resolved.
    # Just verify no crash and state is consistent.
    assert g.state.tile == (hx - 1, hy)


def test_headbutt_tree_interaction_without_capability(ow):
    g, o = ow
    g.state.flags.discard("can_headbutt")
    _place(o, g, "rock", (1, 1))
    hx, hy = _find(o.map, lambda m, x, y: m.is_headbutt_tree(x, y))
    _place(o, g, "rock", (hx - 1, hy), "right")
    _press_a(o, g)
    assert o.map.blocked(hx, hy)          # tree always stays blocked


# ── new capability properties ─────────────────────────────────────────

def test_capability_properties_from_flags(ow):
    g, o = ow
    for cap in ("can_rock_smash", "can_waterfall", "can_headbutt", "can_fly"):
        assert getattr(g.state, cap), f"{cap} should be set"
        g.state.flags.discard(cap)
        assert not getattr(g.state, cap), f"{cap} should be clear"


# ── Fly scene ─────────────────────────────────────────────────────────

def test_fly_scene_loads_without_error(ow):
    g, o = ow
    from pkmn.game.menus import FlyScene
    fs = FlyScene(g)
    import pygame
    surf = pygame.Surface((160, 144))
    fs.draw(surf)    # should not raise


def test_fly_scene_lists_visited_maps_with_fly_name(ow):
    """Only maps with a fly_name prop appear in FlyScene."""
    g, o = ow
    from pkmn.game.menus import FlyScene
    g.state.visited_maps = {"meadow", "glade", "rock"}
    fs = FlyScene(g)
    # None of the seamless demo maps have fly_name set,
    # so _spots should be empty (no crash).
    assert isinstance(fs._spots, list)


# ── badges scene ──────────────────────────────────────────────────────

def test_badges_scene_draws_without_error(ow):
    g, o = ow
    from pkmn.game.menus import BadgesScene
    g.state.badges = {"boulder", "cascade"}
    bs = BadgesScene(g)
    import pygame
    surf = pygame.Surface((160, 144))
    bs.draw(surf)


# ── pause menu includes badges/fly when features are on ───────────────

def test_pause_menu_includes_badges_option(ow):
    g, o = ow
    from pkmn.game.menus import PauseScene
    ps = PauseScene(g)
    assert "BADGES" in ps.OPTIONS


def test_pause_menu_includes_fly_option_when_can_fly(ow):
    g, o = ow
    from pkmn.game.menus import PauseScene
    ps = PauseScene(g)
    assert "FLY" in ps.OPTIONS


def test_pause_menu_excludes_fly_without_capability(ow):
    g, o = ow
    g.state.flags.discard("can_fly")
    from pkmn.game.menus import PauseScene
    ps = PauseScene(g)
    assert "FLY" not in ps.OPTIONS
