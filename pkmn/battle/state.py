"""Battle actions (the engine's input API) and BattlePokemon
(persistent state + battle-volatile layer)."""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Optional

from ..core.pokemon import PokemonState
from ..core.stats import stage_multiplier
from ..data.models import STAGE_KEYS, SPEED
from ..data.repository import GameData

P1, P2 = "p1", "p2"
SIDES = (P1, P2)


def other(side: str) -> str:
    return P2 if side == P1 else P1


# ── Actions ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class MoveAction:
    move_id: str


@dataclass(frozen=True)
class SwitchAction:
    party_index: int


@dataclass(frozen=True)
class ItemAction:
    item_id: str
    target_index: int = -1  # -1 == active Pokemon


@dataclass(frozen=True)
class RunAction:
    pass


@dataclass(frozen=True)
class CatchAction:
    ball_id: str


Action = object  # union for documentation purposes


# ── BattlePokemon ────────────────────────────────────────────────────

@dataclass
class Volatiles:
    confusion_turns: int = 0
    flinched: bool = False
    toxic_counter: int = 0
    sleep_turns: int = -1      # -1 == roll on next attempt
    has_moved: bool = False    # this turn (gates flinch)


class BattlePokemon:
    """A PokemonState plus battle-only state. HP / status / PP mutations
    go straight through to the PokemonState (they persist after battle,
    as in the games); stages and volatiles vanish with this wrapper."""

    def __init__(self, data: GameData, state: PokemonState):
        self.data = data
        self.state = state.bind(data)
        self.species = data.species(state.species_id)
        self.stages = {k: 0 for k in STAGE_KEYS}
        self.vol = Volatiles()

    # passthroughs
    @property
    def name(self): return self.state.name
    @property
    def level(self): return self.state.level
    @property
    def stats(self): return self.state.stats
    @property
    def max_hp(self): return self.state.max_hp
    @property
    def current_hp(self): return self.state.current_hp
    @property
    def status(self): return self.state.status
    @status.setter
    def status(self, v): self.state.status = v
    @property
    def fainted(self): return self.state.fainted
    @property
    def types(self): return self.species.types
    @property
    def moves(self): return self.state.moves

    def take_damage(self, n: int) -> int: return self.state.take_damage(n)
    def heal(self, n: int) -> int: return self.state.heal(n)

    def effective_speed(self) -> int:
        s = int(self.stats[SPEED] * stage_multiplier(self.stages[SPEED]))
        if self.status == "paralysis":
            s //= 4  # Gen 5 paralysis quarters speed
        return s

    def modify_stage(self, stat: str, change: int) -> int:
        """Returns the actual change applied (0 if already capped)."""
        before = self.stages[stat]
        after = max(-6, min(6, before + change))
        self.stages[stat] = after
        return after - before

    def on_switch_out(self) -> None:
        """Reset everything battle-volatile (Gen 5 behavior: stages,
        confusion, flinch, and the toxic counter all reset; the sleep
        counter re-rolls on re-entry)."""
        self.stages = {k: 0 for k in STAGE_KEYS}
        self.vol = Volatiles()

    def usable_moves(self) -> list:
        return [s for s in self.state.moves if s.pp > 0]
