"""Move execution.

Two layers:

1. A data-driven interpreter that executes any move from its MoveEffect
   metadata (damage, multi-hit, drain/recoil, ailments, stat changes,
   flinch, healing, fixed damage, OHKO, traps, force-switch).
2. A handler registry (`@handler("rest")`) for moves whose behavior
   can't be expressed in metadata: Protect, weather moves, screens,
   hazards, Explosion, Rapid Spin... Unknown effect kinds emit an
   EFFECT_SKIPPED event instead of silently misbehaving.
"""
from __future__ import annotations

from ..data.models import MoveData, MoveEffect, STATUS
from . import passives
from .damage import accuracy_check, calc_damage
from .events import E, Event
from .passives import SOUND_MOVES, POWDER_MOVES
from .state import BattlePokemon, other

# ── Built-in pseudo-moves ────────────────────────────────────────────

STRUGGLE = MoveData(id="struggle", name="Struggle", type="typeless",
                    category="physical", power=50, accuracy=None, pp=1,
                    effect=MoveEffect(kind="damage"))

CONFUSION_HIT = MoveData(id="confusion-self-hit", name="confusion", type="typeless",
                         category="physical", power=40, accuracy=None, pp=1)

RECHARGE_PSEUDO = MoveData(id="recharge", name="Recharge", type="typeless",
                           category="status", power=None, accuracy=None, pp=1)

# ── Tables ───────────────────────────────────────────────────────────

FIXED_DAMAGE = {"sonic-boom": 20, "dragon-rage": 40}
LEVEL_DAMAGE = {"seismic-toss", "night-shade"}
TOXIC_MOVES = {"toxic", "poison-fang"}

# Two-turn moves: value is the semi-invulnerable state (or None = charge
# in place). Solar Beam skips its charge turn in sun.
CHARGE_MOVES = {"fly": "fly", "bounce": "bounce", "dig": "dig", "dive": "dive",
                "solar-beam": None, "razor-wind": None, "sky-attack": None,
                "skull-bash": None}
# Moves that can hit a semi-invulnerable target: power multiplier applied.
SEMI_HIT = {
    "fly": {"gust": 2.0, "twister": 2.0, "thunder": 1.0, "hurricane": 1.0,
            "sky-uppercut": 1.0},
    "bounce": {"gust": 2.0, "twister": 2.0, "thunder": 1.0, "hurricane": 1.0,
               "sky-uppercut": 1.0},
    "dig": {"earthquake": 2.0, "magnitude": 2.0},
    "dive": {"surf": 2.0, "whirlpool": 2.0},
}
RECHARGE_MOVES = {"hyper-beam", "giga-impact", "blast-burn", "frenzy-plant",
                  "hydro-cannon", "rock-wrecker", "roar-of-time"}
RAMPAGE_MOVES = {"thrash", "outrage", "petal-dance"}

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

MULTI_HIT_WEIGHTS = ((2, 2), (3, 2), (4, 1), (5, 1))

HANDLERS: dict = {}


def handler(move_id: str):
    def deco(fn):
        HANDLERS[move_id] = fn
        return fn
    return deco


# ── Status application ───────────────────────────────────────────────

def _hits(eng, user, target, move) -> bool:
    """Accuracy gate with Lock-On / Telekinesis sure-hit handling."""
    if user.vol.lock_on:
        user.vol.lock_on = False
        return True
    if target.vol.telekinesis_turns > 0:
        return True
    return accuracy_check(move, user, target, rng=eng.rng, weather=eng.weather)


def apply_status(eng, target: BattlePokemon, status: str, events, *,
                 turns: int | None = None, from_attacker: BattlePokemon | None = None) -> bool:
    """Apply a non-volatile status with Gen 5 rules. Returns success."""
    if target.fainted or target.status is not None:
        return False
    immune_types = STATUS_TYPE_IMMUNITY.get(status, set())
    if any(t in immune_types for t in target.types):
        return False
    if passives.status_blocked(target, status):
        return False
    # Leaf Guard: immune to all status in sun
    if passives.abil(target) == "leaf-guard" and eng.weather == "sun":
        return False
    target.status = status
    if status == "toxic":
        target.vol.toxic_counter = 0
    if status == "sleep":
        if turns is not None:
            rolled = turns
        else:
            rolled = eng.rng.randint(1, 3)
            if passives.abil(target) == "early-bird":
                rolled = max(1, rolled // 2)
        target.vol.sleep_turns = rolled
    events.append(Event(E.STATUS_APPLIED, eng.side_of(target),
                        {"status": status, "pokemon": target.name}))
    passives.check_lum(eng, target, events)
    passives.check_status_berry(eng, target, events)
    # Synchronize: mirror status back to attacker
    if from_attacker is not None and not from_attacker.fainted \
            and passives.abil(target) == "synchronize" \
            and status in ("burn", "poison", "toxic", "paralysis"):
        mirror = "poison" if status == "toxic" else status
        if not from_attacker.status:
            from_attacker.status = mirror
            events.append(Event(E.ABILITY, eng.side_of(target),
                                {"ability": "synchronize", "pokemon": target.name}))
            events.append(Event(E.STATUS_APPLIED, eng.side_of(from_attacker),
                                {"status": mirror, "pokemon": from_attacker.name}))
    return True


def apply_ailment(eng, user: BattlePokemon, target: BattlePokemon,
                  move: MoveData, events) -> None:
    ailment = move.effect.ailment
    if not ailment or ailment == "none":
        return
    if target is not user and ailment in NONVOLATILE_AILMENTS | {"confusion"} \
            and eng.sides[eng.side_of(target)].safeguard > 0:
        if move.category == STATUS:
            events.append(Event(E.MOVE_FAILED, eng.side_of(user),
                                {"move": move.name, "safeguard": True}))
        return
    if ailment == "confusion":
        if target.vol.confusion_turns <= 0 and not target.fainted \
                and not passives.confusion_blocked(target):
            target.vol.confusion_turns = eng.rng.randint(2, 5)
            events.append(Event(E.CONFUSED, eng.side_of(target),
                                {"pokemon": target.name, "start": True}))
            passives.check_lum(eng, target, events)
        return
    if ailment in NONVOLATILE_AILMENTS:
        status = "toxic" if (ailment == "poison" and move.id in TOXIC_MOVES) else ailment
        attacker_ref = user if target is not user else None
        ok = apply_status(eng, target, status, events, from_attacker=attacker_ref)
        if not ok and move.category == STATUS:
            events.append(Event(E.MOVE_FAILED, eng.side_of(user), {"move": move.name}))
        return
    if ailment == "leech-seed":
        if "grass" in target.types or target.vol.leech_seeded:
            events.append(Event(E.MOVE_FAILED, eng.side_of(user), {"move": move.name}))
        else:
            target.vol.leech_seeded = True
            events.append(Event(E.LEECH_SEED, eng.side_of(target),
                                {"pokemon": target.name}))
        return
    if ailment == "infatuation":
        # Oblivious is immune to infatuation
        if passives.abil(target) == "oblivious":
            return
        # Simplification: genders aren't modeled yet, so Attract always
        # takes (documented in ARCHITECTURE.md).
        if not target.vol.infatuated and not target.fainted:
            target.vol.infatuated = True
            events.append(Event(E.CONFUSED, eng.side_of(target),
                                {"pokemon": target.name, "start": True,
                                 "infatuated": True}))
        return
    if ailment == "trap":
        if target.vol.trap_turns <= 0 and not target.fainted:
            target.vol.trap_turns = eng.rng.randint(4, 5)
            target.vol.trap_name = move.name
            events.append(Event(E.TRAPPED, eng.side_of(target),
                                {"pokemon": target.name, "move": move.name}))
        return
    # disable / encore / infatuation / etc. -- later phases
    events.append(Event(E.EFFECT_SKIPPED, eng.side_of(user),
                        {"move": move.id, "effect": ailment}))


def apply_stat_changes(eng, user, target, move: MoveData, events, *,
                       chance_mult: float = 1.0) -> None:
    eff = move.effect
    if not eff.stat_changes:
        return
    # PokeAPI convention: for damaging moves, 'damage+raise' stat changes
    # apply to the USER (incl. Superpower/Overheat's self-drops), while
    # 'damage+lower' applies to the TARGET. Status moves follow move.target.
    kind = eff.kind.replace("+", "-")
    if move.is_damaging:
        recipient = user if kind == "damage-raise" else target
    else:
        recipient = user if move.targets_user else target
    chance = eff.stat_chance or 100
    if chance < 100:
        mult = passives.secondary_mult(user, recipient is target, target)
        chance = chance * mult
    if eng.rng.randint(1, 100) > chance:
        return
    misted = (recipient is target and recipient is not user
              and eng.sides[eng.side_of(recipient)].mist > 0)
    lowering_target = (recipient is target and recipient is not user)
    # Clear Body / White Smoke: no stat lowering by foes at all
    # Hyper Cutter: only Attack cannot be lowered by foes
    # Big Pecks: only Defense cannot be lowered by foes
    foe_lowering = lowering_target
    _ra = passives.abil(recipient) if lowering_target else ""
    _stat_block_all = _ra in ("clear-body", "white-smoke")
    for sc in eff.stat_changes:
        if recipient.fainted:
            continue
        if misted and sc.change < 0:
            events.append(Event(E.MOVE_FAILED, eng.side_of(user),
                                {"move": move.name, "mist": True}))
            continue
        # Ability-based stat lower immunity
        if foe_lowering and sc.change < 0:
            if _stat_block_all:
                continue
            if _ra == "hyper-cutter" and sc.stat == "attack":
                continue
            if _ra == "big-pecks" and sc.stat == "defense":
                continue
            if _ra == "keen-eye" and sc.stat == "accuracy":
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
        # Defiant / Competitive: triggered when foe lowers our stat
        if lowering_target and sc.change < 0 and not recipient.fainted:
            passives.on_defiant_competitive(eng, recipient, sc.stat, sc.change,
                                            True, events)


# ── Damage application helpers ───────────────────────────────────────

def deal_damage(eng, target: BattlePokemon, amount: int, events,
                detail: dict | None = None) -> int:
    if amount >= target.current_hp and target.vol.endured:
        amount = target.current_hp - 1
        events.append(Event(E.PROTECTED, eng.side_of(target),
                            {"pokemon": target.name, "setup": False,
                             "endure": True}))
    if amount >= target.current_hp:
        survive = passives.survives_lethal(target)
        if survive:
            kind, name = survive
            amount = target.current_hp - 1
            if kind == "item":
                target.state.held_item = None
                events.append(Event(E.ITEM_HELD, eng.side_of(target),
                                    {"item": name, "pokemon": target.name,
                                     "endure": True}))
            else:
                events.append(Event(E.ABILITY, eng.side_of(target),
                                    {"ability": name, "pokemon": target.name,
                                     "endure": True}))
    dealt = target.take_damage(amount)
    ev = {"pokemon": target.name, "amount": dealt,
          "remaining_hp": target.current_hp, "max_hp": target.max_hp}
    if detail:
        ev.update({"crit": detail.get("crit", False),
                   "effectiveness": detail.get("effectiveness", 1.0)})
    events.append(Event(E.DAMAGE, eng.side_of(target), ev))
    eng.announce_faint(target, events)
    passives.check_hp_berry(eng, target, events)
    return dealt


def roll_hits(eng, eff: MoveEffect, user=None) -> int:
    if not eff.min_hits:
        return 1
    if eff.min_hits == eff.max_hits:
        return eff.min_hits
    # Skill Link: always hit the maximum number of times
    if user is not None and passives.abil(user) == "skill-link":
        return eff.max_hits
    if (eff.min_hits, eff.max_hits) == (2, 5):
        pool = [n for n, w in MULTI_HIT_WEIGHTS for _ in range(w)]
        return eng.rng.choice(pool)
    return eng.rng.randint(eff.min_hits, eff.max_hits)


def force_switch(eng, target_side: str, events) -> bool:
    """Roar/Whirlwind/Dragon Tail. Wild battles end; trainer battles drag
    a random able benched Pokemon in."""
    target = eng.active(target_side)
    if passives.abil(target) == "suction-cups":
        return False
    if eng.wild:
        events.append(Event(E.RUN_SUCCESS, target_side, {"forced": True}))
        eng._end_battle("escaped", events)
        return True
    bench = eng.bench(target_side)
    if not bench:
        return False
    old = eng.active(target_side)
    slot = next((i for i, idx in enumerate(eng.active_slots[target_side])
                 if eng.parties[target_side][idx] is old), 0)
    old.on_switch_out()
    eng._set_active(target_side, eng.rng.choice(bench), slot)
    events.append(Event(E.DRAGGED, target_side,
                        {"pokemon": eng.parties[target_side][
                            eng.active_slots[target_side][slot]].name}))
    events.append(eng._send_in_event(target_side, slot))
    eng._switch_in_effects(target_side, events, slot)
    return True


# ── Main entry ───────────────────────────────────────────────────────

def execute_move(eng, side: str, move: MoveData, events,
                 power_mult: float = 1.0,
                 target: BattlePokemon | None = None) -> None:
    """Execute `move` by the active Pokemon on `side`. Incapacity checks,
    PP, and two-turn/rampage bookkeeping happen in the engine before this.
    `target` defaults to the lone foe (singles); the doubles path passes an
    explicit target."""
    user = eng.active(side)
    if target is None:
        target = eng.active(other(side))

    # Mold Breaker: suppress the target's abilities for this move's duration
    _mb = (passives.abil(user) == "mold-breaker"
           and not move.targets_user and target is not None)
    if _mb:
        events.append(Event(E.ABILITY, side,
                            {"ability": "mold-breaker", "pokemon": user.name}))
        passives.mb_suppress(target)

    try:
        _execute_move_inner(eng, side, move, events, power_mult, user, target)
    finally:
        if _mb:
            passives.mb_clear(target)


def _execute_move_inner(eng, side, move, events, power_mult, user, target):
    events.append(Event(E.MOVE_USED, side, {"pokemon": user.name, "move": move.name}))

    targets_foe = not move.targets_user

    # Protection blocks foe-targeted moves carrying the 'protect' flag.
    if targets_foe and target.vol.protected and "protect" in move.flags:
        events.append(Event(E.PROTECTED, eng.side_of(target),
                            {"pokemon": target.name, "setup": False}))
        return

    # Semi-invulnerable target (Fly/Dig/...): auto-miss unless excepted.
    semi = target.vol.semi_invulnerable
    if targets_foe and semi:
        mult = SEMI_HIT.get(semi, {}).get(move.id)
        if mult is None:
            events.append(Event(E.MOVE_MISSED, side, {"move": move.name}))
            return
        power_mult *= mult

    # Soundproof: immune to sound-based moves
    if targets_foe and move.id in SOUND_MOVES and passives.soundproof_immune(target):
        events.append(Event(E.ABILITY, eng.side_of(target),
                            {"ability": "soundproof", "pokemon": target.name}))
        events.append(Event(E.MOVE_IMMUNE, eng.side_of(target),
                            {"pokemon": target.name}))
        return

    # Overcoat: immune to powder / spore moves
    if targets_foe and move.id in POWDER_MOVES and passives.powder_immune(target):
        events.append(Event(E.ABILITY, eng.side_of(target),
                            {"ability": "overcoat", "pokemon": target.name}))
        events.append(Event(E.MOVE_IMMUNE, eng.side_of(target),
                            {"pokemon": target.name}))
        return

    if move.id in HANDLERS:
        HANDLERS[move.id](eng, user, target, move, events)
        return

    kind = move.effect.kind.replace("+", "-")

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
        absorb = passives.immunity_or_absorb(target, move)
        if absorb == "immune":
            events.append(Event(E.ABILITY, eng.side_of(target),
                                {"ability": passives.abil(target),
                                 "pokemon": target.name}))
            events.append(Event(E.MOVE_IMMUNE, eng.side_of(target),
                                {"pokemon": target.name}))
            return
        if absorb == "absorb":
            events.append(Event(E.ABILITY, eng.side_of(target),
                                {"ability": passives.abil(target),
                                 "pokemon": target.name}))
            if passives.abil(target) == "dry-skin":
                # Dry Skin heals 25% on water hit
                healed = target.heal(max(1, target.max_hp // 4))
            else:
                healed = target.heal(max(1, target.max_hp // 4))
            if healed:
                events.append(Event(E.HEAL, eng.side_of(target),
                                    {"pokemon": target.name, "amount": healed,
                                     "remaining_hp": target.current_hp}))
            return
        if absorb == "flash-fire":
            passives.on_flash_fire(eng, eng.side_of(target), target, move, events)
            return
        if absorb == "absorb-raise":
            passives.on_absorb_raise(eng, eng.side_of(target), target, move, events)
            return
        eff_mult = (1.0 if move.type == "typeless"
                    else eng.data.effectiveness(move.type, target.types))
        # Scrappy: Normal/Fighting bypass Ghost immunity
        if eff_mult == 0 and passives.abil(user) == "scrappy" \
                and move.type in ("normal", "fighting") and "ghost" in target.types:
            eff_mult = 1.0
        if eff_mult == 0:
            events.append(Event(E.MOVE_IMMUNE, eng.side_of(target), {"pokemon": target.name}))
            return
        if not _hits(eng, user, target, move):
            events.append(Event(E.MOVE_MISSED, side, {"move": move.name}))
            return

        if move.type == "electric" and eng.sport["mud"] > 0:
            power_mult *= 0.33
        if move.type == "fire" and eng.sport["water"] > 0:
            power_mult *= 0.33

        # Infiltrator: bypass Light Screen, Reflect
        screened = (eng.screened(eng.side_of(target), move)
                    and passives.abil(user) != "infiltrator")
        if move.id in FIXED_DAMAGE:
            deal_damage(eng, target, FIXED_DAMAGE[move.id], events,
                        {"effectiveness": 1.0, "crit": False})
            total, landed = FIXED_DAMAGE[move.id], 1
        elif move.id in LEVEL_DAMAGE:
            deal_damage(eng, target, user.level, events,
                        {"effectiveness": 1.0, "crit": False})
            total, landed = user.level, 1
        else:
            hits = roll_hits(eng, move.effect, user)
            total, landed = 0, 0
            for _ in range(hits):
                if target.fainted or user.fainted:
                    break
                crit = eng.rng.random() < eng.crit_chance_for(user, move, target)
                dmg, detail = calc_damage(eng.data, user, target, move,
                                          rng=eng.rng, crit=crit,
                                          weather=eng.weather, screened=screened,
                                          power_mult=power_mult)
                total += deal_damage(eng, target, dmg, events, detail)
                landed += 1
            if hits > 1:
                events.append(Event(E.MULTI_HIT, side, {"hits": landed}))
        if total > 0:
            target.vol.last_hit = (move.category, total)

        if target.status == "freeze" and move.type == "fire" and not target.fainted:
            target.status = None
            events.append(Event(E.THAWED, eng.side_of(target), {"pokemon": target.name}))

        # Dry Skin: fire hits do extra 25% damage
        if move.type == "fire" and not target.fainted and landed:
            passives.on_dry_skin_fire(eng, target, total, events)

        # Justified: hit by dark move -> +1 Atk
        if move.type == "dark" and not target.fainted and landed \
                and passives.abil(target) == "justified":
            events.append(Event(E.ABILITY, eng.side_of(target),
                                {"ability": "justified", "pokemon": target.name}))
            applied = target.modify_stage("attack", 1)
            if applied:
                events.append(Event(E.STAT_CHANGE, eng.side_of(target),
                                    {"pokemon": target.name, "stat": "attack",
                                     "change": applied,
                                     "stage": target.stages["attack"]}))

        # Weak Armor: hit by physical move -> -1 Def, +1 Speed (Gen 5)
        if move.category == "physical" and not target.fainted and landed \
                and passives.abil(target) == "weak-armor":
            events.append(Event(E.ABILITY, eng.side_of(target),
                                {"ability": "weak-armor", "pokemon": target.name}))
            for stat, change in (("defense", -1), ("speed", 1)):
                applied = target.modify_stage(stat, change)
                if applied:
                    events.append(Event(E.STAT_CHANGE, eng.side_of(target),
                                        {"pokemon": target.name, "stat": stat,
                                         "change": applied,
                                         "stage": target.stages[stat]}))

        # Drain / recoil
        drain = move.effect.drain
        if drain > 0 and user.vol.heal_block_turns > 0:
            drain = 0
        if drain > 0 and total > 0 and not user.fainted:
            if passives.liquid_ooze_reverses(target):
                # Liquid Ooze: drain deals damage to the drainer instead
                rec = max(1, total * drain // 100)
                user.take_damage(rec)
                events.append(Event(E.ABILITY, eng.side_of(target),
                                    {"ability": "liquid-ooze", "pokemon": target.name}))
                events.append(Event(E.RECOIL, side,
                                    {"pokemon": user.name, "amount": rec,
                                     "remaining_hp": user.current_hp}))
                eng.announce_faint(user, events)
            else:
                healed = user.heal(max(1, total * drain // 100))
                if healed:
                    events.append(Event(E.DRAIN, side, {"pokemon": user.name, "amount": healed}))
        elif drain < 0 and total > 0 and not user.fainted:
            if passives.abil(user) != "rock-head":
                rec = max(1, total * (-drain) // 100)
                user.take_damage(rec)
                events.append(Event(E.RECOIL, side, {"pokemon": user.name, "amount": rec,
                                                     "remaining_hp": user.current_hp}))
                eng.announce_faint(user, events)

        # Contact abilities punish the attacker
        if landed and "contact" in move.flags and not user.fainted:
            passives.on_contact(eng, user, target, events)

        # Rattled: hit by Dark/Ghost/Bug -> +1 Speed
        if landed and not target.fainted and passives.abil(target) == "rattled" \
                and move.type in ("dark", "ghost", "bug"):
            events.append(Event(E.ABILITY, eng.side_of(target),
                                {"ability": "rattled", "pokemon": target.name}))
            applied = target.modify_stage("speed", 1)
            if applied:
                events.append(Event(E.STAT_CHANGE, eng.side_of(target),
                                    {"pokemon": target.name, "stat": "speed",
                                     "change": applied,
                                     "stage": target.stages["speed"]}))

        # Anger Point: critical hit -> maximize attack
        if landed and not target.fainted and passives.abil(target) == "anger-point":
            last_detail = None
            for ev in reversed(events):
                if ev.type == E.DAMAGE and ev.side == eng.side_of(target):
                    last_detail = ev.data
                    break
            if last_detail and last_detail.get("crit"):
                events.append(Event(E.ABILITY, eng.side_of(target),
                                    {"ability": "anger-point", "pokemon": target.name}))
                applied = target.modify_stage("attack", 12)  # max out at +6
                if applied:
                    events.append(Event(E.STAT_CHANGE, eng.side_of(target),
                                        {"pokemon": target.name, "stat": "attack",
                                         "change": applied,
                                         "stage": target.stages["attack"]}))

        # Moxie: user KOs foe -> +1 Attack
        if target.fainted and not user.fainted and passives.abil(user) == "moxie":
            events.append(Event(E.ABILITY, side,
                                {"ability": "moxie", "pokemon": user.name}))
            applied = user.modify_stage("attack", 1)
            if applied:
                events.append(Event(E.STAT_CHANGE, side,
                                    {"pokemon": user.name, "stat": "attack",
                                     "change": applied,
                                     "stage": user.stages["attack"]}))

        # Secondary effects only land if the target is still standing
        # Sheer Force removes all secondaries (they were already skipped in power_mod)
        sheer = passives.abil(user) == "sheer-force" and passives._has_secondary(move)
        if not target.fainted and landed and not sheer:
            sec_mult = passives.secondary_mult(user, True, target)
            ail_chance = move.effect.ailment_chance or (100 if move.effect.ailment else 0)
            if ail_chance < 100:
                ail_chance *= sec_mult
            if move.effect.ailment and eng.rng.randint(1, 100) <= ail_chance:
                apply_ailment(eng, user, target, move, events)
            flinch = move.effect.flinch_chance * sec_mult
            if flinch and not target.vol.has_moved \
                    and passives.abil(target) != "inner-focus":
                if eng.rng.randint(1, 100) <= flinch:
                    target.vol.flinched = True
        if not sheer:
            apply_stat_changes(eng, user, target, move, events)

        # Force-switch riders (Dragon Tail / Circle Throw)
        if kind == "force-switch" and not target.fainted and not eng.over:
            force_switch(eng, other(side), events)

        # Life Orb recoil
        if landed and total > 0 and passives.held(user) == "life-orb" \
                and not user.fainted:
            rec = max(1, user.max_hp // 10)
            user.take_damage(rec)
            events.append(Event(E.ITEM_HELD, side, {"item": "life-orb",
                                                    "pokemon": user.name}))
            events.append(Event(E.RECOIL, side, {"pokemon": user.name, "amount": rec,
                                                 "remaining_hp": user.current_hp}))
            eng.announce_faint(user, events)

        if move.id == "struggle" and not user.fainted:
            rec = max(1, user.max_hp // 4)
            user.take_damage(rec)
            events.append(Event(E.RECOIL, side, {"pokemon": user.name, "amount": rec,
                                                 "remaining_hp": user.current_hp}))
            eng.announce_faint(user, events)

        if move.id in RECHARGE_MOVES and landed and not user.fainted:
            user.vol.recharging = True

        # Destiny Bond: if target fainted and had destiny-bond, user also faints
        if target.fainted and target.vol.destiny_bond and not user.fainted:
            user.take_damage(user.current_hp)
            events.append(Event(E.ABILITY, eng.side_of(target),
                                {"ability": "destiny-bond", "pokemon": target.name}))
            eng.announce_faint(user, events)

        # Grudge: if target fainted and had grudge, KO move PP -> 0
        if target.fainted and target.vol.grudge:
            slot = user.state.move_slot(move.id)
            if slot is not None:
                slot.pp = 0
                events.append(Event(E.ABILITY, eng.side_of(target),
                                    {"ability": "grudge", "pokemon": target.name,
                                     "move": move.id}))
        return

    # ── Status moves ──
    # Snatch: steal user-targeted buffing moves
    if move.targets_user and not move.is_damaging:
        foe = eng.active(other(side))
        if foe.vol.snatch_active:
            foe.vol.snatch_active = False
            events.append(Event(E.ABILITY, eng.side_of(foe),
                                {"ability": "snatch", "pokemon": foe.name,
                                 "stolen": move.name}))
            # Execute the stolen move for the snatcher
            execute_move(eng, eng.side_of(foe), move, events)
            return
    # Assault Vest: user cannot use status moves
    if passives.held(user) == "assault-vest" and not move.is_damaging:
        events.append(Event(E.MOVE_FAILED, side, {"move": move.name,
                                                   "reason": "assault-vest"}))
        return
    if move.effect.ailment and move.effect.ailment in NONVOLATILE_AILMENTS:
        if eng.data.effectiveness(move.type, target.types) == 0:
            events.append(Event(E.MOVE_IMMUNE, eng.side_of(target), {"pokemon": target.name}))
            return
    if targets_foe and not _hits(eng, user, target, move):
        events.append(Event(E.MOVE_MISSED, side, {"move": move.name}))
        return

    # Magic Bounce: reflect foe-targeted status moves back at the user
    if targets_foe and not move.is_damaging and kind != "force-switch" \
            and passives.abil(target) == "magic-bounce":
        events.append(Event(E.ABILITY, eng.side_of(target),
                            {"ability": "magic-bounce", "pokemon": target.name}))
        # Apply the move's ailment/stat effects to the original user instead
        if move.effect.ailment:
            apply_ailment(eng, target, user, move, events)
        if move.effect.stat_changes:
            apply_stat_changes(eng, target, user, move, events)
        return

    if kind == "force-switch":
        if not force_switch(eng, other(side), events):
            events.append(Event(E.MOVE_FAILED, side, {"move": move.name}))
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
        if recipient.vol.heal_block_turns > 0:
            events.append(Event(E.MOVE_FAILED, side, {"move": move.name,
                                                      "heal_block": True}))
            return
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


# ── Special-case handlers (the Phase 2 extension point) ──────────────

@handler("rest")
def _rest(eng, user, target, move, events):
    if user.current_hp == user.max_hp or user.status == "sleep" \
            or passives.status_blocked(user, "sleep"):
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


def _protect(eng, user, target, move, events):
    side = eng.side_of(user)
    ok = user.vol.protect_count == 0 or \
        eng.rng.random() < 0.5 ** user.vol.protect_count
    if ok:
        user.vol.protected = True
        user.vol.protect_count += 1
        events.append(Event(E.PROTECTED, side, {"pokemon": user.name,
                                                "setup": True}))
    else:
        user.vol.protect_count = 0
        events.append(Event(E.MOVE_FAILED, side, {"move": move.name}))


HANDLERS["protect"] = _protect
HANDLERS["detect"] = _protect


def _weather_move(kind):
    def fn(eng, user, target, move, events):
        if eng.weather == kind:
            events.append(Event(E.MOVE_FAILED, eng.side_of(user), {"move": move.name}))
        else:
            eng.set_weather(kind, 5, events)
    return fn


HANDLERS["rain-dance"] = _weather_move("rain")
HANDLERS["sunny-day"] = _weather_move("sun")
HANDLERS["sandstorm"] = _weather_move("sandstorm")
HANDLERS["hail"] = _weather_move("hail")


def _screen(attr):
    def fn(eng, user, target, move, events):
        side = eng.side_of(user)
        ss = eng.sides[side]
        if getattr(ss, attr) > 0:
            events.append(Event(E.MOVE_FAILED, side, {"move": move.name}))
            return
        setattr(ss, attr, 5)
        events.append(Event(E.SCREEN_START, side, {"screen": attr.replace("_", "-")}))
    return fn


HANDLERS["reflect"] = _screen("reflect")
HANDLERS["light-screen"] = _screen("light_screen")


def _hazard(attr, maximum):
    def fn(eng, user, target, move, events):
        side = eng.side_of(user)
        foe_side = other(side)
        ss = eng.sides[foe_side]
        cur = getattr(ss, attr)
        if cur is True or cur == maximum:
            events.append(Event(E.MOVE_FAILED, side, {"move": move.name}))
            return
        setattr(ss, attr, True if maximum is True else cur + 1)
        events.append(Event(E.HAZARD_SET, foe_side,
                            {"hazard": attr.replace("_", "-"),
                             "layers": 1 if maximum is True else cur + 1}))
    return fn


HANDLERS["stealth-rock"] = _hazard("stealth_rock", True)
HANDLERS["spikes"] = _hazard("spikes", 3)
HANDLERS["toxic-spikes"] = _hazard("toxic_spikes", 2)


@handler("rapid-spin")
def _rapid_spin(eng, user, target, move, events):
    side = eng.side_of(user)
    if not accuracy_check(move, user, target, rng=eng.rng, weather=eng.weather):
        events.append(Event(E.MOVE_MISSED, side, {"move": move.name}))
        return
    eff = eng.data.effectiveness(move.type, target.types)
    if eff > 0:
        crit = eng.rng.random() < eng.crit_chance_for(user, move, target)
        dmg, detail = calc_damage(eng.data, user, target, move, rng=eng.rng,
                                  crit=crit, weather=eng.weather,
                                  screened=eng.screened(other(side), move))
        deal_damage(eng, target, dmg, events, detail)
    else:
        events.append(Event(E.MOVE_IMMUNE, eng.side_of(target),
                            {"pokemon": target.name}))
    for hz in eng.sides[side].clear_hazards():
        events.append(Event(E.HAZARD_CLEARED, side, {"hazard": hz}))
    user.vol.leech_seeded = False
    if user.vol.trap_turns > 0:
        user.vol.trap_turns = 0
        events.append(Event(E.TRAP_END, side, {"pokemon": user.name}))


@handler("focus-energy")
def _focus_energy(eng, user, target, move, events):
    side = eng.side_of(user)
    if user.vol.crit_bonus > 0:
        events.append(Event(E.MOVE_FAILED, side, {"move": move.name}))
        return
    user.vol.crit_bonus = 2
    events.append(Event(E.STAT_CHANGE, side,
                        {"pokemon": user.name, "stat": "crit_rate",
                         "change": 2, "stage": 2}))


@handler("haze")
def _haze(eng, user, target, move, events):
    for bp in (user, target):
        bp.stages = {k: 0 for k in bp.stages}
    events.append(Event(E.STAGES_RESET, None, {}))


def _explode(eng, user, target, move, events):
    side = eng.side_of(user)

    def faint_user():
        user.take_damage(user.current_hp)
        eng.announce_faint(user, events)

    # Damp ability blocks explosion/self-destruct
    if passives.abil(user) == "damp" or passives.abil(target) == "damp":
        events.append(Event(E.MOVE_FAILED, side, {"move": move.name}))
        return
    if target.vol.protected:
        events.append(Event(E.PROTECTED, eng.side_of(target),
                            {"pokemon": target.name, "setup": False}))
        faint_user()
        return
    eff = eng.data.effectiveness(move.type, target.types)
    if eff == 0:
        events.append(Event(E.MOVE_IMMUNE, eng.side_of(target), {"pokemon": target.name}))
        faint_user()
        return
    if not accuracy_check(move, user, target, rng=eng.rng, weather=eng.weather):
        events.append(Event(E.MOVE_MISSED, side, {"move": move.name}))
        faint_user()
        return
    crit = eng.rng.random() < eng.crit_chance_for(user, move, target)
    dmg, detail = calc_damage(eng.data, user, target, move, rng=eng.rng,
                              crit=crit, weather=eng.weather,
                              screened=eng.screened(other(side), move))
    deal_damage(eng, target, dmg, events, detail)
    faint_user()


HANDLERS["explosion"] = _explode
HANDLERS["self-destruct"] = _explode


@handler("false-swipe")
def _false_swipe(eng, user, target, move, events):
    side = eng.side_of(user)
    eff = eng.data.effectiveness(move.type, target.types)
    if eff == 0:
        events.append(Event(E.MOVE_IMMUNE, eng.side_of(target), {"pokemon": target.name}))
        return
    if not accuracy_check(move, user, target, rng=eng.rng, weather=eng.weather):
        events.append(Event(E.MOVE_MISSED, side, {"move": move.name}))
        return
    crit = eng.rng.random() < eng.crit_chance_for(user, move, target)
    dmg, detail = calc_damage(eng.data, user, target, move, rng=eng.rng,
                              crit=crit, weather=eng.weather,
                              screened=eng.screened(other(side), move))
    dmg = min(dmg, max(0, target.current_hp - 1))
    if dmg:
        deal_damage(eng, target, dmg, events, detail)
    else:
        events.append(Event(E.DAMAGE, eng.side_of(target),
                            {"pokemon": target.name, "amount": 0,
                             "remaining_hp": target.current_hp,
                             "max_hp": target.max_hp, "crit": False,
                             "effectiveness": eff}))


# ── Phase 2 status-move handlers (coverage batch) ────────────────────

def _fails_in_singles(eng, user, target, move, events):
    events.append(Event(E.MOVE_FAILED, eng.side_of(user), {"move": move.name}))


for _m in ("helping-hand", "follow-me", "rage-powder", "ally-switch", "splash"):
    HANDLERS[_m] = _fails_in_singles


def _endure(eng, user, target, move, events):
    side = eng.side_of(user)
    ok = user.vol.protect_count == 0 or \
        eng.rng.random() < 0.5 ** user.vol.protect_count
    if ok:
        user.vol.endured = True
        user.vol.protect_count += 1
        events.append(Event(E.PROTECTED, side, {"pokemon": user.name,
                                                "setup": True, "endure": True}))
    else:
        user.vol.protect_count = 0
        events.append(Event(E.MOVE_FAILED, side, {"move": move.name}))


HANDLERS["endure"] = _endure


def _side_condition(attr, turns):
    def fn(eng, user, target, move, events):
        side = eng.side_of(user)
        ss = eng.sides[side]
        if getattr(ss, attr) > 0:
            events.append(Event(E.MOVE_FAILED, side, {"move": move.name}))
            return
        setattr(ss, attr, turns)
        events.append(Event(E.SCREEN_START, side,
                            {"screen": attr.replace("_", "-")}))
    return fn


HANDLERS["safeguard"] = _side_condition("safeguard", 5)
HANDLERS["mist"] = _side_condition("mist", 5)
HANDLERS["lucky-chant"] = _side_condition("lucky_chant", 5)
HANDLERS["tailwind"] = _side_condition("tailwind", 4)


def _lock_on(eng, user, target, move, events):
    user.vol.lock_on = True
    events.append(Event(E.STAT_CHANGE, eng.side_of(user),
                        {"pokemon": user.name, "stat": "accuracy",
                         "change": 0, "stage": 0, "lock_on": True}))


HANDLERS["lock-on"] = _lock_on
HANDLERS["mind-reader"] = _lock_on


@handler("psych-up")
def _psych_up(eng, user, target, move, events):
    user.stages = dict(target.stages)
    events.append(Event(E.STAGES_RESET, eng.side_of(user), {"copied": True}))


@handler("taunt")
def _taunt(eng, user, target, move, events):
    if target.vol.taunt_turns > 0:
        events.append(Event(E.MOVE_FAILED, eng.side_of(user), {"move": move.name}))
        return
    target.vol.taunt_turns = 3
    events.append(Event(E.TRAPPED, eng.side_of(target),
                        {"pokemon": target.name, "move": move.name, "taunt": True}))


def _mean_look(eng, user, target, move, events):
    if target.vol.no_escape:
        events.append(Event(E.MOVE_FAILED, eng.side_of(user), {"move": move.name}))
        return
    target.vol.no_escape = True
    events.append(Event(E.TRAPPED, eng.side_of(target),
                        {"pokemon": target.name, "move": move.name}))


for _m in ("mean-look", "block", "spider-web"):
    HANDLERS[_m] = _mean_look


@handler("gastro-acid")
def _gastro_acid(eng, user, target, move, events):
    if target.vol.ability_suppressed:
        events.append(Event(E.MOVE_FAILED, eng.side_of(user), {"move": move.name}))
        return
    target.vol.ability_suppressed = True
    events.append(Event(E.ABILITY, eng.side_of(target),
                        {"ability": "suppressed", "pokemon": target.name}))


@handler("ingrain")
def _ingrain(eng, user, target, move, events):
    if user.vol.ingrained:
        events.append(Event(E.MOVE_FAILED, eng.side_of(user), {"move": move.name}))
        return
    user.vol.ingrained = True
    events.append(Event(E.LEECH_SEED, eng.side_of(user),
                        {"pokemon": user.name, "ingrain": True}))


@handler("telekinesis")
def _telekinesis(eng, user, target, move, events):
    if target.vol.telekinesis_turns > 0:
        events.append(Event(E.MOVE_FAILED, eng.side_of(user), {"move": move.name}))
        return
    target.vol.telekinesis_turns = 3
    events.append(Event(E.STAT_CHANGE, eng.side_of(target),
                        {"pokemon": target.name, "stat": "evasion",
                         "change": 0, "stage": 0, "telekinesis": True}))


@handler("refresh")
def _refresh(eng, user, target, move, events):
    if user.status in ("burn", "paralysis", "poison", "toxic"):
        cured = user.status
        user.status = None
        user.vol.toxic_counter = 0
        events.append(Event(E.STATUS_CURED, eng.side_of(user),
                            {"pokemon": user.name, "status": cured}))
    else:
        events.append(Event(E.MOVE_FAILED, eng.side_of(user), {"move": move.name}))


def _heal_bell(eng, user, target, move, events):
    side = eng.side_of(user)
    any_cured = False
    for bp in eng.parties[side]:
        if bp.status and not bp.fainted:
            cured = bp.status
            bp.status = None
            bp.vol.toxic_counter = 0
            events.append(Event(E.STATUS_CURED, side,
                                {"pokemon": bp.name, "status": cured}))
            any_cured = True
    if not any_cured:
        events.append(Event(E.MOVE_FAILED, side, {"move": move.name}))


HANDLERS["heal-bell"] = _heal_bell
HANDLERS["aromatherapy"] = _heal_bell


@handler("curse")
def _curse(eng, user, target, move, events):
    side = eng.side_of(user)
    if "ghost" in user.types:
        if target.vol.cursed:
            events.append(Event(E.MOVE_FAILED, side, {"move": move.name}))
            return
        cost = max(1, user.max_hp // 2)
        user.take_damage(cost)
        events.append(Event(E.DAMAGE, side, {"pokemon": user.name, "amount": cost,
                                             "remaining_hp": user.current_hp,
                                             "max_hp": user.max_hp,
                                             "crit": False, "effectiveness": 1.0}))
        eng.announce_faint(user, events)
        target.vol.cursed = True
        events.append(Event(E.LEECH_SEED, eng.side_of(target),
                            {"pokemon": target.name, "curse": True}))
    else:
        for stat, delta in (("attack", 1), ("defense", 1), ("speed", -1)):
            applied = user.modify_stage(stat, delta)
            if applied:
                events.append(Event(E.STAT_CHANGE, side,
                                    {"pokemon": user.name, "stat": stat,
                                     "change": applied,
                                     "stage": user.stages[stat]}))


@handler("pain-split")
def _pain_split(eng, user, target, move, events):
    avg = (user.current_hp + target.current_hp) // 2
    for bp in (user, target):
        s = eng.side_of(bp)
        if avg < bp.current_hp:
            bp.take_damage(bp.current_hp - avg)
            events.append(Event(E.DAMAGE, s, {"pokemon": bp.name,
                                              "amount": bp.current_hp - avg,
                                              "remaining_hp": bp.current_hp,
                                              "max_hp": bp.max_hp,
                                              "crit": False, "effectiveness": 1.0}))
        elif avg > bp.current_hp:
            healed = bp.heal(avg - bp.current_hp)
            events.append(Event(E.HEAL, s, {"pokemon": bp.name, "amount": healed,
                                            "remaining_hp": bp.current_hp}))


@handler("super-fang")
def _super_fang(eng, user, target, move, events):
    side = eng.side_of(user)
    if eng.data.effectiveness(move.type, target.types) == 0:
        events.append(Event(E.MOVE_IMMUNE, eng.side_of(target), {"pokemon": target.name}))
        return
    if not _hits(eng, user, target, move):
        events.append(Event(E.MOVE_MISSED, side, {"move": move.name}))
        return
    deal_damage(eng, target, max(1, target.current_hp // 2), events,
                {"effectiveness": 1.0, "crit": False})


@handler("teleport")
def _teleport(eng, user, target, move, events):
    side = eng.side_of(user)
    if eng.wild:
        events.append(Event(E.RUN_SUCCESS, side, {}))
        eng._end_battle("escaped", events)
    else:
        events.append(Event(E.MOVE_FAILED, side, {"move": move.name}))


def _counter(category, mult):
    def fn(eng, user, target, move, events):
        side = eng.side_of(user)
        hit = user.vol.last_hit
        if not hit or hit[0] != category or hit[1] <= 0:
            events.append(Event(E.MOVE_FAILED, side, {"move": move.name}))
            return
        deal_damage(eng, target, hit[1] * mult, events,
                    {"effectiveness": 1.0, "crit": False})
    return fn


HANDLERS["counter"] = _counter("physical", 2)
HANDLERS["mirror-coat"] = _counter("special", 2)


# ── Phase 2 status-move handlers (second coverage batch) ─────────────

@handler("aqua-ring")
def _aqua_ring(eng, user, target, move, events):
    if user.vol.aqua_ring:
        events.append(Event(E.MOVE_FAILED, eng.side_of(user), {"move": move.name}))
        return
    user.vol.aqua_ring = True
    events.append(Event(E.LEECH_SEED, eng.side_of(user),
                        {"pokemon": user.name, "aqua_ring": True}))


def _ability_override(which):
    """Worry Seed / Entrainment / Simple Beam set a volatile ability
    override (the underlying PokemonState is untouched)."""
    def fn(eng, user, target, move, events):
        new = which if which else passives.abil(user)
        if not new or passives.abil(target) == new:
            events.append(Event(E.MOVE_FAILED, eng.side_of(user), {"move": move.name}))
            return
        target.vol.ability_override = new
        events.append(Event(E.ABILITY, eng.side_of(target),
                            {"ability": new, "pokemon": target.name,
                             "overridden": True}))
    return fn


HANDLERS["worry-seed"] = _ability_override("insomnia")
HANDLERS["simple-beam"] = _ability_override("simple")
HANDLERS["entrainment"] = _ability_override(None)


@handler("encore")
def _encore(eng, user, target, move, events):
    last = target.vol.last_move
    slot = target.state.move_slot(last) if last else None
    if not last or target.vol.encore_move or slot is None or slot.pp <= 0:
        events.append(Event(E.MOVE_FAILED, eng.side_of(user), {"move": move.name}))
        return
    target.vol.encore_move = last
    target.vol.encore_turns = 3
    events.append(Event(E.TRAPPED, eng.side_of(target),
                        {"pokemon": target.name, "move": move.name,
                         "encore": last}))


@handler("torment")
def _torment(eng, user, target, move, events):
    if target.vol.tormented:
        events.append(Event(E.MOVE_FAILED, eng.side_of(user), {"move": move.name}))
        return
    target.vol.tormented = True
    events.append(Event(E.TRAPPED, eng.side_of(target),
                        {"pokemon": target.name, "move": move.name,
                         "torment": True}))


@handler("imprison")
def _imprison(eng, user, target, move, events):
    if user.vol.imprison:
        events.append(Event(E.MOVE_FAILED, eng.side_of(user), {"move": move.name}))
        return
    user.vol.imprison = True
    events.append(Event(E.TRAPPED, eng.side_of(user),
                        {"pokemon": user.name, "move": move.name,
                         "imprison": True}))


@handler("copycat")
def _copycat(eng, user, target, move, events):
    last = target.vol.last_move
    if not last or last == "copycat" or not eng.data.has_move(last):
        events.append(Event(E.MOVE_FAILED, eng.side_of(user), {"move": move.name}))
        return
    execute_move(eng, eng.side_of(user), eng.data.move(last), events)


@handler("bestow")
def _bestow(eng, user, target, move, events):
    if not user.state.held_item or target.state.held_item:
        events.append(Event(E.MOVE_FAILED, eng.side_of(user), {"move": move.name}))
        return
    item = user.state.held_item
    user.state.held_item = None
    target.state.held_item = item
    events.append(Event(E.ITEM_HELD, eng.side_of(target),
                        {"item": item, "pokemon": target.name, "bestow": True}))


@handler("healing-wish")
def _healing_wish(eng, user, target, move, events):
    side = eng.side_of(user)
    if not eng.bench(side):
        events.append(Event(E.MOVE_FAILED, side, {"move": move.name}))
        return
    eng.sides[side].healing_wish = True
    user.take_damage(user.current_hp)
    eng.announce_faint(user, events)


@handler("heal-block")
def _heal_block(eng, user, target, move, events):
    if target.vol.heal_block_turns > 0:
        events.append(Event(E.MOVE_FAILED, eng.side_of(user), {"move": move.name}))
        return
    target.vol.heal_block_turns = 5
    events.append(Event(E.TRAPPED, eng.side_of(target),
                        {"pokemon": target.name, "move": move.name,
                         "heal_block": True}))


@handler("embargo")
def _embargo(eng, user, target, move, events):
    if target.vol.embargo_turns > 0:
        events.append(Event(E.MOVE_FAILED, eng.side_of(user), {"move": move.name}))
        return
    target.vol.embargo_turns = 5
    events.append(Event(E.TRAPPED, eng.side_of(target),
                        {"pokemon": target.name, "move": move.name,
                         "embargo": True}))


def _sport(kind):
    def fn(eng, user, target, move, events):
        if eng.sport[kind] > 0:
            events.append(Event(E.MOVE_FAILED, eng.side_of(user), {"move": move.name}))
            return
        eng.sport[kind] = 5  # simplification: 5 turns (Gen 5 ties it to
        # the user staying in; documented in ARCHITECTURE.md)
        events.append(Event(E.SCREEN_START, None, {"screen": f"{kind}-sport"}))
    return fn


HANDLERS["mud-sport"] = _sport("mud")
HANDLERS["water-sport"] = _sport("water")


@handler("baton-pass")
def _baton_pass(eng, user, target, move, events):
    """Simplification: passes to a random able bench member (a real
    client will prompt for the recipient in Phase 3). Stages and the
    passable volatiles carry over; hazards still apply."""
    side = eng.side_of(user)
    bench = eng.bench(side)
    if not bench:
        events.append(Event(E.MOVE_FAILED, side, {"move": move.name}))
        return
    carry_stages = dict(user.stages)
    v = user.vol
    carry = {"crit_bonus": v.crit_bonus, "leech_seeded": v.leech_seeded,
             "confusion_turns": v.confusion_turns, "ingrained": v.ingrained,
             "aqua_ring": v.aqua_ring, "no_escape": v.no_escape}
    slot = next((i for i, idx in enumerate(eng.active_slots[side])
                 if eng.parties[side][idx] is user), 0)
    user.on_switch_out()
    events.append(Event(E.SWITCH_OUT, side, {"pokemon": user.name}))
    eng._set_active(side, eng.rng.choice(bench), slot)
    incoming = eng.parties[side][eng.active_slots[side][slot]]
    incoming.stages.update(carry_stages)
    for k, val in carry.items():
        setattr(incoming.vol, k, val)
    events.append(eng._send_in_event(side, slot))
    eng._switch_in_effects(side, events, slot)


@handler("belly-drum")
def _belly_drum(eng, user, target, move, events):
    side = eng.side_of(user)
    if user.stages["attack"] >= 6 or user.current_hp * 2 <= user.max_hp:
        events.append(Event(E.MOVE_FAILED, side, {"move": move.name}))
        return
    cost = user.max_hp // 2
    user.take_damage(cost)
    events.append(Event(E.DAMAGE, side, {"pokemon": user.name, "amount": cost,
                                         "remaining_hp": user.current_hp,
                                         "max_hp": user.max_hp,
                                         "crit": False, "effectiveness": 1.0}))
    user.modify_stage("attack", 12)
    events.append(Event(E.STAT_CHANGE, side, {"pokemon": user.name,
                                              "stat": "attack", "change": 12,
                                              "stage": user.stages["attack"]}))


@handler("spite")
def _spite(eng, user, target, move, events):
    side = eng.side_of(user)
    last = target.vol.last_move
    slot = target.state.move_slot(last) if last else None
    if slot is None or slot.pp <= 0:
        events.append(Event(E.MOVE_FAILED, side, {"move": move.name}))
        return
    slot.pp = max(0, slot.pp - 4)
    events.append(Event(E.TRAPPED, eng.side_of(target),
                        {"pokemon": target.name, "move": move.name,
                         "spite": last}))


@handler("role-play")
def _role_play(eng, user, target, move, events):
    new = passives.abil(target)
    if not new or passives.abil(user) == new:
        events.append(Event(E.MOVE_FAILED, eng.side_of(user), {"move": move.name}))
        return
    user.vol.ability_override = new
    events.append(Event(E.ABILITY, eng.side_of(user),
                        {"ability": new, "pokemon": user.name,
                         "overridden": True}))


# ── Phase B move handlers ──────────────────────────────────────────────

@handler("destiny-bond")
def _destiny_bond(eng, user, target, move, events):
    user.vol.destiny_bond = True
    events.append(Event(E.ABILITY, eng.side_of(user),
                        {"ability": "destiny-bond", "pokemon": user.name}))


@handler("grudge")
def _grudge(eng, user, target, move, events):
    user.vol.grudge = True
    events.append(Event(E.ABILITY, eng.side_of(user),
                        {"ability": "grudge", "pokemon": user.name}))


@handler("snatch")
def _snatch(eng, user, target, move, events):
    user.vol.snatch_active = True
    events.append(Event(E.ABILITY, eng.side_of(user),
                        {"ability": "snatch", "pokemon": user.name}))


@handler("magnet-rise")
def _magnet_rise(eng, user, target, move, events):
    side = eng.side_of(user)
    if user.vol.magnet_rise_turns > 0 or passives.abil(user) == "levitate":
        events.append(Event(E.MOVE_FAILED, side, {"move": move.name}))
        return
    user.vol.magnet_rise_turns = 5
    events.append(Event(E.ABILITY, side,
                        {"ability": "magnet-rise", "pokemon": user.name}))


@handler("guard-swap")
def _guard_swap(eng, user, target, move, events):
    for stat in ("defense", "special_defense"):
        user.stages[stat], target.stages[stat] = target.stages[stat], user.stages[stat]
    events.append(Event(E.STAGES_RESET, eng.side_of(user),
                        {"pokemon": user.name, "swap": "guard"}))


@handler("power-swap")
def _power_swap(eng, user, target, move, events):
    for stat in ("attack", "special_attack"):
        user.stages[stat], target.stages[stat] = target.stages[stat], user.stages[stat]
    events.append(Event(E.STAGES_RESET, eng.side_of(user),
                        {"pokemon": user.name, "swap": "power"}))


@handler("yawn")
def _yawn(eng, user, target, move, events):
    side = eng.side_of(user)
    if target.status == "sleep" or target.vol.yawn_turns > 0 \
            or passives.status_blocked(target, "sleep"):
        events.append(Event(E.MOVE_FAILED, side, {"move": move.name}))
        return
    target.vol.yawn_turns = 2
    events.append(Event(E.ABILITY, eng.side_of(target),
                        {"ability": "yawn", "pokemon": target.name}))


@handler("perish-song")
def _perish_song(eng, user, target, move, events):
    side = eng.side_of(user)
    if user.vol.perish_count > 0 or target.vol.perish_count > 0:
        events.append(Event(E.MOVE_FAILED, side, {"move": move.name}))
        return
    user.vol.perish_count = 3
    target.vol.perish_count = 3
    events.append(Event(E.ABILITY, side,
                        {"ability": "perish-song", "pokemon": user.name,
                         "count": 3}))
    events.append(Event(E.ABILITY, eng.side_of(target),
                        {"ability": "perish-song", "pokemon": target.name,
                         "count": 3}))


@handler("transform")
def _transform(eng, user, target, move, events):
    side = eng.side_of(user)
    if user.vol.transformed or target.vol.transformed:
        events.append(Event(E.MOVE_FAILED, side, {"move": move.name}))
        return
    # Copy target's types, stats (not HP), ability override, and moves
    user.species = target.species
    for k, v in target.stats.items():
        if k != "hp":
            user.state.stats[k] = v
    user.vol.ability_override = passives.abil(target)
    user.vol.transformed = True
    # Copy moves with pp_max and pp = 5
    from ..core.pokemon import MoveSlot
    new_moves = []
    for slot in target.state.moves:
        new_moves.append(MoveSlot(move_id=slot.move_id, pp=5, pp_max=5))
    user.state.moves = new_moves
    events.append(Event(E.ABILITY, side,
                        {"ability": "transform", "pokemon": user.name,
                         "target": target.name}))


@handler("metronome")
def _metronome(eng, user, target, move, events):
    import os
    side = eng.side_of(user)
    moves_dir = os.path.join(eng.data.data_dir, "moves")
    exclude = {"metronome", "struggle", "after-you", "assist", "belch",
               "bestow", "chatter", "copycat", "counter", "covet",
               "destiny-bond", "detect", "endure", "feint",
               "focus-punch", "follow-me", "helping-hand", "me-first",
               "mimic", "mirror-coat", "mirror-move", "protect",
               "rage-powder", "sketch", "sleep-talk", "snatch",
               "snore", "spite", "transform"}
    try:
        available = [f[:-5] for f in os.listdir(moves_dir)
                     if f.endswith(".json") and f[:-5] not in exclude]
    except Exception:
        events.append(Event(E.MOVE_FAILED, side, {"move": move.name}))
        return
    if not available:
        events.append(Event(E.MOVE_FAILED, side, {"move": move.name}))
        return
    chosen_id = eng.rng.choice(sorted(available))
    try:
        chosen = eng.data.move(chosen_id)
    except Exception:
        events.append(Event(E.MOVE_FAILED, side, {"move": move.name}))
        return
    events.append(Event(E.ABILITY, side,
                        {"ability": "metronome", "pokemon": user.name,
                         "chosen": chosen_id}))
    execute_move(eng, side, chosen, events)


_ACUPRESSURE_STATS = ["attack", "defense", "special_attack", "special_defense",
                       "speed", "accuracy", "evasion"]


@handler("acupressure")
def _acupressure(eng, user, target, move, events):
    side = eng.side_of(user)
    available = [s for s in _ACUPRESSURE_STATS if user.stages.get(s, 0) < 6]
    if not available:
        events.append(Event(E.MOVE_FAILED, side, {"move": move.name}))
        return
    chosen = eng.rng.choice(available)
    applied = user.modify_stage(chosen, 2)
    if applied:
        events.append(Event(E.STAT_CHANGE, side,
                            {"pokemon": user.name, "stat": chosen,
                             "change": applied,
                             "stage": user.stages[chosen]}))


@handler("nightmare")
def _nightmare(eng, user, target, move, events):
    side = eng.side_of(user)
    if target.status != "sleep":
        events.append(Event(E.MOVE_FAILED, side, {"move": move.name}))
        return
    if target.vol.nightmare:
        events.append(Event(E.MOVE_FAILED, side, {"move": move.name}))
        return
    target.vol.nightmare = True
    events.append(Event(E.ABILITY, eng.side_of(target),
                        {"ability": "nightmare", "pokemon": target.name}))


@handler("after-you")
def _after_you(eng, user, target, move, events):
    events.append(Event(E.MOVE_FAILED, eng.side_of(user), {"move": move.name}))


@handler("quick-guard")
def _quick_guard(eng, user, target, move, events):
    events.append(Event(E.MOVE_FAILED, eng.side_of(user), {"move": move.name}))


@handler("wide-guard")
def _wide_guard(eng, user, target, move, events):
    events.append(Event(E.MOVE_FAILED, eng.side_of(user), {"move": move.name}))


@handler("wonder-room")
def _wonder_room(eng, user, target, move, events):
    events.append(Event(E.EFFECT_SKIPPED, eng.side_of(user),
                        {"move": move.id, "effect": "wonder-room"}))
