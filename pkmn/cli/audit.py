"""Dataset + implementation audit.

Reports what's in game/data (the full PokeAPI Gen 1-5 catalog) versus
what the battle engine actually implements, and cross-validates every
reference (species -> abilities, learnsets -> moves, types -> chart).

    python -m pkmn.cli.audit [--data game/data]
"""
from __future__ import annotations

import argparse
from collections import Counter

from ..battle import passives
from ..battle.moves import HANDLERS
from ..data.repository import GameData


def run(data_dir: str) -> int:
    data = GameData(data_dir)
    species = data.all_species_ids()
    abilities = data.all_ability_ids()
    items = data.all_item_ids()
    n_moves = 0
    kinds: Counter = Counter()
    for sid in []:
        pass
    import os
    move_ids = [f[:-5] for f in sorted(os.listdir(os.path.join(data_dir, "moves")))
                if f.endswith(".json")]
    for mid in move_ids:
        kinds[data.move(mid).effect.kind] += 1
        n_moves += 1

    print(f"species:   {len(species)}")
    print(f"moves:     {n_moves}  (special-case handlers: {len(HANDLERS)};"
          " runtime gap: python -m pkmn.cli.coverage)")
    used_abilities = sorted({a for sid in species for a in data.species(sid).abilities})
    impl_a = [a for a in used_abilities if a in passives.IMPLEMENTED_ABILITIES]
    print(f"abilities: {len(abilities)} in catalog, {len(used_abilities)} used by "
          f"species, {len(impl_a)} battle-implemented "
          f"({100 * len(impl_a) // max(1, len(used_abilities))}% of used)")
    mech = [i for i in items if any([
        (it := data.item(i)).heal, it.cures, it.ball_rate, it.revive,
        it.stages, it.crit, it.guard])]
    held_impl = [i for i in items if i in passives.IMPLEMENTED_HELD]
    print(f"items:     {len(items)} in catalog, {len(mech)} with bag/ball "
          f"mechanics, {len(held_impl)} held-item battle effects; the rest "
          "are data-only (inert)")
    print("move effect kinds:", dict(kinds.most_common()))

    problems = data.validate()
    if problems:
        print(f"\nVALIDATION: {len(problems)} problem(s)")
        for p in problems[:20]:
            print("  -", p)
        return 1
    print("\nVALIDATION: all cross-references resolve (species->abilities,"
          " learnsets->moves, types->chart)")
    return 0


def main() -> None:
    import pathlib as _pl
    _data_default = str(_pl.Path(__file__).resolve().parent.parent.parent / "game" / "data")
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=_data_default)
    raise SystemExit(run(ap.parse_args().data))


if __name__ == "__main__":
    main()
