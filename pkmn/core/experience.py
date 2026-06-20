"""Experience curves (total EXP required to be at a given level).

PokeAPI growth-rate identifiers map to the standard mainline formulas;
the two piecewise curves use their canonical breakpoints.
"""
from __future__ import annotations


def _erratic(n):  # PokeAPI: 'slow-then-very-fast'
    if n < 50:
        return n ** 3 * (100 - n) // 50
    if n < 68:
        return n ** 3 * (150 - n) // 100
    if n < 98:
        return n ** 3 * ((1911 - 10 * n) // 3) // 500
    return n ** 3 * (160 - n) // 100


def _fluctuating(n):  # PokeAPI: 'fast-then-very-slow'
    if n < 15:
        return n ** 3 * ((n + 1) // 3 + 24) // 50
    if n < 36:
        return n ** 3 * (n + 14) // 50
    return n ** 3 * (n // 2 + 32) // 50


CURVES = {
    "medium": lambda n: n ** 3,
    "medium-fast": lambda n: n ** 3,
    "fast": lambda n: 4 * n ** 3 // 5,
    "slow": lambda n: 5 * n ** 3 // 4,
    "medium-slow": lambda n: 6 * n ** 3 // 5 - 15 * n ** 2 + 100 * n - 140,
    "slow-then-very-fast": _erratic,
    "fast-then-very-slow": _fluctuating,
}


def exp_total(rate: str, level: int) -> int:
    """Total EXP at the moment of reaching `level`."""
    if level <= 1:
        return 0
    return max(0, CURVES.get(rate, CURVES["medium"])(level))


def level_for_exp(rate: str, exp: int) -> int:
    lvl = 1
    while lvl < 100 and exp >= exp_total(rate, lvl + 1):
        lvl += 1
    return lvl


def battle_exp(base_experience: int, foe_level: int, *,
               trainer: bool = False, winner_level: int | None = None,
               participants: int = 1) -> int:
    """EXP for defeating a Pokemon.

    With `winner_level` given, uses the Gen 5 scaled formula, which rewards
    beating higher-level foes and tapers as you out-level them:

        ((base * L) / (5*s)) * a * (2L+10)^2.5 / (L+Lp+10)^2.5 + 1

    (L = foe level, Lp = winner level, s = participants, a = 1.5 for
    trainer battles). Without `winner_level` it falls back to the classic
    flat award, so callers that don't know the winner still work."""
    b, L = base_experience, foe_level
    if winner_level is None:
        exp = b * L // 7
        if trainer:
            exp = exp * 3 // 2
        return max(1, exp)
    s, Lp = max(1, participants), winner_level
    a = 1.5 if trainer else 1.0
    scaled = (b * L / (5.0 * s)) * a
    scaled *= ((2 * L + 10) ** 2.5) / ((L + Lp + 10) ** 2.5)
    return max(1, int(scaled) + 1)
