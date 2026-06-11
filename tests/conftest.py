"""Shared pytest fixtures: writes the mini dataset to a temp game dir,
provides GameData, deterministic RNGs, and party builders."""
from __future__ import annotations

import json
import random

import pytest

from pkmn.core.pokemon import PokemonState
from pkmn.data.repository import GameData

from . import fixtures as fx


class MaxRoll(random.Random):
    """Fully deterministic battle RNG: max damage roll, no crits, all
    percent-chance rolls succeed (randint(1,100) -> 1), speed ties go to
    insertion order, multi-hit choice picks the first option."""

    def randint(self, a, b):
        if (a, b) == (85, 100):   # damage roll
            return 100
        if (a, b) == (1, 100):    # percent-chance rolls succeed
            return 1
        if (a, b) == (1, 3):      # sleep counter: max
            return 3
        return a

    def random(self):
        return 1.0                # never crit, never para-block, no self-hit

    def choice(self, seq):
        return seq[0]


class NoChance(MaxRoll):
    """Like MaxRoll but all percent-chance rolls FAIL (secondary effects
    never trigger)."""

    def randint(self, a, b):
        if (a, b) == (1, 100):
            return 100
        return super().randint(a, b)


def write_game_dir(root) -> str:
    data = root / "data"
    (data / "species").mkdir(parents=True)
    (data / "moves").mkdir(parents=True)
    for sid, sp in fx.SPECIES.items():
        (data / "species" / f"{sp['dex']:03d}-{sid}.json").write_text(json.dumps(sp))
    for mid, mv in fx.MOVES.items():
        (data / "moves" / f"{mid}.json").write_text(json.dumps(mv))
    (data / "types.json").write_text(json.dumps(fx.TYPES))
    (data / "natures.json").write_text(json.dumps(fx.NATURES))
    (data / "items.json").write_text(json.dumps(fx.ITEMS))
    return str(data)


@pytest.fixture(scope="session")
def game_dir(tmp_path_factory):
    return write_game_dir(tmp_path_factory.mktemp("game"))


@pytest.fixture(scope="session")
def data(game_dir):
    return GameData(game_dir)


@pytest.fixture
def maxroll():
    return MaxRoll()


@pytest.fixture
def nochance():
    return NoChance()


@pytest.fixture
def make_mon(data):
    def _make(species, level=50, *, moves=None, nature="hardy", ivs31=True,
              evs=None):
        ivs = {k: 31 for k in
               ("hp", "attack", "defense", "special_attack",
                "special_defense", "speed")} if ivs31 else None
        return PokemonState.generate(
            data, species, level, ivs=ivs, evs=evs, nature=nature,
            moves=moves, rng=random.Random(0))
    return _make
