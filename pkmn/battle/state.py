"""Battle actions (the engine's input API) and BattlePokemon
(persistent state + battle-volatile layer)."""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Optional

from ..core.pokemon import PokemonState
from ..core.stats import stage_multiplier
from . import passives
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
    target_slot: int = -1   # -1 = auto; in doubles: 0 or 1 (which foe slot)


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
    # Phase 2 volatiles
    protected: bool = False        # this turn
    protect_count: int = 0         # consecutive uses (success halves)
    charging: Optional[str] = None         # two-turn move being charged
    semi_invulnerable: Optional[str] = None  # 'fly'|'dig'|'dive'|'bounce'
    recharging: bool = False       # Hyper Beam family
    rampage_move: Optional[str] = None     # Outrage family lock
    rampage_turns: int = 0
    choice_lock: Optional[str] = None      # choice-item move lock
    crit_bonus: int = 0            # Focus Energy
    leech_seeded: bool = False
    trap_turns: int = 0            # Wrap family
    trap_name: str = ""
    endured: bool = False          # this turn (Endure)
    lock_on: bool = False          # next move can't miss
    taunt_turns: int = 0
    no_escape: bool = False        # Mean Look family
    ability_suppressed: bool = False   # Gastro Acid
    ingrained: bool = False
    cursed: bool = False           # Ghost-type Curse
    telekinesis_turns: int = 0
    last_hit: Optional[tuple] = None   # (category, amount) taken this turn
    last_move: Optional[str] = None
    aqua_ring: bool = False
    ability_override: Optional[str] = None  # Worry Seed / Entrainment
    infatuated: bool = False
    encore_move: Optional[str] = None
    encore_turns: int = 0
    tormented: bool = False
    imprison: bool = False
    heal_block_turns: int = 0
    embargo_turns: int = 0
    # Phase B volatiles
    flash_fire_active: bool = False
    destiny_bond: bool = False
    grudge: bool = False
    snatch_active: bool = False
    magnet_rise_turns: int = 0
    yawn_turns: int = 0
    perish_count: int = 0
    transformed: bool = False
    nightmare: bool = False
    unburden_active: bool = False
    # Batch-3 ability volatiles
    truant_resting: bool = False    # Truant: True on the loafing turn
    analytic_active: bool = False   # Analytic: foe already moved this turn
    # Move-effect volatiles
    foresight_active: bool = False   # Foresight/Odor Sleuth: Normal/Fight hits Ghost
    miracle_eye_active: bool = False # Miracle Eye: Psychic hits Dark
    disabled_move: Optional[str] = None   # Disable: locked-out move id
    disable_turns: int = 0
    substitute_hp: int = 0          # >0 = substitute is active with this HP
    power_trick_swapped: bool = False  # Power Trick: Atk/Def physically swapped
    type_override: Optional[list] = None  # Soak/Reflect Type/Conversion forced type(s)
    last_received_move: Optional[str] = None  # Mirror Move: last move that hit this mon
    last_used_item: Optional[str] = None  # Recycle: last consumed item
    magic_coat_active: bool = False  # Magic Coat: reflects status moves this turn


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
    def types(self):
        if self.vol.type_override is not None:
            return self.vol.type_override
        return self.species.types
    @property
    def held_item(self): return self.state.held_item
    @property
    def moves(self): return self.state.moves

    def take_damage(self, n: int) -> int: return self.state.take_damage(n)
    def heal(self, n: int) -> int: return self.state.heal(n)

    def effective_speed(self, weather: Optional[str] = None) -> int:
        s = int(self.stats[SPEED] * stage_multiplier(self.stages[SPEED]))
        s = int(s * passives.speed_mod(self, weather))
        if self.status == "paralysis" and passives.abil(self) != "quick-feet":
            s //= 4  # Gen 5 paralysis quarters speed (Quick Feet ignores this)
        return s

    def modify_stage(self, stat: str, change: int) -> int:
        """Returns the actual change applied (0 if already capped).
        Contrary inverts; Simple doubles all stat stage changes."""
        if passives.abil(self) == "contrary":
            change = -change
        elif passives.abil(self) == "simple":
            change *= 2
        before = self.stages[stat]
        after = max(-6, min(6, before + change))
        self.stages[stat] = after
        return after - before

    def on_switch_out(self) -> None:
        """Reset everything battle-volatile (Gen 5 behavior: stages,
        confusion, flinch, and the toxic counter all reset; the sleep
        counter re-rolls on re-entry)."""
        if self.vol.power_trick_swapped:
            self.state.stats["attack"], self.state.stats["defense"] = (
                self.state.stats["defense"], self.state.stats["attack"])
        self.stages = {k: 0 for k in STAGE_KEYS}
        self.vol = Volatiles()

    def usable_moves(self) -> list:
        return [s for s in self.state.moves if s.pp > 0]
