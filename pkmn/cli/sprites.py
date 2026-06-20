"""Pre-warm the Gen 5 sprite cache.

Downloading sprites lazily during play means a one-time blip the first
time you meet each species. Run this once to fetch everything a game
folder can show — its dex subset, starter, wild encounters, gift
Pokemon, and every trainer's party — so play is hitch-free from then on.

    python -m pkmn.cli.sprites --game examples/triad
    python -m pkmn.cli.sprites --all            # the whole 1-649 dex
"""
from __future__ import annotations

import argparse
import json
import os

from ..data.repository import GameData
from ..game import sprites


def _species_in_party_spec(spec: str) -> list[str]:
    out = []
    for part in str(spec).split("|"):
        sid = part.strip().partition(":")[0]
        if sid:
            out.append(sid)
    return out


def species_for_game(game_dir: str) -> set[str]:
    """Every species id a game folder could put on screen."""
    found: set[str] = set()

    def load(name):
        path = os.path.join(game_dir, name)
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        return None

    manifest = load("game.json") or {}
    found.update(manifest.get("dex", []))
    if manifest.get("starter"):
        found.add(manifest["starter"]["species"])

    for table in (load("encounters.json") or {}).values():
        found.update(e["species"] for e in table)

    def walk_scripts(steps):
        for step in steps if isinstance(steps, list) else []:
            if "battle" in step:
                found.update(_species_in_party_spec(
                    step["battle"].get("party", "")))
            if "give_pokemon" in step:
                found.add(step["give_pokemon"]["species"])
            if "if_flag" in step:
                walk_scripts(step.get("then", []))
                walk_scripts(step.get("else", []))
            if "if_money" in step:
                walk_scripts(step.get("then", []))
                walk_scripts(step.get("else", []))
            if "choice" in step:
                for o in step["choice"].get("options", []):
                    walk_scripts(o.get("then", []))
    for steps in (load("scripts.json") or {}).values():
        walk_scripts(steps)

    # trainer parties declared in the maps themselves
    try:
        import pytmx
        mdir = os.path.join(game_dir, "maps")
        for fn in os.listdir(mdir) if os.path.isdir(mdir) else []:
            if not fn.endswith(".tmx"):
                continue
            tm = pytmx.TiledMap(os.path.join(mdir, fn))
            for obj in tm.objects:
                if obj.name == "trainer":
                    found.update(_species_in_party_spec(
                        obj.properties.get("party", "")))
    except Exception:
        pass
    return found


def run(dexes: list[int]) -> int:
    sprites.FETCH_ENABLED = True
    fetched = cached = failed = 0
    for dex in dexes:
        for back in (False, True):
            existed = os.path.exists(sprites.cache_path(dex, back=back))
            path = sprites.sprite_path(dex, back=back)
            if path is None:
                failed += 1
            elif existed:
                cached += 1
            else:
                fetched += 1
    print(f"sprites: {fetched} fetched, {cached} already cached, "
          f"{failed} unavailable -> {sprites.default_cache_dir()}")
    return 0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", default="game/assets")
    ap.add_argument("--data", default="game/data")
    ap.add_argument("--all", action="store_true",
                    help="warm the full 1-649 national dex")
    a = ap.parse_args()
    data = GameData(a.data)
    if a.all:
        dexes = sorted({data.species(sid).dex for sid in data.all_species_ids()})
    else:
        dexes = sorted({d for sid in species_for_game(a.game)
                        if (d := getattr(_safe_species(data, sid), "dex", 0))})
    print(f"warming {len(dexes)} species "
          f"({'full dex' if a.all else a.game})...")
    raise SystemExit(run(dexes))


def _safe_species(data, sid):
    try:
        return data.species(sid)
    except Exception:
        return None


if __name__ == "__main__":
    main()
