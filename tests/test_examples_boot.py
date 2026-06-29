"""A5: CI smoke harness — boot every example region headless.

Each parametrized test creates a Game, pushes OverworldScene (bypassing
the TitleScene so we can test the region directly), and ticks N frames.
A region that lints clean but crashes on load will fail here.
"""
import glob
import os

import pytest

from pkmn.game.overworld import OverworldScene
from pkmn.game.scene import Game

_GITIGNORED = {"kanto_frlg"}   # local-only; proprietary tiles, not in the repo
_EXAMPLES = sorted(
    os.path.dirname(p) for p in glob.glob("examples/*/game.json")
    if os.path.basename(os.path.dirname(p)) not in _GITIGNORED
)
_IDS = [os.path.basename(p) for p in _EXAMPLES]


@pytest.mark.parametrize("game_dir", _EXAMPLES, ids=_IDS)
def test_example_boots(game_dir):
    """Boot region headless and tick 10 frames without crashing."""
    g = Game(headless=True, game_dir=game_dir)
    g.push(OverworldScene(g))
    for _ in range(10):
        g.tick()
    assert len(g.scenes) > 0, "scene stack unexpectedly empty"
