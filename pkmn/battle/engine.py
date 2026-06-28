"""BattleEngine: a pure, deterministic Gen 5-style battle resolver.

Properties that matter:
  * No disk I/O, no printing. Inputs are Actions; outputs are Events.
  * All randomness flows through one injected random.Random, so battles
    are seedable and tests are deterministic.
  * Phase machine: WAITING_ACTIONS -> (maybe WAITING_REPLACEMENT) ->
    ... -> OVER. The caller drives it; the engine never blocks.

Phase 2 adds: abilities, held items, weather, entry hazards, screens,
Protect, two-turn / recharge / rampage moves, partial trapping, Leech
Seed, choice locks, and forced switching. See docs/ROADMAP.md.
"""
from __future__ import annotations

import random
from enum import Enum
from typing import Optional

from ..core.pokemon import PokemonState
from ..core.stats import crit_chance
from ..data.repository import GameData
from . import moves as movex
from . import passives
from .events import E, Event
from .field import SideState
from .state import (BattlePokemon, CatchAction, ItemAction, MoveAction, P1,
                    P2, RunAction, SIDES, SwitchAction, other)


class Phase(str, Enum):
    WAITING_ACTIONS = "waiting_actions"
    WAITING_REPLACEMENT = "waiting_replacement"
    OVER = "over"


class BattleError(Exception):
    pass


class BattleEngine:
    def __init__(self, data: GameData, party1: list, party2: list, *,
                 wild: bool = False, rng: Optional[random.Random] = None,
                 dex_caught: int = 0, format: str = "single"):
        if not party1 or not party2:
            raise BattleError("Both sides need at least one Pokemon")
        self.data = data
        self.rng = rng or random.Random()
        self.wild = wild
        self.format = format
        self.parties = {P1: [BattlePokemon(data, s) for s in party1],
                        P2: [BattlePokemon(data, s) for s in party2]}
        n_slots = 2 if format == "double" else 1
        self.active_slots: dict[str, list[int]] = {}
        for side in SIDES:
            able = [i for i, bp in enumerate(self.parties[side]) if not bp.fainted]
            if not able:
                raise BattleError("Both sides need at least one able Pokemon")
            self.active_slots[side] = able[:n_slots]
        self.active_idx = {P1: self.active_slots[P1][0],
                           P2: self.active_slots[P2][0]}
        self.phase = Phase.WAITING_ACTIONS
        self.pending_replacements: set = set()
        self.winner: Optional[str] = None   # 'p1' | 'p2' | 'draw' | 'escaped' | 'caught'
        self.turn = 0
        self.run_attempts = 0
        self.caught_pokemon: Optional[PokemonState] = None
        self.dex_caught = dex_caught         # species owned -> critical-capture rate
        self.weather: Optional[str] = None  # 'rain'|'sun'|'sandstorm'|'hail'
        self.weather_turns = 0              # -1 == ability weather (no expiry)
        self.sides = {P1: SideState(), P2: SideState()}
        self.sport = {"mud": 0, "water": 0}   # Mud/Water Sport (5 turns)
        self.trick_room: int = 0
        self.gravity_turns: int = 0
        self.magic_room: int = 0
        self.log: list[Event] = []
        ev = [Event(E.BATTLE_START, None, {"wild": wild})]
        for side in SIDES:
            for slot in range(len(self.active_slots[side])):
                ev.append(self._send_in_event(side, slot))
        sendin = [(side, slot) for side in SIDES
                  for slot in range(len(self.active_slots[side]))]
        sendin.sort(key=lambda ss: self.actives(ss[0])[ss[1]].effective_speed(),
                    reverse=True)
        for side, slot in sendin:
            passives.switch_in(self, side, self.actives(side)[slot], ev)
        self.log.extend(ev)
        self._start_events = ev

    # ── helpers ──────────────────────────────────────────────────────
    def _first_able(self, side):
        for i, bp in enumerate(self.parties[side]):
            if not bp.fainted:
                return i
        return None

    def active(self, side: str) -> BattlePokemon:
        return self.parties[side][self.active_idx[side]]

    def actives(self, side: str) -> list[BattlePokemon]:
        return [self.parties[side][i] for i in self.active_slots[side]]

    def _set_active(self, side: str, party_index: int, slot: int = 0) -> None:
        """Point a slot at a new party member, keeping active_idx (slot 0
        mirror) and active_slots in sync."""
        self.active_slots[side][slot] = party_index
        if slot == 0:
            self.active_idx[side] = party_index

    def side_of(self, bp: BattlePokemon) -> str:
        for side in SIDES:
            if self.active(side) is bp:
                return side
        for side in SIDES:
            if bp in self.parties[side]:
                return side
        return "?"

    def _send_in_event(self, side: str, slot: int = 0) -> Event:
        idx = self.active_slots[side][slot]
        bp = self.parties[side][idx]
        return Event(E.SEND_IN, side, {"pokemon": bp.name, "level": bp.level,
                                       "hp": bp.current_hp, "max_hp": bp.max_hp,
                                       "party_index": idx, "slot": slot})

    def crit_chance_for(self, user: BattlePokemon, move,
                        defender: Optional[BattlePokemon] = None) -> float:
        if defender is not None and \
                self.sides[self.side_of(defender)].lucky_chant > 0:
            return 0.0
        if defender is not None and \
                passives.abil(defender) in ("battle-armor", "shell-armor"):
            return 0.0
        return crit_chance(move.crit_stage + passives.crit_bonus(user))

    def speed_of(self, side: str) -> int:
        s = self.active(side).effective_speed(self.weather)
        if self.sides[side].tailwind > 0:
            s *= 2
        return s

    def speed_of_slot(self, side: str, slot: int) -> int:
        bp = self.parties[side][self.active_slots[side][slot]]
        s = bp.effective_speed(self.weather)
        if self.sides[side].tailwind > 0:
            s *= 2
        return s

    def announce_faint(self, bp: BattlePokemon, events) -> None:
        if bp.fainted and not getattr(bp, "_faint_announced", False):
            bp._faint_announced = True
            events.append(Event(E.FAINT, self.side_of(bp), {"pokemon": bp.name}))

    def bench(self, side: str) -> list[int]:
        return [i for i, bp in enumerate(self.parties[side])
                if i not in self.active_slots[side] and not bp.fainted]

    def screened(self, defender_side: str, move) -> bool:
        ss = self.sides[defender_side]
        return ((move.category == "physical" and ss.reflect > 0)
                or (move.category == "special" and ss.light_screen > 0))

    def effective_weather(self) -> Optional[str]:
        """Weather is suppressed when Cloud Nine or Air Lock is active."""
        if passives.suppress_weather(self):
            return None
        return self.weather

    def set_weather(self, kind: str, turns: int, events) -> None:
        self.weather = kind
        self.weather_turns = turns
        events.append(Event(E.WEATHER_START, None, {"weather": kind}))

    def legal_actions(self, side: str, slot: int = 0) -> list:
        if self.phase != Phase.WAITING_ACTIONS:
            return []
        if slot >= len(self.active_slots[side]):
            return []
        bp = self.parties[side][self.active_slots[side][slot]]
        v = bp.vol
        if v.recharging:
            return [MoveAction("recharge")]
        if v.charging:
            return [MoveAction(v.charging)]
        if v.rampage_move:
            return [MoveAction(v.rampage_move)]
        usable = bp.usable_moves()
        if v.choice_lock:
            usable = [s for s in usable if s.move_id == v.choice_lock]
        if v.encore_move:
            usable = [s for s in usable if s.move_id == v.encore_move]
        if v.tormented and v.last_move:
            usable = [s for s in usable if s.move_id != v.last_move]
        if v.disable_turns > 0 and v.disabled_move:
            usable = [s for s in usable if s.move_id != v.disabled_move]
        foe = self.active(other(side))
        if foe.vol.imprison:
            sealed = {s.move_id for s in foe.state.moves}
            usable = [s for s in usable if s.move_id not in sealed]
        if v.taunt_turns > 0:
            usable = [s for s in usable
                      if self.data.move(s.move_id).is_damaging]
        actions: list = ([MoveAction(s.move_id) for s in usable]
                         if usable else [MoveAction("struggle")])
        # Check ability-based trapping by the foe
        _trapped_by_foe = False
        if v.trap_turns <= 0 and not v.no_escape and not v.ingrained:
            foe = self.active(other(side))
            fa = passives.abil(foe)
            user_bp = self.active(side)
            if fa == "shadow-tag":
                _trapped_by_foe = True
            elif fa == "magnet-pull" and "steel" in user_bp.types:
                _trapped_by_foe = True
            elif fa == "arena-trap":
                grounded = (self.gravity_turns > 0
                            or ("flying" not in user_bp.types
                                and passives.abil(user_bp) != "levitate"
                                and user_bp.vol.magnet_rise_turns <= 0))
                if grounded:
                    _trapped_by_foe = True
            if not _trapped_by_foe:
                actions += [SwitchAction(i) for i in self.bench(side)]
        if self.wild and side == P1 and not _trapped_by_foe:
            actions.append(RunAction())
        return actions

    # ── action ordering ──────────────────────────────────────────────
    def _category_priority(self, action, side: str | None = None) -> int:
        if isinstance(action, RunAction):
            return 8
        if isinstance(action, (ItemAction, CatchAction)):
            return 7
        if isinstance(action, SwitchAction):
            return 6
        move = self._resolve_move(action)
        p = move.priority
        # Prankster: status moves gain +1 priority
        if side is not None and not move.is_damaging:
            if passives.abil(self.active(side)) == "prankster":
                p += 1
        return p

    def _resolve_move(self, action: MoveAction):
        if action.move_id == "struggle":
            return movex.STRUGGLE
        if action.move_id == "recharge":
            return movex.RECHARGE_PSEUDO
        return self.data.move(action.move_id)

    # ── public API ───────────────────────────────────────────────────
    def submit_turn(self, p1_action, p2_action) -> list[Event]:
        if self.phase != Phase.WAITING_ACTIONS:
            raise BattleError(f"Cannot submit actions in phase {self.phase}")
        if isinstance(p1_action, list):
            return self._submit_turn_doubles(p1_action, p2_action)
        self.turn += 1
        events: list[Event] = [Event(E.TURN_START, None, {"turn": self.turn})]
        for side in SIDES:
            v = self.active(side).vol
            v.has_moved = False
            v.flinched = False
            v.protected = False
            v.endured = False
            v.last_hit = None
            v.magic_coat_active = False

        pairs = [(P1, p1_action), (P2, p2_action)]
        spd_sign = -1 if self.trick_room > 0 else 1
        pairs.sort(key=lambda pa: (self._category_priority(pa[1], pa[0]),
                                   spd_sign * self.speed_of(pa[0]),
                                   self.rng.random()),
                   reverse=True)

        for side, action in pairs:
            if self.phase == Phase.OVER:
                break
            if self.active(side).fainted:
                continue  # fainted before acting; replacement at end of turn
            self._execute_action(side, action, events)

        if self.phase != Phase.OVER:
            self._end_of_turn(events)
        self._resolve_faints(events)
        self.log.extend(events)
        return events

    def _submit_turn_doubles(self, p1_actions: list, p2_actions: list) -> list[Event]:
        self.turn += 1
        events: list[Event] = [Event(E.TURN_START, None, {"turn": self.turn})]
        for side in SIDES:
            for bp in self.actives(side):
                v = bp.vol
                v.has_moved = False
                v.flinched = False
                v.protected = False
                v.endured = False
                v.last_hit = None
                v.magic_coat_active = False

        # One actor per (side, slot). Capture the BattlePokemon so a slot's
        # action still resolves against the right mon if active_slots mutate.
        actors = []
        for side, acts in ((P1, p1_actions), (P2, p2_actions)):
            for slot in range(len(self.active_slots[side])):
                action = acts[slot] if slot < len(acts) else MoveAction("struggle")
                actors.append((side, slot, action,
                               self.parties[side][self.active_slots[side][slot]]))
        spd_sign = -1 if self.trick_room > 0 else 1
        actors.sort(key=lambda a: (self._category_priority(a[2], a[0]),
                                   spd_sign * self.speed_of_slot(a[0], a[1]),
                                   self.rng.random()),
                    reverse=True)

        for side, slot, action, bp in actors:
            if self.phase == Phase.OVER:
                break
            if bp.fainted:
                continue
            self._execute_action_doubles(side, slot, action, bp, events)

        if self.phase != Phase.OVER:
            self._end_of_turn(events)
        self._resolve_faints(events)
        self.log.extend(events)
        return events

    def _execute_action_doubles(self, side, slot, action, bp, events) -> None:
        if isinstance(action, MoveAction):
            self._do_move_doubles(side, slot, action, bp, events)
        elif isinstance(action, SwitchAction):
            self._do_switch_slot(side, slot, action.party_index, events)
        else:
            # Item/Catch/Run fall back to the singles path (slot-agnostic).
            self._execute_action(side, action, events)

    def submit_replacement(self, side: str, party_index: int,
                           slot: int = 0) -> list[Event]:
        token = (side, slot) if self.format == "double" else side
        if self.phase != Phase.WAITING_REPLACEMENT \
                or token not in self.pending_replacements:
            raise BattleError(f"No replacement pending for {side}")
        if party_index not in self.bench(side):
            raise BattleError("Replacement must be an able, benched Pokemon")
        self._set_active(side, party_index, slot)
        bp = self.parties[side][party_index]
        bp._faint_announced = False
        bp.on_switch_out()  # fresh volatiles
        ev = [self._send_in_event(side, slot)]
        self._switch_in_effects(side, ev, slot)
        self.pending_replacements.discard(token)
        if self.format == "double":
            if self.phase != Phase.OVER and bp.fainted:
                # Re-derive pending from the board (handles a hazard KO on
                # switch-in and depleted benches without ending the battle).
                self._resolve_faints_doubles(ev)
            # Drop any pending slots whose side has nothing left to send.
            self.pending_replacements = {
                (s, sl) for (s, sl) in self.pending_replacements
                if self.bench(s)}
        elif self.phase != Phase.OVER and bp.fainted:
            if self.bench(side):
                self.pending_replacements.add(token)
                ev.append(Event(E.REPLACEMENT_NEEDED, side, {}))
            else:
                self._end_battle(other(side), ev)
        if not self.pending_replacements and self.phase != Phase.OVER:
            self.phase = Phase.WAITING_ACTIONS
        self.log.extend(ev)
        return ev

    # ── switch-in pipeline (hazards, then abilities) ─────────────────
    def _switch_in_effects(self, side: str, events, slot: int = 0) -> None:
        bp = self.parties[side][self.active_slots[side][slot]]
        ss = self.sides[side]
        if ss.stealth_rock and not bp.fainted and not passives.magic_guard(bp):
            eff = self.data.effectiveness("rock", bp.types)
            if eff > 0:
                dmg = max(1, int(bp.max_hp * eff) // 8)
                bp.take_damage(dmg)
                events.append(Event(E.HAZARD_DAMAGE, side,
                                    {"hazard": "stealth-rock", "pokemon": bp.name,
                                     "amount": dmg, "remaining_hp": bp.current_hp}))
                self.announce_faint(bp, events)
        grounded = (self.gravity_turns > 0
                    or ("flying" not in bp.types
                        and passives.abil(bp) != "levitate"
                        and bp.vol.magnet_rise_turns <= 0))
        if not bp.fainted and grounded and ss.spikes > 0 and not passives.magic_guard(bp):
            dmg = max(1, bp.max_hp // {1: 8, 2: 6}.get(ss.spikes, 4))
            bp.take_damage(dmg)
            events.append(Event(E.HAZARD_DAMAGE, side,
                                {"hazard": "spikes", "pokemon": bp.name,
                                 "amount": dmg, "remaining_hp": bp.current_hp}))
            self.announce_faint(bp, events)
        if not bp.fainted and grounded and ss.toxic_spikes > 0:
            if "poison" in bp.types:
                ss.toxic_spikes = 0
                events.append(Event(E.HAZARD_CLEARED, side,
                                    {"hazard": "toxic-spikes", "pokemon": bp.name}))
            else:
                movex.apply_status(self, bp,
                                   "poison" if ss.toxic_spikes == 1 else "toxic",
                                   events)
        if not bp.fainted and ss.healing_wish:
            ss.healing_wish = False
            bp.status = None
            bp.vol.toxic_counter = 0
            healed = bp.heal(bp.max_hp)
            if healed:
                events.append(Event(E.HEAL, side,
                                    {"pokemon": bp.name, "amount": healed,
                                     "remaining_hp": bp.current_hp,
                                     "healing_wish": True}))
        if not bp.fainted and ss.lunar_dance:
            ss.lunar_dance = False
            bp.status = None
            bp.vol.toxic_counter = 0
            healed = bp.heal(bp.max_hp)
            if healed:
                events.append(Event(E.HEAL, side,
                                    {"pokemon": bp.name, "amount": healed,
                                     "remaining_hp": bp.current_hp,
                                     "lunar_dance": True}))
            # Also restore all PP
            for slot in bp.state.moves:
                slot.pp = slot.pp_max
        if not bp.fainted:
            passives.switch_in(self, side, bp, events)

    # ── action execution ─────────────────────────────────────────────
    def _execute_action(self, side: str, action, events) -> None:
        if isinstance(action, MoveAction):
            self._do_move(side, action, events)
        elif isinstance(action, SwitchAction):
            self._do_switch(side, action.party_index, events)
        elif isinstance(action, ItemAction):
            self._do_item(side, action, events)
        elif isinstance(action, CatchAction):
            self._do_catch(side, action, events)
        elif isinstance(action, RunAction):
            self._do_run(side, events)
        else:
            raise BattleError(f"Unknown action: {action!r}")

    def _do_move(self, side: str, action: MoveAction, events,
                 targets=None) -> None:
        user = self.active(side)
        # `targets`: optional [(BattlePokemon, power_mult), ...] override used
        # by the doubles path. None -> singles default (the lone foe).
        target = targets[0][0] if targets else self.active(other(side))

        if user.vol.recharging:
            user.vol.recharging = False
            user.vol.has_moved = True
            events.append(Event(E.RECHARGING, side, {"pokemon": user.name}))
            return

        if targets is None and target.fainted:
            return  # nothing to hit; mainline skips the second move

        move = self._resolve_move(action)
        releasing = user.vol.charging is not None and user.vol.charging == move.id
        rampaging = user.vol.rampage_move == move.id

        if move.id not in ("struggle", "recharge"):
            slot = user.state.move_slot(move.id)
            if slot is None:
                raise BattleError(f"{user.name} does not know {move.id}")
            if slot.pp <= 0 and not (releasing or rampaging):
                if user.usable_moves():
                    raise BattleError(f"No PP left for {move.id}")
                move = movex.STRUGGLE

        if not self._can_act(side, user, move, events):
            user.vol.has_moved = True
            return

        if move.id not in ("protect", "detect"):
            user.vol.protect_count = 0

        # Two-turn charge initiation (Solar Beam fires instantly in sun)
        if move.id in movex.CHARGE_MOVES and not releasing \
                and not (move.id == "solar-beam" and self.weather == "sun"):
            user.state.move_slot(move.id).pp -= 1
            user.vol.charging = move.id
            user.vol.semi_invulnerable = movex.CHARGE_MOVES[move.id]
            user.vol.has_moved = True
            events.append(Event(E.CHARGING, side, {"pokemon": user.name,
                                                   "move": move.name}))
            if move.id == "skull-bash":
                applied = user.modify_stage("defense", 1)
                if applied:
                    events.append(Event(E.STAT_CHANGE, side,
                                        {"pokemon": user.name, "stat": "defense",
                                         "change": applied,
                                         "stage": user.stages["defense"]}))
            return

        if releasing:
            user.vol.charging = None
            user.vol.semi_invulnerable = None
        elif not rampaging and move.id not in ("struggle", "recharge"):
            user.state.move_slot(move.id).pp -= 1  # PP spent even on a miss

        if move.id in movex.RAMPAGE_MOVES:
            if user.vol.rampage_move != move.id:
                user.vol.rampage_move = move.id
                user.vol.rampage_turns = self.rng.randint(2, 3)
            user.vol.rampage_turns -= 1

        if passives.held(user) in passives.CHOICE_ITEMS \
                and move.id not in ("struggle", "recharge"):
            user.vol.choice_lock = move.id

        # Pressure: foe uses 2 PP per move (extra -1 PP)
        if move.id not in ("struggle", "recharge") and not releasing and not rampaging:
            foe_active = self.active(other(side))
            if passives.abil(foe_active) == "pressure":
                slot = user.state.move_slot(move.id)
                if slot is not None and slot.pp > 0:
                    slot.pp -= 1

        user.vol.has_moved = True
        if move.id not in ("struggle", "recharge"):
            user.vol.last_move = move.id
        # Analytic: set flag if the foe has already moved this turn
        foe_for_analytic = targets[0][0] if targets else self.active(other(side))
        user.vol.analytic_active = foe_for_analytic.vol.has_moved
        if targets is None:
            movex.execute_move(self, side, move, events)
        else:
            for t, pmult in targets:
                if t.fainted or user.fainted or self.over:
                    continue
                movex.execute_move(self, side, move, events,
                                   power_mult=pmult, target=t)

        # Rampage fatigue -> confusion
        if move.id in movex.RAMPAGE_MOVES and user.vol.rampage_move \
                and user.vol.rampage_turns <= 0:
            user.vol.rampage_move = None
            if not user.fainted and user.vol.confusion_turns <= 0 \
                    and not passives.confusion_blocked(user):
                user.vol.confusion_turns = self.rng.randint(2, 5)
                events.append(Event(E.CONFUSED, side, {"pokemon": user.name,
                                                       "start": True,
                                                       "fatigue": True}))

    def _can_act(self, side, user: BattlePokemon, move, events) -> bool:
        """Pre-move incapacity gauntlet: truant -> sleep/freeze -> flinch ->
        confusion -> paralysis."""
        # Truant: loaf every other turn
        if passives.abil(user) == "truant":
            if user.vol.truant_resting:
                user.vol.truant_resting = False
                events.append(Event(E.ABILITY, side,
                                    {"ability": "truant", "pokemon": user.name,
                                     "loafing": True}))
                return False
            else:
                user.vol.truant_resting = True
        if user.status == "sleep":
            # sleep_turns == failed turns remaining; -1 means re-entered
            # while asleep, so the counter re-rolls (Gen 5 behavior).
            if user.vol.sleep_turns < 0:
                base = self.rng.randint(1, 3)
                # Early Bird: halves sleep counter
                if passives.abil(user) == "early-bird":
                    base = max(1, base // 2)
                user.vol.sleep_turns = base
            if user.vol.sleep_turns > 0:
                user.vol.sleep_turns -= 1
                events.append(Event(E.ASLEEP, side, {"pokemon": user.name}))
                if move.id != "sleep-talk":
                    return False
                # Sleep Talk fires while asleep; fall through to execute
            else:
                user.status = None
                events.append(Event(E.WOKE_UP, side, {"pokemon": user.name}))
        elif user.status == "freeze":
            if "defrost" in move.flags or self.rng.random() < 0.20:
                user.status = None
                events.append(Event(E.THAWED, side, {"pokemon": user.name}))
            else:
                events.append(Event(E.FROZEN, side, {"pokemon": user.name}))
                return False

        if user.vol.flinched:
            events.append(Event(E.FLINCHED, side, {"pokemon": user.name}))
            # Steadfast: flinch causes +1 Speed
            if passives.abil(user) == "steadfast":
                applied = user.modify_stage("speed", 1)
                if applied:
                    events.append(Event(E.ABILITY, side,
                                        {"ability": "steadfast", "pokemon": user.name}))
                    events.append(Event(E.STAT_CHANGE, side,
                                        {"pokemon": user.name, "stat": "speed",
                                         "change": applied,
                                         "stage": user.stages["speed"]}))
            return False

        if user.vol.confusion_turns > 0:
            user.vol.confusion_turns -= 1
            if user.vol.confusion_turns == 0:
                events.append(Event(E.CONFUSION_ENDED, side, {"pokemon": user.name}))
            else:
                events.append(Event(E.CONFUSED, side, {"pokemon": user.name, "start": False}))
                if self.rng.random() < 0.5:  # Gen 5: 50% self-hit
                    from .damage import calc_damage
                    dmg, _ = calc_damage(self.data, user, user, movex.CONFUSION_HIT,
                                         rng=self.rng, crit=False)
                    user.take_damage(dmg)
                    events.append(Event(E.CONFUSION_SELF_HIT, side,
                                        {"pokemon": user.name, "amount": dmg,
                                         "remaining_hp": user.current_hp}))
                    self.announce_faint(user, events)
                    return False

        if user.vol.infatuated and self.rng.random() < 0.5:
            events.append(Event(E.CONFUSED, side, {"pokemon": user.name,
                                                   "start": False,
                                                   "infatuated": True}))
            return False

        if user.status == "paralysis" and self.rng.random() < 0.25:
            events.append(Event(E.FULLY_PARALYZED, side, {"pokemon": user.name}))
            return False
        return True

    def _do_switch(self, side: str, new_index: int, events) -> None:
        if new_index not in self.bench(side):
            raise BattleError(f"Illegal switch to index {new_index}")
        old = self.active(side)
        passives.on_switch_out(old, events, side)
        old.on_switch_out()
        events.append(Event(E.SWITCH_OUT, side, {"pokemon": old.name}))
        self._set_active(side, new_index)
        events.append(self._send_in_event(side))
        self._switch_in_effects(side, events)

    def _do_switch_slot(self, side: str, slot: int, new_index: int, events) -> None:
        if new_index not in self.bench(side):
            raise BattleError(f"Illegal switch to index {new_index}")
        old = self.parties[side][self.active_slots[side][slot]]
        passives.on_switch_out(old, events, side)
        old.on_switch_out()
        events.append(Event(E.SWITCH_OUT, side, {"pokemon": old.name}))
        self._set_active(side, new_index, slot)
        events.append(self._send_in_event(side, slot))
        self._switch_in_effects(side, events, slot)

    def _do_move_doubles(self, side: str, slot: int, action: MoveAction,
                         bp: BattlePokemon, events) -> None:
        # The slot's mon may have moved to a different position via earlier
        # switches; re-resolve its current slot index. If it's no longer
        # active (switched out / replaced), skip.
        try:
            cur_slot = self.active_slots[side].index(
                next(i for i in self.active_slots[side]
                     if self.parties[side][i] is bp))
        except StopIteration:
            return
        move = self._resolve_move(action)
        foe = other(side)
        live_foes = [b for b in self.actives(foe) if not b.fainted]
        if move.target == "all-other-pokemon":
            targets = [(b, 0.75) for b in live_foes]
            targets += [(b, 0.75) for b in self.actives(side)
                        if b is not bp and not b.fainted]
        elif move.targets_user or move.target in ("user", "users-field",
                                                   "user-and-allies",
                                                   "entire-field", "user-side"):
            targets = [(bp, 1.0)]
        elif move.target == "ally":
            ally = [b for b in self.actives(side) if b is not bp and not b.fainted]
            targets = [(ally[0], 1.0)] if ally else [(bp, 1.0)]
        else:
            # Single-target foe move: pick the requested foe slot, falling
            # back to any live foe.
            want = action.target_slot
            chosen = None
            if 0 <= want < len(self.active_slots[foe]):
                cand = self.parties[foe][self.active_slots[foe][want]]
                if not cand.fainted:
                    chosen = cand
            if chosen is None:
                chosen = live_foes[0] if live_foes else None
            if chosen is None:
                return  # no foe to hit
            targets = [(chosen, 1.0)]

        # Point slot 0 at this actor so the existing _do_move bookkeeping
        # (user = self.active(side), PP, choice lock, etc.) operates on it.
        saved0 = self.active_slots[side][0]
        saved_idx = self.active_idx[side]
        self.active_slots[side][0] = self.active_slots[side][cur_slot]
        self.active_idx[side] = self.active_slots[side][0]
        try:
            self._do_move(side, action, events, targets=targets)
        finally:
            self.active_slots[side][0] = saved0
            self.active_idx[side] = saved_idx

    def _do_item(self, side: str, action: ItemAction, events) -> None:
        item = self.data.item(action.item_id)
        if item is None:
            events.append(Event(E.ITEM_FAILED, side, {"item": action.item_id,
                                                      "reason": "unknown_item"}))
            return
        if item.is_ball:
            self._do_catch(side, CatchAction(item.id), events)
            return
        idx = action.target_index if action.target_index >= 0 else self.active_idx[side]
        target = self.parties[side][idx]
        if item.revive:
            # default to the first fainted party member when untargeted
            if not target.fainted:
                target = next((bp for bp in self.parties[side] if bp.fainted),
                              target)
            if not target.fainted:
                events.append(Event(E.ITEM_FAILED, side,
                                    {"item": item.name, "reason": "no_effect"}))
                return
            events.append(Event(E.ITEM_USED, side, {"item": item.name,
                                                    "pokemon": target.name}))
            target.state.current_hp = max(1, int(target.max_hp * item.revive))
            target.status = None
            target._faint_announced = False
            events.append(Event(E.HEAL, side, {"pokemon": target.name,
                                               "amount": target.current_hp,
                                               "remaining_hp": target.current_hp}))
            return
        events.append(Event(E.ITEM_USED, side, {"item": item.name,
                                                "pokemon": target.name}))
        did = False
        active = self.active(side)
        for stat, change in item.stages:
            applied = active.modify_stage(stat, change)
            if applied:
                events.append(Event(E.STAT_CHANGE, side,
                                    {"pokemon": active.name, "stat": stat,
                                     "change": applied,
                                     "stage": active.stages[stat]}))
                did = True
        if item.crit and active.vol.crit_bonus < item.crit:
            active.vol.crit_bonus = item.crit
            events.append(Event(E.STAT_CHANGE, side,
                                {"pokemon": active.name, "stat": "crit_rate",
                                 "change": item.crit, "stage": item.crit}))
            did = True
        if item.guard and self.sides[side].mist <= 0:
            self.sides[side].mist = 5
            events.append(Event(E.SCREEN_START, side, {"screen": "mist"}))
            did = True
        if item.heal and not target.fainted:
            amount = target.max_hp if item.heal == -1 else item.heal
            healed = target.heal(amount)
            if healed:
                events.append(Event(E.HEAL, side, {"pokemon": target.name,
                                                   "amount": healed,
                                                   "remaining_hp": target.current_hp}))
                did = True
        if item.cures and target.status and ("all" in item.cures or target.status in item.cures):
            cured = target.status
            target.status = None
            target.vol.toxic_counter = 0
            events.append(Event(E.STATUS_CURED, side, {"pokemon": target.name,
                                                       "status": cured}))
            did = True
        if not did:
            events.append(Event(E.ITEM_FAILED, side, {"item": item.name,
                                                      "reason": "no_effect"}))

    def _do_run(self, side: str, events) -> None:
        events.append(Event(E.RUN_ATTEMPT, side, {}))
        if not self.wild:
            events.append(Event(E.RUN_FAIL, side, {"reason": "trainer_battle"}))
            return
        self.run_attempts += 1
        a = self.active(side).stats["speed"]
        b = max(1, self.active(other(side)).stats["speed"])
        if a >= b:
            ok = True
        else:
            f = ((a * 128) // b + 30 * self.run_attempts) % 256
            ok = self.rng.randint(0, 255) < f
        if ok:
            events.append(Event(E.RUN_SUCCESS, side, {}))
            self._end_battle("escaped", events)
        else:
            events.append(Event(E.RUN_FAIL, side, {"attempts": self.run_attempts}))

    def _do_catch(self, side: str, action: CatchAction, events) -> None:
        item = self.data.item(action.ball_id)
        ball_rate = item.ball_rate if item else 1.0
        target = self.active(other(side))
        events.append(Event(E.CATCH_ATTEMPT, side, {"ball": action.ball_id,
                                                    "target": target.name}))
        if not self.wild:
            events.append(Event(E.CATCH_FAIL, side, {"reason": "trainer_battle"}))
            return
        m, h = target.max_hp, max(1, target.current_hp)
        status_bonus = {"sleep": 2.5, "freeze": 2.5, "paralysis": 1.5,
                        "burn": 1.5, "poison": 1.5, "toxic": 1.5}.get(target.status, 1.0)
        a = ((3 * m - 2 * h) * target.species.catch_rate * ball_rate) / (3 * m)
        a *= status_bonus
        # Gen 5 critical capture: likelier the more species you've caught.
        c_mult = (0.0 if self.dex_caught <= 30 else 0.5 if self.dex_caught <= 150
                  else 1.0 if self.dex_caught <= 300 else 1.5 if self.dex_caught <= 450
                  else 2.0 if self.dex_caught <= 600 else 2.5)
        critical = False
        if a >= 255:
            caught, shakes = True, 3
        else:
            b = int(65536 / ((255 / max(a, 1e-9)) ** 0.1875))
            crit_chance = min(255, int(a * c_mult) // 6)
            critical = self.rng.randint(0, 255) < crit_chance
            if critical:                       # one decisive shake, then resolve
                caught = self.rng.randint(0, 65535) < b
                shakes = 1
            else:
                shakes, caught = 0, True
                for _ in range(4):
                    if self.rng.randint(0, 65535) < b:
                        shakes += 1
                    else:
                        caught = False
                        break
        for s in range(min(shakes, 3)):
            events.append(Event(E.CATCH_SHAKE, side,
                                {"shake": s + 1, "critical": critical}))
        if caught:
            events.append(Event(E.CATCH_SUCCESS, side, {"pokemon": target.name}))
            self.caught_pokemon = target.state
            self._end_battle("caught", events)
        else:
            events.append(Event(E.CATCH_FAIL, side, {"shakes": shakes}))

    # ── end of turn ──────────────────────────────────────────────────
    def _end_of_turn(self, events) -> None:
        order = sorted(SIDES, key=self.speed_of, reverse=True)
        # 1. weather chip + expiry
        if self.weather in ("sandstorm", "hail"):
            for side in order:
                for bp in self.actives(side):
                    if bp.fainted:
                        continue
                    if self.weather == "sandstorm" and passives.sand_immune(bp):
                        continue
                    if self.weather == "hail" and "ice" in bp.types:
                        continue
                    if passives.magic_guard(bp):
                        continue
                    dmg = max(1, bp.max_hp // 16)
                    bp.take_damage(dmg)
                    events.append(Event(E.WEATHER_DAMAGE, side,
                                        {"weather": self.weather, "pokemon": bp.name,
                                         "amount": dmg, "remaining_hp": bp.current_hp}))
                    self.announce_faint(bp, events)
        if self.weather and self.weather_turns > 0:
            self.weather_turns -= 1
            if self.weather_turns == 0:
                events.append(Event(E.WEATHER_END, None, {"weather": self.weather}))
                self.weather = None
        # 1b. Wish healing
        for side in SIDES:
            ss = self.sides[side]
            if ss.wish_turns > 0:
                ss.wish_turns -= 1
                if ss.wish_turns == 0:
                    bp = self.active(side)
                    if not bp.fainted and bp.current_hp < bp.max_hp \
                            and bp.vol.heal_block_turns <= 0:
                        healed = bp.heal(ss.wish_hp)
                        if healed:
                            events.append(Event(E.HEAL, side,
                                                {"pokemon": bp.name, "amount": healed,
                                                 "remaining_hp": bp.current_hp,
                                                 "wish": True}))
        # 2. item/ability residuals (Leftovers, berries, Speed Boost)
        for side in order:
            for bp in self.actives(side):
                passives.end_of_turn(self, side, bp, events)
        # 2b. Ingrain heal
        for side in order:
            for bp in self.actives(side):
                if not bp.fainted and (bp.vol.ingrained or bp.vol.aqua_ring) \
                        and bp.current_hp < bp.max_hp:
                    healed = bp.heal(max(1, bp.max_hp // 16))
                    events.append(Event(E.HEAL, side,
                                        {"pokemon": bp.name, "amount": healed,
                                         "remaining_hp": bp.current_hp,
                                         "ingrain": True}))
        # 3. Leech Seed
        for side in order:
            for bp in self.actives(side):
                if bp.fainted or not bp.vol.leech_seeded:
                    continue
                if passives.magic_guard(bp):
                    continue
                foe = next((b for b in self.actives(other(side))
                            if not b.fainted), None)
                dmg = max(1, bp.max_hp // 8)
                dealt = bp.take_damage(dmg)
                events.append(Event(E.LEECH_DRAIN, side,
                                    {"pokemon": bp.name, "amount": dealt,
                                     "remaining_hp": bp.current_hp}))
                self.announce_faint(bp, events)
                if foe is not None and not foe.fainted and dealt:
                    healed = foe.heal(dealt)
                    if healed:
                        events.append(Event(E.HEAL, other(side),
                                            {"pokemon": foe.name, "amount": healed,
                                             "remaining_hp": foe.current_hp}))
        # 4. status damage
        for side in order:
            for bp in self.actives(side):
                if bp.fainted:
                    continue
                self._status_chip(side, bp, events)
        # 4b. Curse chip
        for side in order:
            for bp in self.actives(side):
                if bp.fainted or not bp.vol.cursed:
                    continue
                if passives.magic_guard(bp):
                    continue
                dmg = max(1, bp.max_hp // 4)
                bp.take_damage(dmg)
                events.append(Event(E.STATUS_DAMAGE, side,
                                    {"pokemon": bp.name, "status": "curse",
                                     "amount": dmg, "remaining_hp": bp.current_hp}))
                self.announce_faint(bp, events)
        # 5. partial trapping
        for side in order:
            for bp in self.actives(side):
                if bp.fainted or bp.vol.trap_turns <= 0:
                    continue
                if not passives.magic_guard(bp):
                    dmg = max(1, bp.max_hp // 16)
                    bp.take_damage(dmg)
                    events.append(Event(E.TRAP_DAMAGE, side,
                                        {"pokemon": bp.name, "move": bp.vol.trap_name,
                                         "amount": dmg, "remaining_hp": bp.current_hp}))
                    self.announce_faint(bp, events)
                bp.vol.trap_turns -= 1
                if bp.vol.trap_turns == 0:
                    events.append(Event(E.TRAP_END, side, {"pokemon": bp.name}))
        # 6. side-condition + volatile countdowns
        for side in SIDES:
            ss = self.sides[side]
            for attr in ("reflect", "light_screen", "safeguard", "mist",
                         "lucky_chant", "tailwind"):
                turns = getattr(ss, attr)
                if turns > 0:
                    setattr(ss, attr, turns - 1)
                    if turns - 1 == 0:
                        events.append(Event(E.SCREEN_END, side,
                                            {"screen": attr.replace("_", "-")}))
            for bp in self.actives(side):
                v = bp.vol
                if v.taunt_turns > 0:
                    v.taunt_turns -= 1
                if v.telekinesis_turns > 0:
                    v.telekinesis_turns -= 1
                if v.heal_block_turns > 0:
                    v.heal_block_turns -= 1
                if v.embargo_turns > 0:
                    v.embargo_turns -= 1
                if v.encore_turns > 0:
                    v.encore_turns -= 1
                    if v.encore_turns == 0:
                        v.encore_move = None
                if v.disable_turns > 0:
                    v.disable_turns -= 1
                    if v.disable_turns == 0:
                        v.disabled_move = None
        for k in self.sport:
            if self.sport[k] > 0:
                self.sport[k] -= 1
        # Whole-field condition countdowns
        for field_attr, screen_name in (
                ("trick_room", "trick-room"),
                ("gravity_turns", "gravity"),
                ("magic_room", "magic-room")):
            turns = getattr(self, field_attr)
            if turns > 0:
                setattr(self, field_attr, turns - 1)
                if turns - 1 == 0:
                    events.append(Event(E.SCREEN_END, None, {"screen": screen_name}))

    def _status_chip(self, side, bp, events) -> None:
        if bp.status in ("poison", "toxic") and passives.abil(bp) == "poison-heal":
            # Poison Heal: heal 1/8 max HP instead of taking damage
            healed = bp.heal(max(1, bp.max_hp // 8))
            if healed:
                events.append(Event(E.ABILITY, side,
                                    {"ability": "poison-heal", "pokemon": bp.name}))
                events.append(Event(E.HEAL, side,
                                    {"pokemon": bp.name, "amount": healed,
                                     "remaining_hp": bp.current_hp}))
            if bp.status == "toxic":
                bp.vol.toxic_counter += 1
            return
        if passives.magic_guard(bp):
            # Magic Guard: immune to indirect damage; skip status damage
            if bp.status == "toxic":
                bp.vol.toxic_counter += 1
            return
        if bp.status == "burn":
            dmg = max(1, bp.max_hp // 8)
        elif bp.status == "poison":
            dmg = max(1, bp.max_hp // 8)
        elif bp.status == "toxic":
            bp.vol.toxic_counter += 1
            dmg = max(1, bp.max_hp * min(bp.vol.toxic_counter, 15) // 16)
        else:
            return
        bp.take_damage(dmg)
        events.append(Event(E.STATUS_DAMAGE, side,
                            {"pokemon": bp.name, "status": bp.status,
                             "amount": dmg, "remaining_hp": bp.current_hp}))
        self.announce_faint(bp, events)

    def _resolve_faints(self, events) -> None:
        if self.phase == Phase.OVER:
            return
        if self.format == "double":
            self._resolve_faints_doubles(events)
            return
        needed = {s for s in SIDES if self.active(s).fainted}
        if not needed:
            return
        no_bench = {s for s in needed if not self.bench(s)}
        if no_bench == set(SIDES):
            self._end_battle("draw", events)
            return
        if P1 in no_bench:
            self._end_battle(P2, events)
            return
        if P2 in no_bench:
            self._end_battle(P1, events)
            return
        self.pending_replacements = needed
        self.phase = Phase.WAITING_REPLACEMENT
        for s in needed:
            events.append(Event(E.REPLACEMENT_NEEDED, s, {}))

    def _able_count(self, side: str) -> int:
        return sum(1 for bp in self.parties[side] if not bp.fainted)

    def _resolve_faints_doubles(self, events) -> None:
        # A side loses only when it has no able Pokemon at all (active or
        # benched). Otherwise, every empty active slot that can be refilled
        # becomes a pending replacement.
        wiped = {s for s in SIDES if self._able_count(s) == 0}
        if wiped == set(SIDES):
            self._end_battle("draw", events)
            return
        if P1 in wiped:
            self._end_battle(P2, events)
            return
        if P2 in wiped:
            self._end_battle(P1, events)
            return
        pending = set()
        for s in SIDES:
            for slot, idx in enumerate(self.active_slots[s]):
                if self.parties[s][idx].fainted and self.bench(s):
                    pending.add((s, slot))
        if not pending:
            return
        self.pending_replacements = pending
        self.phase = Phase.WAITING_REPLACEMENT
        for s, _slot in sorted(pending):
            events.append(Event(E.REPLACEMENT_NEEDED, s, {}))

    def _end_battle(self, winner: str, events) -> None:
        self.phase = Phase.OVER
        self.winner = winner
        # Gen 5: badly poisoned reverts to regular poison after battle.
        for side in SIDES:
            for bp in self.parties[side]:
                if bp.status == "toxic":
                    bp.status = "poison"
        events.append(Event(E.BATTLE_END, None, {"winner": winner}))

    @property
    def over(self) -> bool:
        return self.phase == Phase.OVER
