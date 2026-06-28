"""Canonical data models.

Single source of truth for stat keys and the shapes of species/move/item
data. Everything in the engine uses these snake_case keys -- the old
hyphen/underscore mismatch bug class is eliminated by normalizing once,
at load time, and nowhere else.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# ── Canonical stat keys ──────────────────────────────────────────────
HP = "hp"
ATTACK = "attack"
DEFENSE = "defense"
SP_ATTACK = "special_attack"
SP_DEFENSE = "special_defense"
SPEED = "speed"
STAT_KEYS = (HP, ATTACK, DEFENSE, SP_ATTACK, SP_DEFENSE, SPEED)

# Battle-only "stats" that exist as stages (never as base stats).
ACCURACY = "accuracy"
EVASION = "evasion"
STAGE_KEYS = (ATTACK, DEFENSE, SP_ATTACK, SP_DEFENSE, SPEED, ACCURACY, EVASION)

PHYSICAL = "physical"
SPECIAL = "special"
STATUS = "status"

# Non-volatile status conditions (persist outside battle).
STATUSES = ("burn", "poison", "toxic", "paralysis", "sleep", "freeze")


def norm_stat(key: str) -> str:
    """Normalize any external stat key ('special-attack', 'Sp. Atk', ...)."""
    k = key.strip().lower().replace("-", "_").replace(" ", "_").replace(".", "")
    aliases = {
        "sp_atk": SP_ATTACK, "spatk": SP_ATTACK, "spa": SP_ATTACK,
        "sp_def": SP_DEFENSE, "spdef": SP_DEFENSE, "spd": SP_DEFENSE,
        "spe": SPEED, "atk": ATTACK, "def": DEFENSE,
    }
    return aliases.get(k, k)


# ── Moves ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class StatChange:
    stat: str            # canonical stat/stage key
    change: int          # e.g. -1, +2

    @staticmethod
    def from_dict(d: dict) -> "StatChange":
        return StatChange(stat=norm_stat(d["stat"]), change=int(d["change"]))


@dataclass(frozen=True)
class MoveEffect:
    """Data-driven effect description, mirroring PokeAPI move meta.

    A generic interpreter in pkmn.battle.moves executes most moves from
    this alone; named special cases live in a handler registry.
    """
    kind: str = "damage"               # PokeAPI meta category identifier
    ailment: Optional[str] = None      # 'paralysis', 'burn', 'confusion', ...
    ailment_chance: int = 0            # 0 == guaranteed for pure status moves
    stat_changes: tuple = ()           # tuple[StatChange, ...]
    stat_chance: int = 0               # 0 == guaranteed when stat_changes set
    flinch_chance: int = 0
    drain: int = 0                     # % of damage healed (<0 == recoil)
    healing: int = 0                   # % of max HP healed
    min_hits: Optional[int] = None
    max_hits: Optional[int] = None

    @staticmethod
    def from_dict(d: dict) -> "MoveEffect":
        return MoveEffect(
            kind=d.get("kind", "damage"),
            ailment=d.get("ailment") or None,
            ailment_chance=int(d.get("ailment_chance") or 0),
            stat_changes=tuple(StatChange.from_dict(s) for s in d.get("stat_changes", [])),
            stat_chance=int(d.get("stat_chance") or 0),
            flinch_chance=int(d.get("flinch_chance") or 0),
            drain=int(d.get("drain") or 0),
            healing=int(d.get("healing") or 0),
            min_hits=d.get("min_hits"),
            max_hits=d.get("max_hits"),
        )


@dataclass(frozen=True)
class MoveData:
    id: str                            # identifier, e.g. 'thunderbolt'
    name: str                          # display name, e.g. 'Thunderbolt'
    type: str                          # 'electric' (lowercase identifier)
    category: str                      # physical | special | status
    power: Optional[int]               # None for status / variable moves
    accuracy: Optional[int]            # None == never misses
    pp: int
    priority: int = 0
    target: str = "selected-pokemon"   # PokeAPI target identifier
    crit_stage: int = 0
    flags: frozenset = frozenset()     # e.g. {'contact', 'defrost', 'protect'}
    effect: MoveEffect = field(default_factory=MoveEffect)

    @property
    def is_damaging(self) -> bool:
        return self.category in (PHYSICAL, SPECIAL)

    @property
    def targets_user(self) -> bool:
        return self.target in ("user", "users-field", "user-or-ally")

    @staticmethod
    def from_dict(d: dict) -> "MoveData":
        return MoveData(
            id=d["id"],
            name=d.get("name") or d["id"].replace("-", " ").title(),
            type=d["type"].lower(),
            category=d["category"].lower(),
            power=d.get("power"),
            accuracy=d.get("accuracy"),
            pp=int(d.get("pp") or 5),
            priority=int(d.get("priority") or 0),
            target=d.get("target", "selected-pokemon"),
            crit_stage=int(d.get("crit_stage") or 0),
            flags=frozenset(d.get("flags", [])),
            effect=MoveEffect.from_dict(d.get("effect", {})),
        )


# ── Species ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class LearnsetEntry:
    move: str
    level: int = 0


@dataclass(frozen=True)
class SpeciesData:
    id: str                            # identifier, e.g. 'pikachu'
    name: str                          # display name
    dex: int
    types: tuple                       # ('electric',) or two entries
    base_stats: dict                   # canonical keys -> int
    abilities: tuple = ()              # identifiers, hidden last
    base_experience: int = 0
    growth_rate: str = "medium"
    evolves_to: tuple = ()
    catch_rate: int = 45
    gender_rate: int = 4               # PokeAPI eighths female; -1 genderless
    learnset: dict = field(default_factory=dict)
    # learnset = {'level_up': [LearnsetEntry...], 'machine': [str...],
    #             'egg': [str...], 'tutor': [str...]}
    ev_yield: dict = field(default_factory=dict)
    # ev_yield = {stat_key: amount}, e.g. {'special_attack': 1}

    def level_up_moves(self, level: int) -> list[str]:
        """Moves learnable by level-up at or below `level`, in learn order."""
        out = []
        for e in self.learnset.get("level_up", []):
            if e.level <= level and e.move not in out:
                out.append(e.move)
        return out

    @staticmethod
    def from_dict(d: dict) -> "SpeciesData":
        ls = d.get("learnset", {})
        learnset = {
            "level_up": [LearnsetEntry(e["move"], int(e.get("level", 0)))
                         for e in ls.get("level_up", [])],
            "machine": list(ls.get("machine", [])),
            "egg": list(ls.get("egg", [])),
            "tutor": list(ls.get("tutor", [])),
        }
        return SpeciesData(
            id=d["id"],
            name=d.get("name") or d["id"].title(),
            dex=int(d["dex"]),
            types=tuple(t.lower() for t in d["types"]),
            base_stats={norm_stat(k): int(v) for k, v in d["base_stats"].items()},
            abilities=tuple(d.get("abilities", [])),
            base_experience=int(d.get("base_experience") or 0),
            growth_rate=d.get("growth_rate", "medium"),
            evolves_to=tuple(d.get("evolves_to", [])),
            catch_rate=int(d.get("catch_rate") or 45),
            gender_rate=int(d.get("gender_rate", 4)),
            learnset=learnset,
            ev_yield={norm_stat(k): int(v)
                      for k, v in d.get("ev_yield", {}).items()},
        )


# ── Items ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ItemData:
    id: str
    name: str
    category: str                      # PokeAPI category identifier
    pocket: str = "misc"               # medicine|pokeballs|berries|battle|...
    heal: int = 0                      # flat HP restored ('full' -> -1)
    cures: tuple = ()                  # statuses cured; ('all',) for Full Heal
    ball_rate: float = 0.0             # ball multiplier (Poke Ball == 1.0)
    revive: float = 0.0                # fraction of max HP restored on revive
    stages: tuple = ()                 # ((stat, change), ...) X items
    crit: int = 0                      # Dire Hit crit-stage bonus
    guard: bool = False                # Guard Spec. (Mist)
    holdable: bool = False
    battle_usable: bool = False
    cost: int = 0
    fling_power: int = 0
    short_effect: str = ""

    @property
    def is_ball(self) -> bool:
        return (self.ball_rate > 0 or self.pocket == "pokeballs"
                or self.category == "ball")

    @staticmethod
    def from_dict(d: dict) -> "ItemData":
        heal = d.get("heal", 0)
        return ItemData(
            id=d["id"],
            name=d.get("name") or d["id"].replace("-", " ").title(),
            category=d.get("category", "medicine"),
            pocket=d.get("pocket", "misc"),
            heal=-1 if heal == "full" else int(heal or 0),
            cures=tuple(d.get("cures", [])),
            ball_rate=float(d.get("ball_rate") or 0.0),
            revive=float(d.get("revive") or 0.0),
            stages=tuple((k, v) for k, v in (d.get("stages") or {}).items()),
            crit=int(d.get("crit") or 0),
            guard=bool(d.get("guard", False)),
            holdable=bool(d.get("holdable", False)),
            battle_usable=bool(d.get("battle_usable", False)),
            cost=int(d.get("cost") or 0),
            fling_power=int(d.get("fling_power") or 0),
            short_effect=d.get("short_effect", ""),
        )
