"""Persistent game-session state: the player's party, bag, and place in
the world. The battle engine mutates party PokemonState objects
directly, so HP/PP/status persist after battles like on cartridge."""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from ..core.pokemon import PokemonState
from ..data.repository import GameData


@dataclass
class GameState:
    data: GameData
    party: list = field(default_factory=list)
    bag: dict = field(default_factory=dict)
    map_id: str = "town"
    tile: tuple = None  # None -> use the map's spawn object
    facing: str = "down"
    rng: random.Random = field(default_factory=random.Random)

    @classmethod
    def new_game(cls, data: GameData, *, starter: str = "oshawott",
                 seed: int | None = None) -> "GameState":
        rng = random.Random(seed)
        st = cls(data=data, rng=rng)
        st.party.append(PokemonState.generate(data, starter, 12, rng=rng))
        st.bag = {"potion": 5, "poke-ball": 10}
        return st

    def heal_party(self) -> None:
        for p in self.party:
            p.bind(self.data)
            p.current_hp = p.max_hp
            p.status = None
            for slot in p.moves:
                slot.pp = slot.pp_max

    def first_able(self):
        for p in self.party:
            if p.current_hp > 0:
                return p
        return None
