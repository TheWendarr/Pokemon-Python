"""Move-effect coverage report.

Runs N random AI-vs-AI battles on the full generated dataset and counts
EFFECT_SKIPPED events against total move usage. Phase 2 acceptance:
skip rate < 5%.

    python -m pkmn.cli.coverage --battles 200 [--data game/data]
"""
from __future__ import annotations

import argparse
import random
from collections import Counter

from ..battle.ai import RandomAI
from ..battle.engine import BattleEngine, Phase
from ..battle.events import E
from ..core.pokemon import PokemonState
from ..data.repository import GameData


def run(data_dir: str, battles: int, seed: int) -> int:
    data = GameData(data_dir)
    rng = random.Random(seed)
    dex = data.all_species_ids()
    used = 0
    skipped: Counter = Counter()
    for b in range(battles):
        brng = random.Random(rng.random())
        parties = []
        for _ in range(2):
            parties.append([PokemonState.generate(
                data, brng.choice(dex), brng.randint(20, 70), rng=brng)
                for _ in range(3)])
        eng = BattleEngine(data, parties[0], parties[1], rng=brng)
        ais = {"p1": RandomAI("p1", brng), "p2": RandomAI("p2", brng)}
        for _ in range(120):
            if eng.over:
                break
            if eng.phase == Phase.WAITING_REPLACEMENT:
                for side in list(eng.pending_replacements):
                    eng.submit_replacement(side, ais[side].choose_replacement(eng))
                continue
            ev = eng.submit_turn(ais["p1"].choose_action(eng),
                                 ais["p2"].choose_action(eng))
            for e in ev:
                if e.type == E.MOVE_USED:
                    used += 1
                elif e.type == E.EFFECT_SKIPPED:
                    skipped[e.data.get("move", "?")] += 1
    n_skip = sum(skipped.values())
    rate = 100.0 * n_skip / max(1, used)
    print(f"battles={battles}  moves_used={used}  effects_skipped={n_skip}  "
          f"skip_rate={rate:.2f}%")
    if skipped:
        print("top skipped moves:")
        for move, n in skipped.most_common(15):
            print(f"  {n:4d}  {move}")
    return 0 if rate < 5.0 else 1


def main() -> None:
    import pathlib as _pl
    _data_default = str(_pl.Path(__file__).resolve().parent.parent.parent / "game" / "data")
    ap = argparse.ArgumentParser()
    ap.add_argument("--battles", type=int, default=200)
    ap.add_argument("--data", default=_data_default)
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    raise SystemExit(run(a.data, a.battles, a.seed))


if __name__ == "__main__":
    main()
