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
    # Unaware: ignore the opponent's relevant stat stages
    if passives.abil(attacker) == "unaware":
        d_stage = 0   # ignore defender's defense/sp.defense boost when attacking
    if passives.abil(defender) == "unaware":
        a_stage = 0   # ignore attacker's attack/sp.attack boost when defending
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
    # Sniper: crits do 2.25× (extra ×1.5 on top of the ×2 above)
    if crit and passives.abil(attacker) == "sniper":
        dmg = dmg * 3 // 2

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
    # Keen Eye: ignore foe's positive evasion stages
    ev_stage = defender.stages[EVASION]
    if passives.abil(attacker) == "keen-eye":
        ev_stage = min(0, ev_stage)   # only negative evasion counts
    # Snow Cloak: +1 effective evasion stage in hail
    if weather == "hail" and passives.abil(defender) == "snow-cloak":
        ev_stage = min(6, ev_stage + 1)
    # Sand Veil: +1 effective evasion stage in sandstorm
    if weather == "sandstorm" and passives.abil(defender) == "sand-veil":
        ev_stage = min(6, ev_stage + 1)
    # Tangled Feet: +2 effective evasion when holder is confused
    if passives.abil(defender) == "tangled-feet" and defender.vol.confusion_turns > 0:
        ev_stage = min(6, ev_stage + 2)
    # Bright Powder / Lax Incense: raise effective evasion of holder
    if passives.held(defender) in ("bright-powder", "lax-incense"):
        ev_stage = min(6, ev_stage + 1)
    stage = max(-6, min(6, attacker.stages[ACCURACY] - ev_stage))
    threshold = acc * accuracy_multiplier(stage)
    # Compound Eyes: x1.3 accuracy
    if passives.abil(attacker) == "compound-eyes":
        threshold *= 1.3
    # Hustle: x0.8 accuracy for physical moves
    if passives.abil(attacker) == "hustle" and move.category == "physical":
        threshold *= 0.8
    # Wide Lens: x1.1 accuracy for the holder
    if passives.held(attacker) == "wide-lens":
        threshold *= 1.1
    # Zoom Lens: x1.2 if the user moves after the target this turn
    if passives.held(attacker) == "zoom-lens" and attacker.vol.analytic_active:
        threshold *= 1.2
    # Micle Berry: +20% accuracy on next move
    if getattr(attacker.vol, "micle_next", False):
        threshold *= 1.2
    return rng.randint(1, 100) <= threshold
