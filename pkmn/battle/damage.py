"""Gen 5 damage and accuracy math (now weather/ability/item aware).

Pipeline with integer floors:
    base = ((2L/5 + 2) * Power * A / D) / 50 + 2
    -> x2 crit -> x(R/100), R in 85..100 -> STAB (1.5 or 2.0 Adaptability)
    -> xType -> xFilter/Multiscale -> burn -> screens/Life Orb -> min 1

Gen 4/5 specifics honored: 2.0x crits at 1/16 base, 85-100% rolls,
crits ignoring helpful stages and screens.
"""
from __future__ import annotations

from ..core.stats import accuracy_multiplier, stage_multiplier
from ..data.models import (ACCURACY, ATTACK, DEFENSE, EVASION, PHYSICAL,
                           SP_ATTACK, SP_DEFENSE)
from . import passives

TYPELESS = "typeless"  # Struggle / confusion self-hit


def _variable_power(attacker, move) -> int:
    """Power for moves whose base power is computed from battle state.
    Return scales up with friendship; Frustration scales up as it drops."""
    fr = getattr(getattr(attacker, "state", None), "friendship", 70)
    if move.id == "return":
        return max(1, fr * 2 // 5)             # up to 102 at max friendship
    if move.id == "frustration":
        return max(1, (255 - fr) * 2 // 5)     # up to 102 at min friendship
    return move.power or 0


def calc_damage(data, attacker, defender, move, *, rng, crit: bool = False,
                weather: str | None = None, screened: bool = False,
                power_mult: float = 1.0) -> tuple[int, dict]:
    """Returns (damage, detail). Assumes immunity was checked by caller."""
    power = _variable_power(attacker, move)
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
    if move.category == PHYSICAL:
        D = max(1, int(D * passives.def_mod(defender, move)))
    else:
        D = max(1, int(D * passives.spdef_mod(defender, move, weather)))

    L = attacker.level
    dmg = ((2 * L) // 5 + 2) * power * A // D // 50 + 2

    if crit:
        dmg *= 2

    r = rng.randint(85, 100)
    dmg = dmg * r // 100

    stab = move.type != TYPELESS and move.type in attacker.types
    if stab:
        stab_mult = passives.stab_mod(attacker, move)
        dmg = int(dmg * stab_mult)

    eff = 1.0 if move.type == TYPELESS else data.effectiveness(move.type, defender.types)
    dmg = int(dmg * eff)

    # Tinted Lens: resisted moves x2
    if eff < 1.0 and passives.abil(attacker) == "tinted-lens":
        dmg *= 2

    # Defender damage modifiers (Filter, Solid Rock, Multiscale, Shadow Shield)
    dmg = int(dmg * passives.defender_damage_mod(defender, eff))

    # Expert Belt: attacker bonus for super-effective hits
    dmg = int(dmg * passives.attacker_eff_bonus(attacker, eff))

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
    # No Guard: always hit
    if passives.abil(attacker) == "no-guard" or passives.abil(defender) == "no-guard":
        return True
    if move.accuracy is None:
        return True
    if weather == "rain" and move.id in ("thunder", "hurricane"):
        return True
    if weather == "hail" and move.id == "blizzard":
        return True
    acc = move.accuracy
    if weather == "sun" and move.id in ("thunder", "hurricane"):
        acc = 50
    # Wonder Skin: non-damaging moves targeting defender have 50% accuracy
    if passives.abil(defender) == "wonder-skin" and not move.is_damaging:
        acc = min(acc, 50)
    stage = max(-6, min(6, attacker.stages[ACCURACY] - defender.stages[EVASION]))
    threshold = acc * accuracy_multiplier(stage)
    # Compound Eyes: x1.3 accuracy
    if passives.abil(attacker) == "compound-eyes":
        threshold *= 1.3
    # Hustle: x0.8 accuracy for physical moves
    if passives.abil(attacker) == "hustle" and move.category == "physical":
        threshold *= 0.8
    return rng.randint(1, 100) <= threshold
