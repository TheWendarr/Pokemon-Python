"""Stat math: Gen 4/5 stat formulas, natures, and stage multipliers.

Stage multipliers use the exact game fractions ((2+n)/2 and 2/(2+n)),
not decimal approximations -- the old code's 0.28/0.33/0.40 table was a
Gen 1 approximation that produces off-by-one damage everywhere.
"""
from __future__ import annotations

from ..data.models import HP, STAT_KEYS


def calc_stat(stat: str, base: int, iv: int, ev: int, level: int,
              nature_mod: float = 1.0) -> int:
    """Gen 3+ stat formula (integer math, floors where the games floor)."""
    if stat == HP:
        if base == 1:  # Shedinja
            return 1
        return ((2 * base + iv + ev // 4) * level) // 100 + level + 10
    raw = ((2 * base + iv + ev // 4) * level) // 100 + 5
    return int(raw * nature_mod)


def calc_all_stats(base_stats: dict, ivs: dict, evs: dict, level: int,
                   nature: dict) -> dict:
    """nature: {'up': stat|None, 'down': stat|None} (already canonical)."""
    out = {}
    for stat in STAT_KEYS:
        mod = 1.0
        if nature.get("up") == stat:
            mod = 1.1
        elif nature.get("down") == stat:
            mod = 0.9
        out[stat] = calc_stat(stat, base_stats[stat], ivs.get(stat, 0),
                              evs.get(stat, 0), level, mod)
    return out


def stage_multiplier(stage: int) -> float:
    """Attack/Defense/Speed stage multiplier, exact Gen 3+ fractions."""
    stage = max(-6, min(6, stage))
    return (2 + stage) / 2 if stage >= 0 else 2 / (2 - stage)


def accuracy_multiplier(stage: int) -> float:
    """Accuracy/Evasion combined-stage multiplier (3-based fractions)."""
    stage = max(-6, min(6, stage))
    return (3 + stage) / 3 if stage >= 0 else 3 / (3 - stage)


# Gen 5 critical-hit chance by crit stage.
CRIT_CHANCE = {0: 1 / 16, 1: 1 / 8, 2: 1 / 4, 3: 1 / 3}


def crit_chance(stage: int) -> float:
    return CRIT_CHANCE.get(stage, 1 / 2)  # stage 4+ caps at 1/2
