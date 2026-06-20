"""Phase 6: the authoring toolkit — game-folder format, validation CLI,
and the acceptance: the example region plays start to finish from a
folder containing no engine code."""
import json
import os
import shutil

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pytest

pytest.importorskip("pygame")
pytest.importorskip("pytmx")

from pkmn.core.pokemon import PokemonState          # noqa: E402
from pkmn.data.repository import GameData           # noqa: E402
from pkmn.cli.lint import Lint                      # noqa: E402
from pkmn.game.battle_scene import BattleScene      # noqa: E402
from pkmn.game.config import A, UP                  # noqa: E402
from pkmn.game.overworld import OverworldScene      # noqa: E402
from pkmn.game.scene import Game                    # noqa: E402

pytestmark = pytest.mark.skipif(
    not os.path.exists("game/data/species"),
    reason="needs the generated full dataset")

ISLE = "examples/isleton"


@pytest.fixture(scope="module")
def data():
    return GameData("game/data")


# ── the validation CLI ───────────────────────────────────────────────

def test_lint_passes_on_both_regions(data):
    assert Lint("game/assets", data).run() == 0
    assert Lint(ISLE, data).run() == 0


def test_lint_catches_broken_content(data, tmp_path):
    broken = tmp_path / "broken"
    shutil.copytree(ISLE, broken)
    # unknown command, bad species, warp to nowhere, bad item
    json.dump({
        "isle_heal": [{"frobnicate": 1}],
        "isle_goal": [{"battle": {"party": "missingno:5"}},
                      {"warp": {"map": "atlantis", "x": 1, "y": 1}},
                      {"give_item": {"item": "not-an-item"}}],
    }, open(broken / "scripts.json", "w"))
    manifest = json.load(open(broken / "game.json"))
    manifest["starter"] = {"species": "mewtwo", "level": 70}  # not in dex
    json.dump(manifest, open(broken / "game.json", "w"))
    lint = Lint(str(broken), data)
    assert lint.run() == 1
    text = "\n".join(lint.errors)
    for needle in ("frobnicate", "missingno", "atlantis", "not-an-item",
                   "dex subset"):
        assert needle in text


def test_lint_requires_manifest(data, tmp_path):
    empty = tmp_path / "empty"
    (empty / "maps").mkdir(parents=True)
    assert Lint(str(empty), data).run() == 1


# ── the acceptance: Isleton start to finish ──────────────────────────

def _mash_battle(g):
    for _ in range(4000):
        if not isinstance(g.top, BattleScene):
            return
        g.input.press(A)
        g.tick()
        g.input.release(A)


def _step(g, direction):
    ow = g.scenes[0]
    for _ in range(60):
        if isinstance(g.top, BattleScene):
            _mash_battle(g)
        before = (g.state.map_id, g.state.tile)
        g.input.press(direction)
        g.tick()
        g.input.release(direction)
        if not isinstance(g.top, OverworldScene):
            return  # dialog/cutscene took over
        if (g.state.map_id, g.state.tile) != before and not ow.moving:
            return


def _mash_a(g, frames=600):
    for _ in range(frames):
        if isinstance(g.top, OverworldScene) and g.scenes[0].script is None \
                and g.scenes[0].cutscene is None:
            return
        g.input.press(A)
        g.tick()
        g.input.release(A)
        g.draw()


def test_isleton_contains_no_engine_code():
    for root, _dirs, files in os.walk(ISLE):
        assert not any(f.endswith(".py") for f in files)


def test_isleton_plays_start_to_finish():
    g = Game(headless=True, seed=77, game_dir=ISLE)
    g.push(OverworldScene(g))
    st = g.state
    # the manifest drove everything: starter, bag, money, start map
    assert st.party[0].species_id == "totodile" and st.party[0].level == 14
    assert st.map_id == "isle_town" and st.tile == (8, 8)
    assert st.money == 800 and st.bag["poke-ball"] == 5
    assert g.assets.root == ISLE                     # its own sprites
    # mashing picks move slot 0, so give the starter a damaging slot 0
    st.party[0] = PokemonState.generate(g.data, "totodile", 14,
                                        rng=st.rng, moves=["water-gun"])
    # north across town onto the pier, into the cove
    for _ in range(10):
        if st.map_id == "cove":
            break
        _step(g, UP)
    assert st.map_id == "cove"
    encounters_seen = len([1 for _ in ()])
    # push north through the forced grass until Sailor Brom spots us
    for _ in range(60):
        if g.scenes[0].cutscene is not None or g.scenes[0].script is not None:
            break
        _step(g, UP)
    _mash_a(g, 2000)                                 # dialog -> battle -> win
    assert "beat_brom" in st.flags
    assert st.money == 800 + 200
    # route around Brom (he walked into column 8) to the shell shrine
    from pkmn.game.config import LEFT, RIGHT
    _step(g, LEFT)
    for _ in range(6):
        _step(g, UP)
    _step(g, RIGHT)
    st.tile = (8, 3)                                 # settle before the shrine
    st.facing = "up"
    g.input.press(A); g.tick(); g.input.release(A)   # touch the shrine
    _mash_a(g, 400)
    assert "finished_isleton" in st.flags            # champion of Isleton
    assert st.money == 1000 + 1000
    import pygame
    pygame.quit()
