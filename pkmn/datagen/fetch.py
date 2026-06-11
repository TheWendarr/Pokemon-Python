"""PokeAPI -> game data pipeline.

Generates the game data folder consumed by pkmn.data.repository.GameData:
species 001-649 (Gen 1-5), all Gen 1-5 moves with *Gen 5* values, the
Gen 5 type chart, natures, and a curated starter item set.

Two sources:

  --source rest    pokeapi.co REST API (default; run this at home).
                   Applies each move's `past_values` changelog so you get
                   Gen 5 numbers (e.g. Thunderbolt 95 power, not 90).
                   Responses are cached on disk, so re-runs are cheap.
  --source csv     PokeAPI's raw CSV dumps on GitHub. Same output; used
                   where pokeapi.co isn't reachable. Applies
                   move_changelog.csv for Gen 5 values when available.

Sprites (--sprites, REST-independent) download from the PokeAPI sprites
repo for personal use. Note: sprite artwork is Nintendo/Game Freak IP --
fine to use locally, but don't redistribute it inside shared game folders.

Usage:
    pkmn-fetch-data --out game/data
    pkmn-fetch-data --out game/data --source csv
    pkmn-fetch-data --out game/data --sprites
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import sys
import time
import urllib.error
import urllib.request

REST_BASE = "https://pokeapi.co/api/v2"
CSV_BASE = "https://raw.githubusercontent.com/PokeAPI/pokeapi/master/data/v2/csv"
SPRITE_BASE = ("https://raw.githubusercontent.com/PokeAPI/sprites/master/"
               "sprites/pokemon/versions/generation-v/black-white")

MAX_DEX = 649          # Genesect
GEN5_VGS = (14, 11)    # black-2-white-2, then black-white fallback
LAST_GEN5_VG = 14
GEN = 5

# Ordered version-group identifiers for REST past_values reconstruction.
VG_ORDER = ["red-blue", "yellow", "gold-silver", "crystal", "ruby-sapphire",
            "emerald", "firered-leafgreen", "diamond-pearl", "platinum",
            "heartgold-soulsilver", "black-white", "colosseum", "xd",
            "black-2-white-2", "x-y", "omega-ruby-alpha-sapphire",
            "sun-moon", "ultra-sun-ultra-moon", "lets-go-pikachu-lets-go-eevee",
            "sword-shield", "the-isle-of-armor", "the-crown-tundra",
            "brilliant-diamond-and-shining-pearl", "legends-arceus",
            "scarlet-violet", "the-teal-mask", "the-indigo-disk"]

STAT_ID_TO_KEY = {1: "hp", 2: "attack", 3: "defense", 4: "special_attack",
                  5: "special_defense", 6: "speed", 7: "accuracy", 8: "evasion"}
DAMAGE_CLASS = {1: "status", 2: "physical", 3: "special"}

CURATED_ITEMS = {
    "potion":        {"name": "Potion", "category": "medicine", "heal": 20},
    "super-potion":  {"name": "Super Potion", "category": "medicine", "heal": 50},
    "hyper-potion":  {"name": "Hyper Potion", "category": "medicine", "heal": 200},
    "max-potion":    {"name": "Max Potion", "category": "medicine", "heal": "full"},
    "full-restore":  {"name": "Full Restore", "category": "medicine",
                      "heal": "full", "cures": ["all"]},
    "antidote":      {"name": "Antidote", "category": "medicine",
                      "cures": ["poison", "toxic"]},
    "burn-heal":     {"name": "Burn Heal", "category": "medicine", "cures": ["burn"]},
    "ice-heal":      {"name": "Ice Heal", "category": "medicine", "cures": ["freeze"]},
    "awakening":     {"name": "Awakening", "category": "medicine", "cures": ["sleep"]},
    "paralyze-heal": {"name": "Paralyze Heal", "category": "medicine",
                      "cures": ["paralysis"]},
    "full-heal":     {"name": "Full Heal", "category": "medicine", "cures": ["all"]},
    "poke-ball":     {"name": "Poke Ball", "category": "ball", "ball_rate": 1.0},
    "great-ball":    {"name": "Great Ball", "category": "ball", "ball_rate": 1.5},
    "ultra-ball":    {"name": "Ultra Ball", "category": "ball", "ball_rate": 2.0},
    # ── held items (battle effects implemented in pkmn/battle/passives.py) ──
    "leftovers":     {"name": "Leftovers", "category": "held"},
    "oran-berry":    {"name": "Oran Berry", "category": "held"},
    "sitrus-berry":  {"name": "Sitrus Berry", "category": "held"},
    "lum-berry":     {"name": "Lum Berry", "category": "held"},
    "choice-band":   {"name": "Choice Band", "category": "held"},
    "choice-specs":  {"name": "Choice Specs", "category": "held"},
    "choice-scarf":  {"name": "Choice Scarf", "category": "held"},
    "life-orb":      {"name": "Life Orb", "category": "held"},
    "focus-sash":    {"name": "Focus Sash", "category": "held"},
    "scope-lens":    {"name": "Scope Lens", "category": "held"},
    "razor-claw":    {"name": "Razor Claw", "category": "held"},
}


# ── plumbing ─────────────────────────────────────────────────────────

def _fetch(url: str, cache_dir: str, *, binary: bool = False, retries: int = 3):
    os.makedirs(cache_dir, exist_ok=True)
    key = url.replace("https://", "").replace("/", "_").replace("?", "_")
    path = os.path.join(cache_dir, key)
    if os.path.exists(path):
        mode = "rb" if binary else "r"
        with open(path, mode) as f:
            return f.read()
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "pkmn-fetch/0.1"})
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            if not binary:
                data = data.decode("utf-8")
            with open(path, "wb" if binary else "w") as f:
                f.write(data)
            return data
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise
            last = e
        except Exception as e:  # noqa: BLE001
            last = e
        time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Failed to fetch {url}: {last}")


def _rest(path: str, cache_dir: str) -> dict:
    return json.loads(_fetch(f"{REST_BASE}/{path}", cache_dir))


def _csv_rows(name: str, cache_dir: str) -> list[dict]:
    text = _fetch(f"{CSV_BASE}/{name}", cache_dir)
    return list(csv.DictReader(io.StringIO(text)))


def _write(path: str, obj) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1)


def _patch_gen5_type_chart(chart: dict) -> dict:
    """Drop Fairy and restore Gen 2-5 Steel resistances to Ghost/Dark."""
    chart = {a: {d: m for d, m in row.items() if d != "fairy"}
             for a, row in chart.items() if a != "fairy"}
    chart.setdefault("ghost", {})["steel"] = 0.5
    chart.setdefault("dark", {})["steel"] = 0.5
    return chart


# ── CSV source ───────────────────────────────────────────────────────

def build_from_csv(out: str, cache: str, *, log=print) -> None:
    log("Downloading PokeAPI CSV tables from GitHub...")
    types_rows = _csv_rows("types.csv", cache)
    type_by_id = {int(r["id"]): r["identifier"] for r in types_rows
                  if int(r["id"]) < 10000}
    gen5_types = {tid: ident for tid, ident in type_by_id.items()
                  if ident != "fairy"}

    # type chart
    chart: dict = {type_by_id[i]: {} for i in gen5_types}
    for r in _csv_rows("type_efficacy.csv", cache):
        a, d = int(r["damage_type_id"]), int(r["target_type_id"])
        if a in gen5_types and d in gen5_types:
            chart[type_by_id[a]][type_by_id[d]] = int(r["damage_factor"]) / 100
    _write(os.path.join(out, "types.json"), _patch_gen5_type_chart(chart))
    log("  types.json written")

    # natures
    natures = {}
    for r in _csv_rows("natures.csv", cache):
        up = STAT_ID_TO_KEY.get(int(r["increased_stat_id"]))
        down = STAT_ID_TO_KEY.get(int(r["decreased_stat_id"]))
        natures[r["identifier"]] = {"up": up if up != down else None,
                                    "down": down if up != down else None}
    _write(os.path.join(out, "natures.json"), natures)
    log(f"  natures.json written ({len(natures)} natures)")

    _write(os.path.join(out, "items.json"), CURATED_ITEMS)
    log("  items.json written (curated starter set)")

    # moves
    targets = {int(r["id"]): r["identifier"] for r in _csv_rows("move_targets.csv", cache)}
    ailments = {int(r["id"]): r["identifier"]
                for r in _csv_rows("move_meta_ailments.csv", cache)}
    categories = {int(r["id"]): r["identifier"]
                  for r in _csv_rows("move_meta_categories.csv", cache)}
    flags = {int(r["id"]): r["identifier"] for r in _csv_rows("move_flags.csv", cache)}
    flag_map: dict[int, list] = {}
    for r in _csv_rows("move_flag_map.csv", cache):
        flag_map.setdefault(int(r["move_id"]), []).append(flags[int(r["move_flag_id"])])
    meta = {int(r["move_id"]): r for r in _csv_rows("move_meta.csv", cache)}
    stat_changes: dict[int, list] = {}
    for r in _csv_rows("move_meta_stat_changes.csv", cache):
        stat_changes.setdefault(int(r["move_id"]), []).append(
            {"stat": STAT_ID_TO_KEY[int(r["stat_id"])], "change": int(r["change"])})

    changelog: dict[int, list] = {}
    try:
        for r in _csv_rows("move_changelog.csv", cache):
            changelog.setdefault(int(r["move_id"]), []).append(r)
        log(f"  move_changelog.csv applied for Gen {GEN} values")
    except Exception:
        log("  WARNING: move_changelog.csv unavailable; a few moves will "
            "carry post-Gen-5 values. REST mode reconstructs them exactly.")

    def _i(v):
        return int(v) if v not in ("", None) else None

    n_moves = 0
    for r in _csv_rows("moves.csv", cache):
        mid = int(r["id"])
        if int(r["generation_id"]) > GEN or mid >= 10000:
            continue
        type_id = int(r["type_id"])
        # 18 == fairy: Gen <=5 moves retyped to fairy in Gen 6 (Sweet Kiss,
        # Charm, Moonlight) get their original type restored by the
        # changelog walk below; true fairy moves die at the post-walk check.
        if type_id not in gen5_types and type_id not in (18, 10001):
            continue
        vals = {"power": _i(r["power"]), "pp": _i(r["pp"]),
                "accuracy": _i(r["accuracy"]), "priority": int(r["priority"]),
                "type_id": type_id}
        # Walk changes that happened *after* Gen 5 back to front; the final
        # state is the move as of B2W2.
        for ch in sorted(changelog.get(mid, []),
                         key=lambda c: int(c["changed_in_version_group_id"]),
                         reverse=True):
            if int(ch["changed_in_version_group_id"]) <= LAST_GEN5_VG:
                continue
            for k in ("power", "pp", "accuracy", "priority", "type_id"):
                if ch.get(k):
                    vals[k] = int(ch[k])
        if vals["type_id"] not in gen5_types:
            continue
        m = meta.get(mid, {})
        ailment_id = int(m.get("meta_ailment_id") or 0)
        move = {
            "id": r["identifier"],
            "name": r["identifier"].replace("-", " ").title(),
            "type": type_by_id[vals["type_id"]],
            "category": DAMAGE_CLASS[int(r["damage_class_id"])],
            "power": vals["power"],
            "accuracy": vals["accuracy"],
            "pp": vals["pp"] or 5,
            "priority": vals["priority"],
            "target": targets.get(int(r["target_id"]), "selected-pokemon"),
            "crit_stage": int(m.get("crit_rate") or 0),
            "flags": sorted(flag_map.get(mid, [])),
            "effect": {
                "kind": categories.get(int(m.get("meta_category_id") or 0), "damage"),
                "ailment": (ailments.get(ailment_id) if ailment_id > 0 else None),
                "ailment_chance": int(m.get("ailment_chance") or 0),
                "stat_changes": stat_changes.get(mid, []),
                "stat_chance": int(m.get("stat_chance") or 0),
                "flinch_chance": int(m.get("flinch_chance") or 0),
                "drain": int(m.get("drain") or 0),
                "healing": int(m.get("healing") or 0),
                "min_hits": _i(m.get("min_hits")),
                "max_hits": _i(m.get("max_hits")),
            },
        }
        _write(os.path.join(out, "moves", f"{r['identifier']}.json"), move)
        n_moves += 1
    log(f"  {n_moves} moves written")

    # species
    log("  downloading pokemon_moves.csv (large, one-time)...")
    learn: dict[int, dict[str, list]] = {}
    move_ident = {int(r["id"]): r["identifier"] for r in _csv_rows("moves.csv", cache)}
    best_vg: dict[int, int] = {}
    rows_by_pkmn: dict[int, list] = {}
    for r in _csv_rows("pokemon_moves.csv", cache):
        pid = int(r["pokemon_id"])
        if pid > MAX_DEX:
            continue
        vg = int(r["version_group_id"])
        if vg not in GEN5_VGS:
            continue
        cur = best_vg.get(pid)
        if cur is None or (vg == GEN5_VGS[0] and cur != GEN5_VGS[0]):
            if cur != vg:
                rows_by_pkmn[pid] = []
            best_vg[pid] = vg
        if vg == best_vg[pid]:
            rows_by_pkmn[pid].append(r)
    METHODS = {1: "level_up", 2: "egg", 3: "tutor", 4: "machine"}
    for pid, rows in rows_by_pkmn.items():
        sets: dict[str, list] = {"level_up": [], "egg": [], "tutor": [], "machine": []}
        for r in sorted(rows, key=lambda x: (int(x["pokemon_move_method_id"]),
                                             int(x["level"] or 0),
                                             int(x["order"] or 0)
                                             if x.get("order") else 0)):
            method = METHODS.get(int(r["pokemon_move_method_id"]))
            if method is None:
                continue
            ident = move_ident[int(r["move_id"])]
            if method == "level_up":
                sets[method].append({"move": ident, "level": int(r["level"])})
            elif ident not in sets[method]:
                sets[method].append(ident)
        learn[pid] = sets

    species_rows = {int(r["id"]): r for r in _csv_rows("pokemon_species.csv", cache)}
    growth = {int(r["id"]): r["identifier"] for r in _csv_rows("growth_rates.csv", cache)}
    stats_by_pkmn: dict[int, dict] = {}
    for r in _csv_rows("pokemon_stats.csv", cache):
        pid = int(r["pokemon_id"])
        if pid <= MAX_DEX:
            stats_by_pkmn.setdefault(pid, {})[STAT_ID_TO_KEY[int(r["stat_id"])]] = \
                int(r["base_stat"])
    types_by_pkmn: dict[int, list] = {}
    for r in _csv_rows("pokemon_types.csv", cache):
        pid = int(r["pokemon_id"])
        if pid <= MAX_DEX:
            types_by_pkmn.setdefault(pid, []).append(
                (int(r["slot"]), type_by_id[int(r["type_id"])]))
    abil_ident = {int(r["id"]): r["identifier"] for r in _csv_rows("abilities.csv", cache)}
    abil_by_pkmn: dict[int, list] = {}
    for r in _csv_rows("pokemon_abilities.csv", cache):
        pid = int(r["pokemon_id"])
        if pid <= MAX_DEX:
            abil_by_pkmn.setdefault(pid, []).append(
                (int(r["is_hidden"]), int(r["slot"]), abil_ident[int(r["ability_id"])]))

    n_species = 0
    for r in _csv_rows("pokemon.csv", cache):
        pid = int(r["id"])
        if pid > MAX_DEX:
            continue
        sp = species_rows[int(r["species_id"])]
        species = {
            "id": r["identifier"],
            "name": r["identifier"].replace("-", " ").title(),
            "dex": pid,
            "types": [t for _, t in sorted(types_by_pkmn[pid])],
            "base_stats": stats_by_pkmn[pid],
            "abilities": [a for _, _, a in sorted(abil_by_pkmn.get(pid, []))],
            "base_experience": int(r["base_experience"] or 0),
            "growth_rate": growth.get(int(sp["growth_rate_id"]), "medium"),
            "catch_rate": int(sp["capture_rate"]),
            "gender_rate": int(sp["gender_rate"]),
            "learnset": learn.get(pid, {}),
        }
        _write(os.path.join(out, "species", f"{pid:03d}-{r['identifier']}.json"), species)
        n_species += 1
    log(f"  {n_species} species written")


# ── REST source ──────────────────────────────────────────────────────

def _gen5_move_values(mv: dict) -> dict:
    """Apply past_values back to B2W2: latest-first, each change strictly
    after Gen 5 overrides, ending at the Gen 5 state."""
    vals = {"power": mv.get("power"), "accuracy": mv.get("accuracy"),
            "pp": mv.get("pp"), "type": mv["type"]["name"]}
    def order(vg_name): return VG_ORDER.index(vg_name) if vg_name in VG_ORDER else 999
    cutoff = order("black-2-white-2")
    past = sorted(mv.get("past_values", []),
                  key=lambda p: order(p["version_group"]["name"]), reverse=True)
    for p in past:
        if order(p["version_group"]["name"]) <= cutoff:
            continue
        for k in ("power", "accuracy", "pp"):
            if p.get(k) is not None:
                vals[k] = p[k]
        if p.get("type"):
            vals["type"] = p["type"]["name"]
    return vals


def build_from_rest(out: str, cache: str, *, delay: float = 0.0, log=print) -> None:
    log("Building from pokeapi.co REST API (cached; first run takes a while)...")
    # type chart
    chart: dict = {}
    type_list = _rest("type?limit=100", cache)["results"]
    gen5_names = []
    for t in type_list:
        td = _rest(f"type/{t['name']}", cache)
        gen_url = td["generation"]["url"].rstrip("/").rsplit("/", 1)[-1]
        if int(gen_url) > GEN or t["name"] in ("unknown", "shadow", "stellar"):
            continue
        gen5_names.append(t["name"])
    for name in gen5_names:
        td = _rest(f"type/{name}", cache)
        row = {d: 1.0 for d in gen5_names}
        dr = td["damage_relations"]
        for rel, mult in (("no_damage_to", 0.0), ("half_damage_to", 0.5),
                          ("double_damage_to", 2.0)):
            for tgt in dr[rel]:
                if tgt["name"] in row:
                    row[tgt["name"]] = mult
        chart[name] = row
        if delay:
            time.sleep(delay)
    _write(os.path.join(out, "types.json"), _patch_gen5_type_chart(chart))
    log("  types.json written")

    natures = {}
    for n in _rest("nature?limit=100", cache)["results"]:
        nd = _rest(f"nature/{n['name']}", cache)
        natures[nd["name"]] = {
            "up": (nd["increased_stat"]["name"].replace("-", "_")
                   if nd["increased_stat"] else None),
            "down": (nd["decreased_stat"]["name"].replace("-", "_")
                     if nd["decreased_stat"] else None)}
    _write(os.path.join(out, "natures.json"), natures)
    _write(os.path.join(out, "items.json"), CURATED_ITEMS)
    log(f"  natures.json ({len(natures)}) + items.json written")

    # moves
    n_moves = 0
    move_list = _rest("move?limit=2000", cache)["results"]
    for entry in move_list:
        mv = _rest(f"move/{entry['name']}", cache)
        gen_name = mv["generation"]["name"]
        gen_num = {"generation-i": 1, "generation-ii": 2, "generation-iii": 3,
                   "generation-iv": 4, "generation-v": 5}.get(gen_name, 99)
        if gen_num > GEN:
            continue
        vals = _gen5_move_values(mv)
        if vals["type"] not in gen5_names:
            continue
        meta = mv.get("meta") or {}
        move = {
            "id": mv["name"],
            "name": next((n["name"] for n in mv["names"]
                          if n["language"]["name"] == "en"),
                         mv["name"].replace("-", " ").title()),
            "type": vals["type"],
            "category": mv["damage_class"]["name"],
            "power": vals["power"],
            "accuracy": vals["accuracy"],
            "pp": vals["pp"] or 5,
            "priority": mv["priority"],
            "target": mv["target"]["name"],
            "crit_stage": meta.get("crit_rate") or 0,
            "flags": [],
            "effect": {
                "kind": (meta.get("category") or {}).get("name", "damage"),
                "ailment": ((meta.get("ailment") or {}).get("name")
                            if (meta.get("ailment") or {}).get("name") != "none" else None),
                "ailment_chance": meta.get("ailment_chance") or 0,
                "stat_changes": [{"stat": sc["stat"]["name"].replace("-", "_"),
                                  "change": sc["change"]}
                                 for sc in mv.get("stat_changes", [])],
                "stat_chance": meta.get("stat_chance") or 0,
                "flinch_chance": meta.get("flinch_chance") or 0,
                "drain": meta.get("drain") or 0,
                "healing": meta.get("healing") or 0,
                "min_hits": meta.get("min_hits"),
                "max_hits": meta.get("max_hits"),
            },
        }
        _write(os.path.join(out, "moves", f"{mv['name']}.json"), move)
        n_moves += 1
        if delay:
            time.sleep(delay)
    log(f"  {n_moves} moves written")

    # species
    n_species = 0
    for dex in range(1, MAX_DEX + 1):
        pk = _rest(f"pokemon/{dex}", cache)
        sp = _rest(f"pokemon-species/{dex}", cache)
        learn: dict[str, list] = {"level_up": [], "egg": [], "tutor": [], "machine": []}
        rows = []
        for mv in pk["moves"]:
            for vgd in mv["version_group_details"]:
                vg = vgd["version_group"]["name"]
                if vg in ("black-2-white-2", "black-white"):
                    rows.append((vg, vgd["move_learn_method"]["name"],
                                 vgd["level_learned_at"], mv["move"]["name"]))
        use_vg = ("black-2-white-2"
                  if any(r[0] == "black-2-white-2" for r in rows) else "black-white")
        for vg, method, level, name in sorted(rows, key=lambda r: (r[2], r[3])):
            if vg != use_vg:
                continue
            key = {"level-up": "level_up", "egg": "egg",
                   "tutor": "tutor", "machine": "machine"}.get(method)
            if key is None:
                continue
            if key == "level_up":
                learn[key].append({"move": name, "level": level})
            elif name not in learn[key]:
                learn[key].append(name)
        species = {
            "id": pk["name"],
            "name": next((n["name"] for n in sp["names"]
                          if n["language"]["name"] == "en"), pk["name"].title()),
            "dex": dex,
            "types": [t["type"]["name"] for t in sorted(pk["types"],
                                                        key=lambda t: t["slot"])],
            "base_stats": {s["stat"]["name"].replace("-", "_"): s["base_stat"]
                           for s in pk["stats"]},
            "abilities": [a["ability"]["name"] for a in sorted(
                pk["abilities"], key=lambda a: (a["is_hidden"], a["slot"]))],
            "base_experience": pk.get("base_experience") or 0,
            "growth_rate": sp["growth_rate"]["name"],
            "catch_rate": sp["capture_rate"],
            "gender_rate": sp["gender_rate"],
            "learnset": learn,
        }
        _write(os.path.join(out, "species", f"{dex:03d}-{pk['name']}.json"), species)
        n_species += 1
        if dex % 50 == 0:
            log(f"  ...{dex}/{MAX_DEX} species")
        if delay:
            time.sleep(delay)
    log(f"  {n_species} species written")


def fetch_sprites(out: str, cache: str, *, log=print) -> None:
    sprite_dir = os.path.join(out, "..", "sprites")
    log("Downloading Gen 5 (B/W) sprites for personal use...")
    ok = 0
    for dex in range(1, MAX_DEX + 1):
        for sub, name in (("", f"{dex}.png"), ("/back", f"{dex}.png")):
            url = f"{SPRITE_BASE}{sub}/{name}"
            dst = os.path.join(sprite_dir, "back" if sub else "front", f"{dex}.png")
            try:
                data = _fetch(url, cache, binary=True)
            except Exception:
                continue
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, "wb") as f:
                f.write(data)
            ok += 1
    log(f"  {ok} sprites saved to {os.path.abspath(sprite_dir)}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="game/data")
    ap.add_argument("--source", choices=("rest", "csv"), default="rest")
    ap.add_argument("--cache", default=".pokeapi_cache")
    ap.add_argument("--delay", type=float, default=0.0,
                    help="seconds between REST requests (be polite)")
    ap.add_argument("--sprites", action="store_true",
                    help="also download B/W sprites (personal use only)")
    args = ap.parse_args(argv)
    try:
        if args.source == "csv":
            build_from_csv(args.out, args.cache)
        else:
            build_from_rest(args.out, args.cache, delay=args.delay)
        if args.sprites:
            fetch_sprites(args.out, args.cache)
    except KeyboardInterrupt:
        print("\nInterrupted; cached progress is kept. Re-run to resume.",
              file=sys.stderr)
        return 130
    print(f"Done. Game data in {os.path.abspath(args.out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
