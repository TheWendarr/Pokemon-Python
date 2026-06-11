"""Typed battle events.

The engine's only output channel: an ordered stream of Event objects.
Renderers (CLI today, pygame later) translate events to text/animation;
the engine never prints or draws. This keeps your original event-code
idea but with named types and JSON-serializable payloads instead of
magic integers in a side file.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class E(str, Enum):
    BATTLE_START = "battle_start"
    TURN_START = "turn_start"
    SEND_IN = "send_in"
    SWITCH_OUT = "switch_out"

    MOVE_USED = "move_used"
    MOVE_MISSED = "move_missed"
    MOVE_FAILED = "move_failed"
    MOVE_IMMUNE = "move_immune"          # "It doesn't affect..."
    DAMAGE = "damage"
    MULTI_HIT = "multi_hit"
    HEAL = "heal"
    DRAIN = "drain"
    RECOIL = "recoil"

    STATUS_APPLIED = "status_applied"
    STATUS_CURED = "status_cured"
    STATUS_DAMAGE = "status_damage"
    STAT_CHANGE = "stat_change"
    STAT_CHANGE_FAILED = "stat_change_failed"

    FULLY_PARALYZED = "fully_paralyzed"
    ASLEEP = "asleep"
    WOKE_UP = "woke_up"
    FROZEN = "frozen"
    THAWED = "thawed"
    FLINCHED = "flinched"
    CONFUSED = "confused"
    CONFUSION_SELF_HIT = "confusion_self_hit"
    CONFUSION_ENDED = "confusion_ended"

    FAINT = "faint"
    REPLACEMENT_NEEDED = "replacement_needed"

    ITEM_USED = "item_used"
    ITEM_FAILED = "item_failed"
    RUN_ATTEMPT = "run_attempt"
    RUN_SUCCESS = "run_success"
    RUN_FAIL = "run_fail"
    CATCH_ATTEMPT = "catch_attempt"
    CATCH_SHAKE = "catch_shake"
    CATCH_SUCCESS = "catch_success"
    CATCH_FAIL = "catch_fail"

    WEATHER_START = "weather_start"
    WEATHER_DAMAGE = "weather_damage"
    WEATHER_END = "weather_end"
    HAZARD_SET = "hazard_set"
    HAZARD_DAMAGE = "hazard_damage"
    HAZARD_CLEARED = "hazard_cleared"
    SCREEN_START = "screen_start"
    SCREEN_END = "screen_end"
    PROTECTED = "protected"              # data: setup True/False
    CHARGING = "charging"                # two-turn move, turn 1
    RECHARGING = "recharging"            # Hyper Beam family rest turn
    DRAGGED = "dragged"                  # Roar/Whirlwind forced switch
    LEECH_SEED = "leech_seed"
    LEECH_DRAIN = "leech_drain"
    TRAPPED = "trapped"
    TRAP_DAMAGE = "trap_damage"
    TRAP_END = "trap_end"
    STAGES_RESET = "stages_reset"        # Haze
    ABILITY = "ability"                  # generic ability proc
    ITEM_HELD = "item_held"              # held-item proc

    EFFECT_SKIPPED = "effect_skipped"    # honest marker for unimplemented effects
    BATTLE_END = "battle_end"


@dataclass
class Event:
    type: E
    side: str | None = None      # 'p1' | 'p2' | None
    data: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"type": self.type.value, "side": self.side, **self.data}

    def __repr__(self) -> str:  # compact for logs/tests
        return f"<{self.type.value} {self.side or ''} {self.data}>"
