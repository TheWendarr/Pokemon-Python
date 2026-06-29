"""Phase 9 -- multi-method encounters: per-method tables (land/surf/rods),
back-compat with the legacy flat list, surf rolls, and fishing. Needs the
dataset (rolls generate real species)."""
import os
import random

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pytest

pytest.importorskip("pygame")
pytest.importorskip("pytmx")

from pkmn.game.battle_scene import BattleScene          # noqa: E402
from pkmn.game.dialog import DialogScene                # noqa: E402
from pkmn.game.overworld import OverworldScene          # noqa: E402
from pkmn.game.scene import Game                        # noqa: E402

pytestmark = pytest.mark.skipif(
    not os.path.exists("game/data/species"),
    reason="needs the generated full dataset")


@pytest.fixture
def ow():
    g = Game(headless=True, seed=4)            # default game has water (glade)
    o = OverworldScene(g)
    g.push(o)
    yield g, o
    import pygame
    pygame.quit()


def _slot(species, lo=10, hi=10, w=1):
    return {"species": species, "min": lo, "max": hi, "weight": w}


def test_flat_list_is_treated_as_land(ow):
    g, o = ow
    o._encounters = {o.map.id: [_slot("sewaddle")]}
    assert o._enc_table("land") and o._enc_table("land")[0]["species"] == "sewaddle"
    assert o._enc_table("surf") is None
    assert o._enc_table("super_rod") is None


def test_per_method_tables_select_correctly(ow):
    g, o = ow
    o._encounters = {o.map.id: {"land": [_slot("sewaddle")],
                                "surf": [_slot("tympole")],
                                "super_rod": [_slot("magikarp")]}}
    assert o._enc_table("surf")[0]["species"] == "tympole"
    assert o._enc_table("super_rod")[0]["species"] == "magikarp"
    assert o._enc_table("old_rod") is None


def test_surf_roll_uses_surf_table(ow):
    g, o = ow
    o._encounters = {o.map.id: {"surf": [_slot("tympole")]}}
    g.state.rng = random.Random(1)
    assert o._roll_encounter("surf") is True
    assert isinstance(g.top, BattleScene)
    assert g.top.eng.active("p2").state.species_id == "tympole"


def test_rod_roll_uses_rod_table(ow):
    g, o = ow
    o._encounters = {o.map.id: {"super_rod": [_slot("magikarp")]}}
    assert o._roll_encounter("super_rod") is True
    assert g.top.eng.active("p2").state.species_id == "magikarp"


def test_fishing_requires_a_rod(ow):
    # seamless example has real surf tiles to fish in
    g2 = Game(headless=True, seed=4, game_dir="examples/seamless")
    o = OverworldScene(g2)
    g2.push(o)
    water = None
    import glob
    mids = [os.path.splitext(os.path.basename(p))[0]
            for p in sorted(glob.glob("examples/seamless/maps/*.tmx"))]
    for mid in mids:
        try:
            o.load_map(mid)
        except Exception:
            continue
        water = next(((x, y) for y in range(o.map.height)
                      for x in range(o.map.width) if o.map.is_surf(x, y)), None)
        if water:
            break
    if water is None:
        pytest.skip("no map with water found")
    o._encounters = {o.map.id: {"super_rod": [_slot("tentacool")]}}
    g = g2
    # no rod in the bag -> not a fishing action
    g.state.bag.pop("super-rod", None)
    assert o._try_fish(water) is False
    # with a rod, facing water is a fishing action (bite or nibble)
    g.state.bag["super-rod"] = 1
    assert o._try_fish(water) is True
    assert isinstance(g.top, (BattleScene, DialogScene))
