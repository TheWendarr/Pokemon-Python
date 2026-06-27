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
    map_id: str = ""           # set from the region manifest / save
    tile: tuple = None  # None -> use the map's spawn object
    facing: str = "down"
    rng: random.Random = field(default_factory=random.Random)
    flags: set = field(default_factory=set)   # event/progress flags (booleans)
    vars: dict = field(default_factory=dict)  # integer event variables
    self_switches: set = field(default_factory=set)  # "map:event:SW" keys
    money: int = 1500
    pc: list = field(default_factory=list)    # PC box (PokemonState)
    seen: set = field(default_factory=set)    # Pokedex: species encountered
    caught: set = field(default_factory=set)  # Pokedex: species owned
    regiondex: list = field(default_factory=list)  # region roster (dex order)
    repel_steps: int = 0                      # remaining steps of repel

    @classmethod
    def new_game(cls, data: GameData, *, manifest: dict | None = None,
                 seed: int | None = None) -> "GameState":
        m = manifest or {}
        rng = random.Random(seed)
        st = cls(data=data, rng=rng)
        starter = m.get("starter")
        if starter:  # absent or null -> begin with an empty party
            st.party.append(PokemonState.generate(
                data, starter["species"], int(starter.get("level", 10)),
                rng=rng, moves=starter.get("moves")))
        st.bag = dict(m.get("bag", {"potion": 5, "poke-ball": 10}))
        st.money = int(m.get("money", 1500))
        start = m.get("start", {})
        st.map_id = start.get("map", "")
        st.tile = tuple(start["tile"]) if start.get("tile") else None
        st.facing = start.get("facing", "down")
        st.flags = set(m.get("flags", []))
        st.regiondex = list(m.get("dex", []))    # roster for the Pokedex view
        for p in st.party:                        # you own your starter
            st.register_caught(p.species_id)
        return st

    # ── Pokedex ──────────────────────────────────────────────────────
    def register_seen(self, species_id: str) -> None:
        self.seen.add(species_id)

    def register_caught(self, species_id: str) -> None:
        self.caught.add(species_id)
        self.seen.add(species_id)

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

    # field-move capabilities, granted like HMs via flags
    @property
    def can_surf(self) -> bool:
        return "can_surf" in self.flags

    @property
    def can_cut(self) -> bool:
        return "can_cut" in self.flags

    # ── persistence ──────────────────────────────────────────────────
    def to_dict(self) -> dict:
        return {"version": 2,
                "party": [p.to_dict() for p in self.party],
                "pc": [p.to_dict() for p in self.pc],
                "bag": dict(self.bag), "money": self.money,
                "flags": sorted(self.flags),
                "vars": dict(self.vars),
                "self_switches": sorted(self.self_switches),
                "map_id": self.map_id, "tile": list(self.tile or (0, 0)),
                "facing": self.facing,
                "seen": sorted(self.seen), "caught": sorted(self.caught),
                "regiondex": list(self.regiondex),
                "repel_steps": self.repel_steps}

    @classmethod
    def from_dict(cls, data: GameData, d: dict,
                  rng: random.Random | None = None) -> "GameState":
        st = cls(data=data, rng=rng or random.Random())
        st.party = [PokemonState.from_dict(p, data).bind(data) for p in d["party"]]
        st.pc = [PokemonState.from_dict(p, data).bind(data) for p in d.get("pc", [])]
        st.bag = dict(d.get("bag", {}))
        st.money = int(d.get("money", 0))
        st.flags = set(d.get("flags", []))
        st.vars = {k: int(v) for k, v in d.get("vars", {}).items()}
        st.self_switches = set(d.get("self_switches", []))
        st.map_id = d.get("map_id", "")
        st.tile = tuple(d.get("tile") or (0, 0))
        st.facing = d.get("facing", "down")
        st.seen = set(d.get("seen", []))
        st.caught = set(d.get("caught", []))
        st.regiondex = list(d.get("regiondex", []))
        st.repel_steps = int(d.get("repel_steps", 0))
        return st
