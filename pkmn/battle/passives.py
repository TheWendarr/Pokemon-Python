"""Passive effects: abilities and held items.

Pure hook functions consumed by damage.py, moves.py, and engine.py.
Adding an ability or item usually means touching only this file.
"""
from __future__ import annotations

from .events import E, Event

CHOICE_ITEMS = ("choice-band", "choice-specs", "choice-scarf")
PINCH_ABILITIES = {"blaze": "fire", "torrent": "water",
                   "overgrow": "grass", "swarm": "bug"}
STATUS_BLOCK = {"limber": "paralysis", "immunity": "poison",
                "insomnia": "sleep", "vital-spirit": "sleep",
                "water-veil": "burn", "magma-armor": "freeze"}
CONTACT_STATUS = {"static": "paralysis", "poison-point": "poison",
                  "flame-body": "burn"}
WEATHER_SETTERS = {"drizzle": "rain", "drought": "sun",
                   "sand-stream": "sandstorm", "snow-warning": "hail"}
WEATHER_SPEED = {"swift-swim": "rain", "chlorophyll": "sun",
                 "sand-rush": "sandstorm"}
SAND_IMMUNE_ABILITIES = ("sand-rush", "sand-veil", "sand-force")

# Every ability id the battle hooks below act on. The audit CLI compares
# this against the full abilities.json catalog; anything not listed is
# inert in battle (data-only) until a hook is added.
IMPLEMENTED_ABILITIES = frozenset({
    "huge-power", "pure-power", "guts", "technician", "blaze", "torrent",
    "overgrow", "swarm", "thick-fat", "super-luck", "limber", "immunity",
    "insomnia", "vital-spirit", "water-veil", "magma-armor", "own-tempo",
    "levitate", "volt-absorb", "water-absorb", "shield-dust",
    "serene-grace", "sturdy", "rough-skin", "iron-barbs", "static",
    "poison-point", "flame-body", "intimidate", "drizzle", "drought",
    "sand-stream", "snow-warning", "swift-swim", "chlorophyll",
    "sand-rush", "sand-veil", "sand-force", "natural-cure", "speed-boost",
})

# Held items with battle behavior in this module / deal_damage.
IMPLEMENTED_HELD = frozenset({
    "choice-band", "choice-specs", "choice-scarf", "leftovers",
    "oran-berry", "sitrus-berry", "lum-berry", "life-orb", "focus-sash",
    "scope-lens", "razor-claw",
})


def abil(bp) -> str:
    v = getattr(bp, "vol", None)
    if v is not None:
        if v.ability_suppressed:
            return ""
        if v.ability_override:
            return v.ability_override
    return (bp.state.ability or "").lower()


def held(bp) -> str:
    v = getattr(bp, "vol", None)
    if v is not None and v.embargo_turns > 0:
        return ""
    return bp.state.held_item or ""


# ── damage-formula hooks ─────────────────────────────────────────────

def attack_stat_mod(attacker, move) -> float:
    m, a = 1.0, abil(attacker)
    if move.category == "physical":
        if a in ("huge-power", "pure-power"):
            m *= 2.0
        if a == "guts" and attacker.status:
            m *= 1.5
        if held(attacker) == "choice-band":
            m *= 1.5
    else:
        if held(attacker) == "choice-specs":
            m *= 1.5
    return m


def power_mod(attacker, defender, move, weather) -> float:
    m, a = 1.0, abil(attacker)
    if a == "technician" and (move.power or 0) <= 60:
        m *= 1.5
    if a in PINCH_ABILITIES and move.type == PINCH_ABILITIES[a] \
            and attacker.current_hp * 3 <= attacker.max_hp:
        m *= 1.5
    if abil(defender) == "thick-fat" and move.type in ("fire", "ice"):
        m *= 0.5
    if weather == "sun":
        if move.type == "fire":
            m *= 1.5
        elif move.type == "water":
            m *= 0.5
    elif weather == "rain":
        if move.type == "water":
            m *= 1.5
        elif move.type == "fire":
            m *= 0.5
    if move.id == "solar-beam" and weather in ("rain", "sandstorm", "hail"):
        m *= 0.5
    return m


def spdef_mod(defender, move, weather) -> float:
    if weather == "sandstorm" and move.category == "special" \
            and "rock" in defender.types:
        return 1.5
    return 1.0


def final_mod(attacker, crit: bool, screened: bool) -> float:
    m = 1.0
    if screened and not crit:
        m *= 0.5
    if held(attacker) == "life-orb":
        m *= 1.3
    return m


def burn_ignored(attacker) -> bool:
    return abil(attacker) == "guts"


def speed_mod(bp, weather) -> float:
    m = 1.0
    if held(bp) == "choice-scarf":
        m *= 1.5
    if weather and WEATHER_SPEED.get(abil(bp)) == weather:
        m *= 2.0
    return m


def crit_bonus(bp) -> int:
    b = bp.vol.crit_bonus
    if abil(bp) == "super-luck":
        b += 1
    if held(bp) in ("scope-lens", "razor-claw"):
        b += 1
    return b


# ── status / immunity hooks ──────────────────────────────────────────

def status_blocked(bp, status: str) -> bool:
    base = "poison" if status == "toxic" else status
    return STATUS_BLOCK.get(abil(bp)) == base


def confusion_blocked(bp) -> bool:
    return abil(bp) == "own-tempo"


def immunity_or_absorb(defender, move):
    """'immune' | 'absorb' | None, for ability-based type interactions."""
    a = abil(defender)
    if a == "levitate" and move.type == "ground":
        return "immune"
    if a == "volt-absorb" and move.type == "electric":
        return "absorb"
    if a == "water-absorb" and move.type == "water":
        return "absorb"
    return None


def secondary_mult(attacker, defender_is_target: bool, defender) -> float:
    """Multiplier on secondary-effect chances (Serene Grace doubles;
    Shield Dust on the target blocks)."""
    if defender_is_target and abil(defender) == "shield-dust":
        return 0.0
    return 2.0 if abil(attacker) == "serene-grace" else 1.0


def survives_lethal(bp):
    """('ability'|'item', name) if a full-HP survival effect applies."""
    if bp.current_hp == bp.max_hp:
        if abil(bp) == "sturdy":
            return ("ability", "sturdy")
        if held(bp) == "focus-sash":
            return ("item", "focus-sash")
    return None


def sand_immune(bp) -> bool:
    return (any(t in ("rock", "ground", "steel") for t in bp.types)
            or abil(bp) in SAND_IMMUNE_ABILITIES)


# ── event-driven hooks ───────────────────────────────────────────────

def on_contact(eng, attacker, defender, events) -> None:
    """Defender's contact abilities punish the attacker."""
    a = abil(defender)
    if a in ("rough-skin", "iron-barbs") and not attacker.fainted:
        dmg = max(1, attacker.max_hp // 8)
        attacker.take_damage(dmg)
        events.append(Event(E.ABILITY, eng.side_of(defender),
                            {"ability": a, "pokemon": defender.name}))
        events.append(Event(E.DAMAGE, eng.side_of(attacker),
                            {"pokemon": attacker.name, "amount": dmg,
                             "remaining_hp": attacker.current_hp,
                             "max_hp": attacker.max_hp,
                             "crit": False, "effectiveness": 1.0}))
        eng.announce_faint(attacker, events)
    if a in CONTACT_STATUS and not attacker.fainted \
            and eng.rng.randint(1, 100) <= 30:
        from .moves import apply_status
        if apply_status(eng, attacker, CONTACT_STATUS[a], events):
            events.insert(-1, Event(E.ABILITY, eng.side_of(defender),
                                    {"ability": a, "pokemon": defender.name}))


def switch_in(eng, side: str, bp, events) -> None:
    a = abil(bp)
    if a == "intimidate":
        foe = eng.active("p2" if side == "p1" else "p1")
        if not foe.fainted:
            events.append(Event(E.ABILITY, side,
                                {"ability": "intimidate", "pokemon": bp.name}))
            applied = foe.modify_stage("attack", -1)
            if applied:
                events.append(Event(E.STAT_CHANGE, eng.side_of(foe),
                                    {"pokemon": foe.name, "stat": "attack",
                                     "change": applied,
                                     "stage": foe.stages["attack"]}))
            else:
                events.append(Event(E.STAT_CHANGE_FAILED, eng.side_of(foe),
                                    {"pokemon": foe.name, "stat": "attack",
                                     "direction": "lower"}))
    w = WEATHER_SETTERS.get(a)
    if w and eng.weather != w:
        events.append(Event(E.ABILITY, side, {"ability": a, "pokemon": bp.name}))
        eng.set_weather(w, -1, events)


def on_switch_out(bp, events, side) -> None:
    if abil(bp) == "natural-cure" and bp.status:
        cured = bp.status
        bp.status = None
        events.append(Event(E.STATUS_CURED, side,
                            {"pokemon": bp.name, "status": cured,
                             "ability": "natural-cure"}))


def check_hp_berry(eng, bp, events) -> None:
    it = held(bp)
    if bp.fainted or it not in ("oran-berry", "sitrus-berry"):
        return
    if bp.current_hp * 2 <= bp.max_hp:
        bp.state.held_item = None
        amount = 10 if it == "oran-berry" else max(1, bp.max_hp // 4)
        healed = bp.heal(amount)
        events.append(Event(E.ITEM_HELD, eng.side_of(bp),
                            {"item": it, "pokemon": bp.name}))
        events.append(Event(E.HEAL, eng.side_of(bp),
                            {"pokemon": bp.name, "amount": healed,
                             "remaining_hp": bp.current_hp}))


def check_lum(eng, bp, events) -> None:
    if held(bp) != "lum-berry" or bp.fainted:
        return
    if bp.status or bp.vol.confusion_turns > 0:
        cured = bp.status or "confusion"
        bp.status = None
        bp.vol.confusion_turns = 0
        bp.vol.toxic_counter = 0
        bp.state.held_item = None
        events.append(Event(E.ITEM_HELD, eng.side_of(bp),
                            {"item": "lum-berry", "pokemon": bp.name}))
        events.append(Event(E.STATUS_CURED, eng.side_of(bp),
                            {"pokemon": bp.name, "status": cured}))


def end_of_turn(eng, side: str, bp, events) -> None:
    if bp.fainted:
        return
    if held(bp) == "leftovers" and bp.current_hp < bp.max_hp:
        healed = bp.heal(max(1, bp.max_hp // 16))
        events.append(Event(E.ITEM_HELD, side, {"item": "leftovers",
                                                "pokemon": bp.name}))
        events.append(Event(E.HEAL, side, {"pokemon": bp.name, "amount": healed,
                                           "remaining_hp": bp.current_hp}))
    check_hp_berry(eng, bp, events)
    if abil(bp) == "speed-boost":
        applied = bp.modify_stage("speed", 1)
        if applied:
            events.append(Event(E.ABILITY, side, {"ability": "speed-boost",
                                                  "pokemon": bp.name}))
            events.append(Event(E.STAT_CHANGE, side,
                                {"pokemon": bp.name, "stat": "speed",
                                 "change": applied,
                                 "stage": bp.stages["speed"]}))
