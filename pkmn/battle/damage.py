"""Gen 5 damage and accuracy math.

Implements the Gen V pipeline with integer floors at each step:

    base = ((2L/5 + 2) * Power * A / D) / 50 + 2        (integer division)
    damage = base -> x2 crit -> x(R/100), R in 85..100 -> x1.5 STAB
             -> xType -> x0.5 burn (physical) -> min 1

Gen 4/5 specifics honored here (the old code had Gen 6 values):
  * Critical hits are x2.0 (x1.5 is Gen 6+) and occur at 1/16 base rate.
  * The random factor is 85-100% (not 90-100%).
  * Crits ignore the attacker's negative offensive stages and the
    defender's positive defensive stages.
"""
from __future__ import annotations

from ..core.stats import accuracy_multiplier, stage_multiplier
from ..data.models import (ACCURACY, ATTACK, DEFENSE, EVASION, PHYSICAL,
                           SP_ATTACK, SP_DEFENSE)

TYPELESS = "typeless"  # Struggle / confusion self-hit


def calc_damage(data, attacker, defender, move, *, rng,
                crit: bool = False, power_override: int | None = None) -> tuple[int, dict]:
    """Returns (damage, detail). detail carries crit/effectiveness for events.
    Assumes immunity (effectiveness 0) was checked by the caller."""
    power = power_override if power_override is not None else (move.power or 0)
    if power <= 0:
        return 0, {"effectiveness": 1.0, "crit": False}

    if move.category == PHYSICAL:
        a_key, d_key = ATTACK, DEFENSE
    else:
        a_key, d_key = SP_ATTACK, SP_DEFENSE

    a_stage = attacker.stages[a_key]
    d_stage = defender.stages[d_key]
    if crit:
        a_stage = max(0, a_stage)
        d_stage = min(0, d_stage)
    A = int(attacker.stats[a_key] * stage_multiplier(a_stage))
    D = max(1, int(defender.stats[d_key] * stage_multiplier(d_stage)))

    L = attacker.level
    dmg = ((2 * L) // 5 + 2) * power * A // D // 50 + 2

    if crit:
        dmg *= 2

    r = rng.randint(85, 100)
    dmg = dmg * r // 100

    stab = move.type != TYPELESS and move.type in attacker.types
    if stab:
        dmg = dmg * 3 // 2

    eff = 1.0 if move.type == TYPELESS else data.effectiveness(move.type, defender.types)
    dmg = int(dmg * eff)

    if move.category == PHYSICAL and attacker.status == "burn":
        dmg //= 2

    dmg = max(1, dmg)
    return dmg, {"effectiveness": eff, "crit": crit, "stab": stab, "roll": r}


def accuracy_check(move, attacker, defender, *, rng) -> bool:
    """Single accuracy roll; accuracy None never misses."""
    if move.accuracy is None:
        return True
    stage = max(-6, min(6, attacker.stages[ACCURACY] - defender.stages[EVASION]))
    threshold = move.accuracy * accuracy_multiplier(stage)
    return rng.randint(1, 100) <= threshold
