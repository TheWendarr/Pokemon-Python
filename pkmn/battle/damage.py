"""Gen 5 damage and accuracy math (now weather/ability/item aware).

Pipeline with integer floors:
    base = ((2L/5 + 2) * Power * A / D) / 50 + 2
    -> x2 crit -> x(R/100), R in 85..100 -> x1.5 STAB -> xType
    -> x0.5 burn (physical, unless Guts) -> screens/Life Orb -> min 1

Gen 4/5 specifics honored: 2.0x crits at 1/16 base, 85-100% rolls,
crits ignoring helpful stages and screens.
"""
from __future__ import annotations

from ..core.stats import accuracy_multiplier, stage_multiplier
from ..data.models import (ACCURACY, ATTACK, DEFENSE, EVASION, PHYSICAL,
                           SP_ATTACK, SP_DEFENSE)
from . import passives

TYPELESS = "typeless"  # Struggle / confusion self-hit


def calc_damage(data, attacker, defender, move, *, rng, crit: bool = False,
                weather: str | None = None, screened: bool = False,
                power_mult: float = 1.0) -> tuple[int, dict]:
    """Returns (damage, detail). Assumes immunity was checked by caller."""
    power = move.power or 0
    if power <= 0:
        return 0, {"effectiveness": 1.0, "crit": False}
    power = max(1, int(power * power_mult
                       * passives.power_mod(attacker, defender, move, weather)))

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
    A = int(A * passives.attack_stat_mod(attacker, move))
    D = max(1, int(defender.stats[d_key] * stage_multiplier(d_stage)))
    D = max(1, int(D * passives.spdef_mod(defender, move, weather)))

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

    if move.category == PHYSICAL and attacker.status == "burn" \
            and not passives.burn_ignored(attacker):
        dmg //= 2

    dmg = int(dmg * passives.final_mod(attacker, crit, screened))

    dmg = max(1, dmg)
    return dmg, {"effectiveness": eff, "crit": crit, "stab": stab, "roll": r}


def accuracy_check(move, attacker, defender, *, rng,
                   weather: str | None = None) -> bool:
    """Single accuracy roll; accuracy None never misses. Weather perfect-
    accuracy interactions: Thunder/Hurricane in rain, Blizzard in hail."""
    if move.accuracy is None:
        return True
    if weather == "rain" and move.id in ("thunder", "hurricane"):
        return True
    if weather == "hail" and move.id == "blizzard":
        return True
    acc = move.accuracy
    if weather == "sun" and move.id in ("thunder", "hurricane"):
        acc = 50
    stage = max(-6, min(6, attacker.stages[ACCURACY] - defender.stages[EVASION]))
    threshold = acc * accuracy_multiplier(stage)
    return rng.randint(1, 100) <= threshold
