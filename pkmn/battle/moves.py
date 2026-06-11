"""Move execution.

Two layers:

1. A data-driven interpreter that executes any move from its MoveEffect
   metadata (damage, multi-hit, drain/recoil, ailments, stat changes,
   flinch, healing, fixed damage, OHKO). This covers the large majority
   of Gen 4/5 moves with zero per-move code.
2. A handler registry (`@handler("rest")`) for moves whose behavior
   can't be expressed in metadata. Phase 2 grows this registry (two-turn
   moves, counters, field effects...). Unknown effect kinds emit an
   EFFECT_SKIPPED event instead of silently misbehaving, so coverage
   gaps are visible in logs and tests.
"""
from __future__ import annotations

from ..data.models import MoveData, MoveEffect, STATUS
from .damage import accuracy_check, calc_damage
from .events import E, Event
from .state import BattlePokemon, other

# ── Built-in pseudo-moves ────────────────────────────────────────────

STRUGGLE = MoveData(id="struggle", name="Struggle", type="typeless",
                    category="physical", power=50, accuracy=None, pp=1,
                    effect=MoveEffect(kind="damage"))

CONFUSION_HIT = MoveData(id="confusion-self-hit", name="confusion", type="typeless",
                         category="physical", power=40, accuracy=None, pp=1)

# ── Tables ───────────────────────────────────────────────────────────

FIXED_DAMAGE = {"sonic-boom": 20, "dragon-rage": 40}
LEVEL_DAMAGE = {"seismic-toss", "night-shade"}
TOXIC_MOVES = {"toxic", "poison-fang"}  # ailment 'poison' upgraded to badly poisoned

# Gen 2-5 status immunities by defender type.
STATUS_TYPE_IMMUNITY = {
    "burn": {"fire"},
    "poison": {"poison", "steel"},
    "toxic": {"poison", "steel"},
    "freeze": {"ice"},
    "paralysis": set(),  # Electric immunity is Gen 6+
    "sleep": set(),
}

VOLATILE_AILMENTS = {"confusion"}
NONVOLATILE_AILMENTS = {"paralysis", "sleep", "freeze", "burn", "poison"}

# Gen 5 multi-hit distribution for 2-5 hit moves.
MULTI_HIT_WEIGHTS = ((2, 2), (3, 2), (4, 1), (5, 1))

HANDLERS: dict = {}


def handler(move_id: str):
    def deco(fn):
        HANDLERS[move_id] = fn
        return fn
    return deco


# ── Status application ───────────────────────────────────────────────

def apply_status(eng, target: BattlePokemon, status: str, events, *,
                 source_side: str | None = None, turns: int | None = None) -> bool:
    """Apply a non-volatile status with Gen 5 rules. Returns success."""
    if target.fainted:
        return False
    if target.status is not None:
        return False
    immune_types = STATUS_TYPE_IMMUNITY.get(status, set())
    if any(t in immune_types for t in target.types):
        return False
    target.status = status
    if status == "toxic":
        target.vol.toxic_counter = 0
    if status == "sleep":
        target.vol.sleep_turns = turns if turns is not None else eng.rng.randint(1, 3)
    events.append(Event(E.STATUS_APPLIED, eng.side_of(target),
                        {"status": status, "pokemon": target.name}))
    return True


def apply_ailment(eng, user: BattlePokemon, target: BattlePokemon,
                  move: MoveData, events) -> None:
    ailment = move.effect.ailment
    if not ailment or ailment == "none":
        return
    if ailment == "confusion":
        if target.vol.confusion_turns <= 0 and not target.fainted:
            target.vol.confusion_turns = eng.rng.randint(2, 5)
            events.append(Event(E.CONFUSED, eng.side_of(target),
                                {"pokemon": target.name, "start": True}))
        return
    if ailment in NONVOLATILE_AILMENTS:
        status = "toxic" if (ailment == "poison" and move.id in TOXIC_MOVES) else ailment
        ok = apply_status(eng, target, status, events)
        if not ok and move.category == STATUS:
            events.append(Event(E.MOVE_FAILED, eng.side_of(user), {"move": move.name}))
        return
    # trap / leech-seed / infatuation / etc. -- Phase 2
    events.append(Event(E.EFFECT_SKIPPED, eng.side_of(user),
                        {"move": move.id, "effect": ailment}))


def apply_stat_changes(eng, user, target, move: MoveData, events) -> None:
    eff = move.effect
    if not eff.stat_changes:
        return
    chance = eff.stat_chance or 100
    if eng.rng.randint(1, 100) > chance:
        return
    # PokeAPI convention: for damaging moves, 'damage+raise' stat changes
    # apply to the USER (incl. Superpower/Overheat's self-drops), while
    # 'damage+lower' applies to the TARGET. Status moves follow move.target.
    kind = eff.kind.replace("+", "-")
    if move.is_damaging:
        recipient = user if kind == "damage-raise" else target
    else:
        recipient = user if move.targets_user else target
    for sc in eff.stat_changes:
        if recipient.fainted:
            continue
        applied = recipient.modify_stage(sc.stat, sc.change)
        side = eng.side_of(recipient)
        if applied == 0:
            events.append(Event(E.STAT_CHANGE_FAILED, side,
                                {"pokemon": recipient.name, "stat": sc.stat,
                                 "direction": "raise" if sc.change > 0 else "lower"}))
        else:
            events.append(Event(E.STAT_CHANGE, side,
                                {"pokemon": recipient.name, "stat": sc.stat,
                                 "change": applied,
                                 "stage": recipient.stages[sc.stat]}))


# ── Damage application helpers ───────────────────────────────────────

def deal_damage(eng, target: BattlePokemon, amount: int, events,
                detail: dict | None = None) -> int:
    dealt = target.take_damage(amount)
    ev = {"pokemon": target.name, "amount": dealt,
          "remaining_hp": target.current_hp, "max_hp": target.max_hp}
    if detail:
        ev.update({"crit": detail.get("crit", False),
                   "effectiveness": detail.get("effectiveness", 1.0)})
    events.append(Event(E.DAMAGE, eng.side_of(target), ev))
    eng.announce_faint(target, events)
    return dealt


def roll_hits(eng, eff: MoveEffect) -> int:
    if not eff.min_hits:
        return 1
    if eff.min_hits == eff.max_hits:
        return eff.min_hits
    if (eff.min_hits, eff.max_hits) == (2, 5):
        pool = [n for n, w in MULTI_HIT_WEIGHTS for _ in range(w)]
        return eng.rng.choice(pool)
    return eng.rng.randint(eff.min_hits, eff.max_hits)


# ── Main entry ───────────────────────────────────────────────────────

def execute_move(eng, side: str, move: MoveData, events) -> None:
    """Execute `move` by the active Pokemon on `side`. Incapacity checks
    (sleep/para/etc.) and PP accounting happen in the engine before this."""
    user = eng.active(side)
    target = eng.active(other(side))

    events.append(Event(E.MOVE_USED, side, {"pokemon": user.name, "move": move.name}))

    if move.id in HANDLERS:
        HANDLERS[move.id](eng, user, target, move, events)
        return

    kind = move.effect.kind

    # ── OHKO moves ──
    if kind == "ohko":
        if eng.data.effectiveness(move.type, target.types) == 0:
            events.append(Event(E.MOVE_IMMUNE, eng.side_of(target), {"pokemon": target.name}))
            return
        if target.level > user.level:
            events.append(Event(E.MOVE_FAILED, side, {"move": move.name}))
            return
        acc = (move.accuracy or 30) + (user.level - target.level)
        if eng.rng.randint(1, 100) > acc:
            events.append(Event(E.MOVE_MISSED, side, {"move": move.name}))
            return
        deal_damage(eng, target, target.current_hp, events,
                    {"effectiveness": 1.0, "crit": False})
        return

    # ── Damaging moves ──
    if move.is_damaging:
        eff_mult = (1.0 if move.type == "typeless"
                    else eng.data.effectiveness(move.type, target.types))
        if eff_mult == 0:
            events.append(Event(E.MOVE_IMMUNE, eng.side_of(target), {"pokemon": target.name}))
            return
        if not accuracy_check(move, user, target, rng=eng.rng):
            events.append(Event(E.MOVE_MISSED, side, {"move": move.name}))
            return

        # Fixed / level-based damage
        if move.id in FIXED_DAMAGE:
            deal_damage(eng, target, FIXED_DAMAGE[move.id], events,
                        {"effectiveness": 1.0, "crit": False})
            total = FIXED_DAMAGE[move.id]
        elif move.id in LEVEL_DAMAGE:
            deal_damage(eng, target, user.level, events,
                        {"effectiveness": 1.0, "crit": False})
            total = user.level
        else:
            hits = roll_hits(eng, move.effect)
            total = 0
            landed = 0
            for _ in range(hits):
                if target.fainted or user.fainted:
                    break
                crit = eng.rng.random() < eng.crit_chance_for(user, move)
                dmg, detail = calc_damage(eng.data, user, target, move,
                                          rng=eng.rng, crit=crit)
                total += deal_damage(eng, target, dmg, events, detail)
                landed += 1
            if hits > 1:
                events.append(Event(E.MULTI_HIT, side, {"hits": landed}))

        # Thaw a frozen target hit by a fire move
        if target.status == "freeze" and move.type == "fire" and not target.fainted:
            target.status = None
            events.append(Event(E.THAWED, eng.side_of(target), {"pokemon": target.name}))

        # Drain / recoil
        drain = move.effect.drain
        if drain > 0 and total > 0 and not user.fainted:
            healed = user.heal(max(1, total * drain // 100))
            if healed:
                events.append(Event(E.DRAIN, side, {"pokemon": user.name, "amount": healed}))
        elif drain < 0 and total > 0 and not user.fainted:
            rec = max(1, total * (-drain) // 100)
            user.take_damage(rec)
            events.append(Event(E.RECOIL, side, {"pokemon": user.name, "amount": rec,
                                                 "remaining_hp": user.current_hp}))
            eng.announce_faint(user, events)

        # Secondary effects only land if the target is still standing
        if not target.fainted:
            ail_chance = move.effect.ailment_chance or (100 if move.effect.ailment else 0)
            if move.effect.ailment and eng.rng.randint(1, 100) <= ail_chance:
                apply_ailment(eng, user, target, move, events)
            if move.effect.flinch_chance and not target.vol.has_moved:
                if eng.rng.randint(1, 100) <= move.effect.flinch_chance:
                    target.vol.flinched = True
        apply_stat_changes(eng, user, target, move, events)

        # Struggle recoil: quarter of user's max HP (Gen 5)
        if move.id == "struggle" and not user.fainted:
            rec = max(1, user.max_hp // 4)
            user.take_damage(rec)
            events.append(Event(E.RECOIL, side, {"pokemon": user.name, "amount": rec,
                                                 "remaining_hp": user.current_hp}))
            eng.announce_faint(user, events)
        return

    # ── Status moves ──
    # Thunder Wave-style type immunity: a pure-ailment status move whose
    # type the target is immune to fails (Gen 5 behavior).
    if move.effect.ailment and move.effect.ailment in NONVOLATILE_AILMENTS:
        if eng.data.effectiveness(move.type, target.types) == 0:
            events.append(Event(E.MOVE_IMMUNE, eng.side_of(target), {"pokemon": target.name}))
            return
    if not move.targets_user and not accuracy_check(move, user, target, rng=eng.rng):
        events.append(Event(E.MOVE_MISSED, side, {"move": move.name}))
        return

    did_something = False
    if move.effect.ailment:
        apply_ailment(eng, user, target, move, events)
        did_something = True
    if move.effect.stat_changes:
        apply_stat_changes(eng, user, target, move, events)
        did_something = True
    if move.effect.healing:
        recipient = user if move.targets_user else target
        healed = recipient.heal(max(1, recipient.max_hp * move.effect.healing // 100))
        if healed:
            events.append(Event(E.HEAL, eng.side_of(recipient),
                                {"pokemon": recipient.name, "amount": healed,
                                 "remaining_hp": recipient.current_hp}))
        else:
            events.append(Event(E.MOVE_FAILED, side, {"move": move.name}))
        did_something = True
    if not did_something:
        events.append(Event(E.EFFECT_SKIPPED, side,
                            {"move": move.id, "effect": move.effect.kind}))


# ── Special-case handlers (the extension point for Phase 2) ──────────

@handler("rest")
def _rest(eng, user, target, move, events):
    if user.current_hp == user.max_hp or user.status == "sleep":
        events.append(Event(E.MOVE_FAILED, eng.side_of(user), {"move": move.name}))
        return
    user.status = None
    user.vol.toxic_counter = 0
    healed = user.heal(user.max_hp)
    user.status = "sleep"
    user.vol.sleep_turns = 2
    events.append(Event(E.HEAL, eng.side_of(user),
                        {"pokemon": user.name, "amount": healed,
                         "remaining_hp": user.current_hp}))
    events.append(Event(E.STATUS_APPLIED, eng.side_of(user),
                        {"status": "sleep", "pokemon": user.name, "rest": True}))
