"""Baseline battle AIs.

RandomAI: picks any legal move (wild-Pokemon behavior).
GreedyAI: picks the move with the highest expected damage (no crit,
average roll), switching only when forced. Roughly "good trainer class"
strength. Phase 2 adds smarter tiers (status valuation, switch logic,
setup awareness).
"""
from __future__ import annotations

import random
from typing import Optional

from . import moves as movex
from .damage import calc_damage
from .engine import BattleEngine
from .state import MoveAction, SwitchAction, other


class _AvgRoll(random.Random):
    """RNG stub that returns the average damage roll and never crits."""
    def randint(self, a, b):
        return (a + b) // 2
    def random(self):
        return 1.0


class RandomAI:
    def __init__(self, side: str, rng: Optional[random.Random] = None):
        self.side = side
        self.rng = rng or random.Random()

    def choose_action(self, eng: BattleEngine):
        moves = [a for a in eng.legal_actions(self.side) if isinstance(a, MoveAction)]
        return self.rng.choice(moves)

    def choose_actions(self, eng: BattleEngine, n: int = 1) -> list:
        """Return n actions (1 for singles, 2 for doubles). Doubles picks
        random moves targeting foe slot 0."""
        out = []
        for slot in range(n):
            moves = [a for a in eng.legal_actions(self.side, slot)
                     if isinstance(a, MoveAction)]
            if not moves:
                out.append(MoveAction("struggle", target_slot=0))
                continue
            a = self.rng.choice(moves)
            out.append(MoveAction(a.move_id, target_slot=0)
                       if a.target_slot < 0 else a)
        return out

    def choose_replacement(self, eng: BattleEngine, slot: int = 0) -> int:
        return self.rng.choice(eng.bench(self.side))


class GreedyAI:
    def __init__(self, side: str, rng: Optional[random.Random] = None):
        self.side = side
        self.rng = rng or random.Random()
        self._avg = _AvgRoll()

    def _expected_damage(self, eng, move_id: str) -> float:
        if move_id == "recharge":
            return 0.0
        move = movex.STRUGGLE if move_id == "struggle" else eng.data.move(move_id)
        user, target = eng.active(self.side), eng.active(other(self.side))
        if not move.is_damaging or move.power is None:
            return 0.0
        if move.type != "typeless" \
                and eng.data.effectiveness(move.type, target.types) == 0:
            return 0.0
        dmg, _ = calc_damage(eng.data, user, target, move, rng=self._avg,
                             crit=False, weather=eng.weather)
        hit_rate = (move.accuracy or 100) / 100
        hits = move.effect.min_hits or 1
        score = dmg * hit_rate * hits
        if dmg >= target.current_hp:    # prefer finishing the target off
            score += 1000 * hit_rate
        return score

    def choose_action(self, eng: BattleEngine):
        moves = [a for a in eng.legal_actions(self.side) if isinstance(a, MoveAction)]
        scored = [(self._expected_damage(eng, a.move_id), self.rng.random(), a)
                  for a in moves]
        scored.sort(reverse=True, key=lambda t: (t[0], t[1]))
        best_dmg, _, best = scored[0]
        if best_dmg <= 0:  # nothing damaging: pick a random (likely status) move
            return self.rng.choice(moves)
        return best

    def choose_actions(self, eng: BattleEngine, n: int = 1) -> list:
        """Return n actions (1 for singles, 2 for doubles). Doubles targets
        foe slot 0 by default and picks each slot's own highest-damage move."""
        out = []
        for slot in range(n):
            moves = [a for a in eng.legal_actions(self.side, slot)
                     if isinstance(a, MoveAction)]
            if not moves:
                out.append(MoveAction("struggle", target_slot=0))
                continue
            scored = [(self._expected_damage(eng, a.move_id), self.rng.random(), a)
                      for a in moves]
            scored.sort(reverse=True, key=lambda t: (t[0], t[1]))
            best_dmg, _, best = scored[0]
            a = best if best_dmg > 0 else self.rng.choice(moves)
            out.append(MoveAction(a.move_id, target_slot=0)
                       if a.target_slot < 0 else a)
        return out

    def choose_replacement(self, eng: BattleEngine, slot: int = 0) -> int:
        # Send the benched Pokemon with the highest remaining HP fraction.
        bench = eng.bench(self.side)
        return max(bench, key=lambda i: eng.parties[self.side][i].current_hp
                   / eng.parties[self.side][i].max_hp)
