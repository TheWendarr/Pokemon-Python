"""Structured battle mechanics overlaid on the full PokeAPI item catalog.

PokeAPI stores item *effects* as prose, so anything the engine must act
on numerically lives here, keyed by item identifier. Everything else in
the catalog still ships in items.json as data (name, category, pocket,
flags, effect text) and is simply inert in battle until given an entry
here or in pkmn/battle/passives.py.

Conditional ball multipliers (Quick, Dusk, Net...) are simplified to
flat Gen-5-plausible constants; see docs/ARCHITECTURE.md.
"""
from __future__ import annotations

# bag medicine: heal (int HP, "full"), cures (status list), revive (frac)
MEDICINE = {
    "potion": {"heal": 20}, "super-potion": {"heal": 50},
    "hyper-potion": {"heal": 200}, "max-potion": {"heal": "full"},
    "full-restore": {"heal": "full", "cures": ["all"]},
    "fresh-water": {"heal": 50}, "soda-pop": {"heal": 60},
    "lemonade": {"heal": 80}, "moomoo-milk": {"heal": 100},
    "berry-juice": {"heal": 20},
    "energy-powder": {"heal": 50}, "energy-root": {"heal": 200},
    "heal-powder": {"cures": ["all"]},
    "antidote": {"cures": ["poison", "toxic"]},
    "burn-heal": {"cures": ["burn"]}, "ice-heal": {"cures": ["freeze"]},
    "awakening": {"cures": ["sleep"]},
    "paralyze-heal": {"cures": ["paralysis"]},
    "full-heal": {"cures": ["all"]}, "lava-cookie": {"cures": ["all"]},
    "old-gateau": {"cures": ["all"]}, "casteliacone": {"cures": ["all"]},
    "revive": {"revive": 0.5}, "max-revive": {"revive": 1.0},
    "revival-herb": {"revive": 1.0}, "sacred-ash": {"revive": 1.0},
    # bag-usable berries (held behavior lives in passives.py)
    "cheri-berry": {"cures": ["paralysis"]}, "chesto-berry": {"cures": ["sleep"]},
    "pecha-berry": {"cures": ["poison", "toxic"]},
    "rawst-berry": {"cures": ["burn"]}, "aspear-berry": {"cures": ["freeze"]},
    "lum-berry": {"cures": ["all"]}, "oran-berry": {"heal": 10},
}

# in-battle boosters: stat stages / crit stage / Guard Spec (Mist)
BOOSTERS = {
    "x-attack": {"stages": {"attack": 1}},
    "x-defense": {"stages": {"defense": 1}},
    "x-defend": {"stages": {"defense": 1}},        # older identifier
    "x-sp-atk": {"stages": {"special_attack": 1}},
    "x-special": {"stages": {"special_attack": 1}},
    "x-sp-def": {"stages": {"special_defense": 1}},
    "x-speed": {"stages": {"speed": 1}},
    "x-accuracy": {"stages": {"accuracy": 1}},
    "dire-hit": {"crit": 2},
    "guard-spec": {"guard": True},
}

# flat Gen 5 ball multipliers (conditionals simplified to constants)
BALL_RATES = {
    "poke-ball": 1.0, "great-ball": 1.5, "ultra-ball": 2.0,
    "master-ball": 255.0, "safari-ball": 1.5, "sport-ball": 1.5,
    "premier-ball": 1.0, "luxury-ball": 1.0, "heal-ball": 1.0,
    "friend-ball": 1.0, "level-ball": 2.0, "lure-ball": 3.0,
    "moon-ball": 3.0, "love-ball": 4.0, "fast-ball": 4.0,
    "heavy-ball": 1.5, "net-ball": 3.0, "nest-ball": 2.0,
    "repeat-ball": 3.0, "timer-ball": 3.0, "quick-ball": 5.0,
    "dusk-ball": 3.5, "dive-ball": 3.5, "cherish-ball": 1.0,
    "park-ball": 255.0, "dream-ball": 255.0,
}


def mechanics_for(item_id: str) -> dict:
    out: dict = {}
    out.update(MEDICINE.get(item_id, {}))
    out.update(BOOSTERS.get(item_id, {}))
    if item_id in BALL_RATES:
        out["ball_rate"] = BALL_RATES[item_id]
    return out


# ── REST normalizers (pure; unit-tested with sample payloads) ────────

GEN_NAMES = {"generation-i": 1, "generation-ii": 2, "generation-iii": 3,
             "generation-iv": 4, "generation-v": 5, "generation-vi": 6,
             "generation-vii": 7, "generation-viii": 8, "generation-ix": 9}


def _english_short_effect(entries: list) -> str:
    for e in entries or []:
        if e.get("language", {}).get("name") == "en":
            return (e.get("short_effect") or e.get("effect") or "").strip()
    return ""


def ability_record_from_rest(d: dict) -> tuple[str, dict] | None:
    """REST /ability/{id} payload -> (identifier, record) or None."""
    gen = GEN_NAMES.get(d.get("generation", {}).get("name", ""), 99)
    if gen > 5 or not d.get("is_main_series", True):
        return None
    return d["name"], {
        "name": d["name"].replace("-", " ").title(),
        "generation": gen,
        "short_effect": _english_short_effect(d.get("effect_entries")),
    }


def item_record_from_rest(d: dict, pocket: str) -> tuple[str, dict] | None:
    """REST /item/{id} payload -> (identifier, record) or None.
    Caller resolves the pocket from the item's category."""
    gens = {GEN_NAMES.get(g.get("generation", {}).get("name", ""), 99)
            for g in d.get("game_indices", [])}
    if gens and min(gens) > 5:
        return None
    attrs = {a["name"] for a in d.get("attributes", [])}
    ident = d["name"]
    rec = {
        "name": ident.replace("-", " ").title(),
        "category": d.get("category", {}).get("name", "unknown"),
        "pocket": pocket,
        "cost": d.get("cost", 0),
        "fling_power": d.get("fling_power") or 0,
        "holdable": bool(attrs & {"holdable", "holdable-passive",
                                  "holdable-active"}),
        "battle_usable": "usable-in-battle" in attrs,
        "short_effect": _english_short_effect(d.get("effect_entries")),
    }
    rec.update(mechanics_for(ident))
    return ident, rec
