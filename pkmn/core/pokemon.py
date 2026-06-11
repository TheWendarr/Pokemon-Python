"""PokemonState: the ONE persistent representation of a Pokemon.

Architecture note. The old code had three competing sources of truth
(roster JSON dicts, Pokemon instances, and the engine's deep-copied
clones with HP reset to full), which is where most of its state bugs
lived. The replacement model:

  * PokemonState owns everything that persists between battles:
    species, level, IVs/EVs, nature, ability, move slots with PP,
    current HP, and non-volatile status. Exactly like the cartridge.
  * pkmn.battle.state.BattlePokemon wraps a PokemonState during battle
    and owns only battle-volatile data (stat stages, confusion, toxic
    counter...). Damage, PP use, and status mutate the PokemonState
    directly -- so, as in the real games, they persist after the battle
    with no copy-back step to forget.
  * Serialization is to_dict/from_dict; whoever owns the save file does
    the disk I/O. The engine never touches disk.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Optional

from ..data.models import STAT_KEYS, HP
from ..data.repository import GameData
from . import stats as statmath


@dataclass
class MoveSlot:
    move_id: str
    pp: int
    pp_max: int

    def to_dict(self) -> dict:
        return {"move": self.move_id, "pp": self.pp, "pp_max": self.pp_max}


@dataclass
class PokemonState:
    species_id: str
    level: int
    ivs: dict
    evs: dict
    nature: str
    ability: str
    moves: list                      # list[MoveSlot]
    current_hp: int = -1             # -1 -> set to max on bind
    status: Optional[str] = None
    nickname: Optional[str] = None

    # Derived (filled by bind()):
    stats: dict = field(default_factory=dict, repr=False)
    _data: Optional[GameData] = field(default=None, repr=False)

    # ── construction ─────────────────────────────────────────────────
    def bind(self, data: GameData) -> "PokemonState":
        """Attach game data and compute stats. Idempotent."""
        self._data = data
        species = data.species(self.species_id)
        nature = data.natures.get(self.nature.lower())
        if nature is None:
            raise ValueError(f"Unknown nature: {self.nature!r}")
        self.stats = statmath.calc_all_stats(
            species.base_stats, self.ivs, self.evs, self.level, nature)
        if self.current_hp < 0:
            self.current_hp = self.max_hp
        self.current_hp = min(self.current_hp, self.max_hp)
        return self

    @staticmethod
    def generate(data: GameData, species_id, level: int, *,
                 ivs: Optional[dict] = None, evs: Optional[dict] = None,
                 nature: Optional[str] = None, ability: Optional[str] = None,
                 moves: Optional[list] = None,
                 rng: Optional[random.Random] = None) -> "PokemonState":
        """Build a Pokemon the way the games do: random IVs, zero EVs,
        random nature/ability, last four level-up moves."""
        rng = rng or random.Random()
        species = data.species(species_id)
        ivs = {s: ivs.get(s) if ivs and ivs.get(s) is not None else rng.randint(0, 31)
               for s in STAT_KEYS} if ivs else {s: rng.randint(0, 31) for s in STAT_KEYS}
        evs = {s: (evs or {}).get(s, 0) for s in STAT_KEYS}
        nature = nature or rng.choice(sorted(data.natures.keys()))
        ability = ability or (rng.choice(species.abilities) if species.abilities else "")
        if moves is None:
            moves = species.level_up_moves(level)[-4:]  # last four learned
        slots = []
        for mid in moves[:4]:
            md = data.move(mid)
            slots.append(MoveSlot(md.id, md.pp, md.pp))
        ps = PokemonState(species_id=species.id, level=level, ivs=ivs, evs=evs,
                          nature=nature, ability=ability, moves=slots)
        return ps.bind(data)

    # ── accessors ────────────────────────────────────────────────────
    @property
    def species(self):
        return self._data.species(self.species_id)

    @property
    def name(self) -> str:
        return self.nickname or self.species.name

    @property
    def max_hp(self) -> int:
        return self.stats[HP]

    @property
    def fainted(self) -> bool:
        return self.current_hp <= 0

    def move_slot(self, move_id: str) -> Optional[MoveSlot]:
        for s in self.moves:
            if s.move_id == move_id:
                return s
        return None

    # ── mutation ─────────────────────────────────────────────────────
    def take_damage(self, amount: int) -> int:
        dealt = min(amount, self.current_hp)
        self.current_hp -= dealt
        return dealt

    def heal(self, amount: int) -> int:
        healed = min(amount, self.max_hp - self.current_hp)
        self.current_hp += healed
        return healed

    # ── serialization ────────────────────────────────────────────────
    def to_dict(self) -> dict:
        return {
            "species": self.species_id,
            "level": self.level,
            "ivs": dict(self.ivs),
            "evs": dict(self.evs),
            "nature": self.nature,
            "ability": self.ability,
            "moves": [s.to_dict() for s in self.moves],
            "current_hp": self.current_hp,
            "status": self.status,
            "nickname": self.nickname,
        }

    @staticmethod
    def from_dict(d: dict, data: GameData) -> "PokemonState":
        slots = []
        for m in d.get("moves", []):
            if isinstance(m, str):  # tolerate bare move-name lists
                md = data.move(m)
                slots.append(MoveSlot(md.id, md.pp, md.pp))
            else:
                slots.append(MoveSlot(m["move"], int(m["pp"]), int(m["pp_max"])))
        ps = PokemonState(
            species_id=d["species"],
            level=int(d["level"]),
            ivs={k: int(v) for k, v in d.get("ivs", {}).items()},
            evs={k: int(v) for k, v in d.get("evs", {}).items()},
            nature=d.get("nature", "hardy"),
            ability=d.get("ability", ""),
            moves=slots,
            current_hp=int(d.get("current_hp", -1)),
            status=d.get("status"),
            nickname=d.get("nickname"),
        )
        # Fill missing IV/EV keys so partial save data can't KeyError.
        from ..data.models import norm_stat
        ps.ivs = {s: int(ps.ivs.get(s, ps.ivs.get(norm_stat(s), 0))) for s in STAT_KEYS}
        ps.evs = {s: int(ps.evs.get(s, 0)) for s in STAT_KEYS}
        return ps.bind(data)
