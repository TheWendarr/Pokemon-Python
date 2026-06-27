"""Phase 9 -- fuller trainer/party spec: parse_party accepts a rich list of
per-mon dicts (level/nature/ability/moves/item/IVs) alongside the legacy
compact string. Needs the dataset."""
import os
import random

os.environ["SDL_VIDEODRIVER"] = "dummy"

import pytest

pytest.importorskip("pygame")
from pkmn.game.scene import Game                        # noqa: E402
from pkmn.game.script import parse_party                 # noqa: E402

pytestmark = pytest.mark.skipif(
    not os.path.exists("game/data/species"),
    reason="needs the generated full dataset")


@pytest.fixture(scope="module")
def data():
    g = Game(headless=True, seed=1)
    yield g.state.data
    import pygame
    pygame.quit()


def test_legacy_string_party_still_works(data):
    party = parse_party("pikachu:12@light-ball|onix:14", data, random.Random(1))
    assert [p.species_id for p in party] == ["pikachu", "onix"]
    assert party[0].held_item == "light-ball"


def test_rich_list_party_sets_everything(data):
    spec = [{"species": "gengar", "level": 36, "nature": "timid",
             "ability": "levitate", "item": "black-sludge",
             "moves": ["shadow-ball", "sludge-bomb", "thunderbolt", "hypnosis"],
             "ivs": {"speed": 31}}]
    party = parse_party(spec, data, random.Random(2))
    mon = party[0]
    assert mon.species_id == "gengar" and mon.level == 36
    assert mon.nature == "timid" and mon.ability == "levitate"
    assert mon.held_item == "black-sludge"
    assert mon.ivs["speed"] == 31
    assert [m.move_id for m in mon.moves] == [
        "shadow-ball", "sludge-bomb", "thunderbolt", "hypnosis"]
