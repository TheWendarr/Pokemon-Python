"""BattleEngine: a pure, deterministic Gen 5-style battle resolver.

Properties that matter:
  * No disk I/O, no printing. Inputs are Actions; outputs are Events.
  * All randomness flows through one injected random.Random, so battles
    are seedable and tests are deterministic.
  * Phase machine: WAITING_ACTIONS -> (maybe WAITING_REPLACEMENT) ->
    ... -> OVER. The caller (CLI, pygame controller, AI harness) drives
    it; the engine never blocks on input.

Phase 1 scope (see docs/ROADMAP.md): full damage model, statuses,
stages, priority/speed ordering, PP & Struggle, switching, items,
fleeing and catching in wild battles. Abilities, held items, weather,
and entry hazards are Phase 2 -- hook points are noted inline.
"""
from __future__ import annotations

import random
from enum import Enum
from typing import Optional

from ..core.pokemon import PokemonState
from ..core.stats import crit_chance
from ..data.repository import GameData
from . import moves as movex
from .events import E, Event
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
                 wild: bool = False, rng: Optional[random.Random] = None):
        if not party1 or not party2:
            raise BattleError("Both sides need at least one Pokemon")
        self.data = data
        self.rng = rng or random.Random()
        self.wild = wild
        self.parties = {P1: [BattlePokemon(data, s) for s in party1],
                        P2: [BattlePokemon(data, s) for s in party2]}
        self.active_idx = {P1: self._first_able(P1), P2: self._first_able(P2)}
        if self.active_idx[P1] is None or self.active_idx[P2] is None:
            raise BattleError("Both sides need at least one able Pokemon")
        self.phase = Phase.WAITING_ACTIONS
        self.pending_replacements: set = set()
        self.winner: Optional[str] = None   # 'p1' | 'p2' | 'draw' | 'escaped' | 'caught'
        self.turn = 0
        self.run_attempts = 0
        self.caught_pokemon: Optional[PokemonState] = None
        self.log: list[Event] = []
        ev = [Event(E.BATTLE_START, None, {"wild": wild})]
        for side in SIDES:
            ev.append(self._send_in_event(side))
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

    def side_of(self, bp: BattlePokemon) -> str:
        for side in SIDES:
            if self.active(side) is bp:
                return side
        for side in SIDES:
            if bp in self.parties[side]:
                return side
        return "?"

    def _send_in_event(self, side: str) -> Event:
        bp = self.active(side)
        return Event(E.SEND_IN, side, {"pokemon": bp.name, "level": bp.level,
                                       "hp": bp.current_hp, "max_hp": bp.max_hp,
                                       "party_index": self.active_idx[side]})

    def crit_chance_for(self, user: BattlePokemon, move) -> float:
        # Phase 2 hook: Super Luck, Scope Lens, Focus Energy add stages.
        return crit_chance(move.crit_stage)

    def announce_faint(self, bp: BattlePokemon, events) -> None:
        if bp.fainted and not getattr(bp, "_faint_announced", False):
            bp._faint_announced = True
            events.append(Event(E.FAINT, self.side_of(bp), {"pokemon": bp.name}))

    def bench(self, side: str) -> list[int]:
        """Indices of able, benched Pokemon."""
        return [i for i, bp in enumerate(self.parties[side])
                if i != self.active_idx[side] and not bp.fainted]

    def legal_actions(self, side: str) -> list:
        """Moves (or Struggle), switches, and Run in wild battles. Items
        are owned by the caller's inventory and validated on submit."""
        if self.phase != Phase.WAITING_ACTIONS:
            return []
        bp = self.active(side)
        usable = bp.usable_moves()
        actions: list = ([MoveAction(s.move_id) for s in usable]
                         if usable else [MoveAction("struggle")])
        actions += [SwitchAction(i) for i in self.bench(side)]
        if self.wild and side == P1:
            actions.append(RunAction())
        return actions

    # ── action ordering ──────────────────────────────────────────────
    def _category_priority(self, action) -> int:
        if isinstance(action, RunAction):
            return 8
        if isinstance(action, (ItemAction, CatchAction)):
            return 7
        if isinstance(action, SwitchAction):
            return 6
        move = self._resolve_move(self.active_idx, action)
        return move.priority

    def _resolve_move(self, _idx, action: MoveAction):
        if action.move_id == "struggle":
            return movex.STRUGGLE
        return self.data.move(action.move_id)

    # ── public API ───────────────────────────────────────────────────
    def submit_turn(self, p1_action, p2_action) -> list[Event]:
        if self.phase != Phase.WAITING_ACTIONS:
            raise BattleError(f"Cannot submit actions in phase {self.phase}")
        self.turn += 1
        events: list[Event] = [Event(E.TURN_START, None, {"turn": self.turn})]
        for side in SIDES:
            self.active(side).vol.has_moved = False
            self.active(side).vol.flinched = False

        pairs = [(P1, p1_action), (P2, p2_action)]
        pairs.sort(key=lambda pa: (self._category_priority(pa[1]),
                                   self.active(pa[0]).effective_speed(),
                                   self.rng.random()),
                   reverse=True)

        for side, action in pairs:
            if self.phase == Phase.OVER:
                break
            actor = self.active(side)
            if actor.fainted:
                continue  # fainted before acting; replacement happens at end of turn
            self._execute_action(side, action, events)

        if self.phase != Phase.OVER:
            self._end_of_turn(events)
        self._resolve_faints(events)
        self.log.extend(events)
        return events

    def submit_replacement(self, side: str, party_index: int) -> list[Event]:
        if self.phase != Phase.WAITING_REPLACEMENT or side not in self.pending_replacements:
            raise BattleError(f"No replacement pending for {side}")
        if party_index not in self.bench(side):
            raise BattleError("Replacement must be an able, benched Pokemon")
        self.active_idx[side] = party_index
        self.active(side)._faint_announced = False
        self.active(side).on_switch_out()  # fresh volatiles
        ev = [self._send_in_event(side)]
        self.pending_replacements.discard(side)
        if not self.pending_replacements:
            self.phase = Phase.WAITING_ACTIONS
        self.log.extend(ev)
        return ev

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

    def _do_move(self, side: str, action: MoveAction, events) -> None:
        user = self.active(side)
        target = self.active(other(side))
        if target.fainted:
            return  # nothing to hit; mainline skips the second move

        move = self._resolve_move(None, action)
        if move.id != "struggle":
            slot = user.state.move_slot(move.id)
            if slot is None:
                raise BattleError(f"{user.name} does not know {move.id}")
            if slot.pp <= 0:
                if user.usable_moves():
                    raise BattleError(f"No PP left for {move.id}")
                move = movex.STRUGGLE

        if not self._can_act(side, user, move, events):
            user.vol.has_moved = True
            return

        if move.id != "struggle":
            user.state.move_slot(move.id).pp -= 1  # PP spent even on a miss

        user.vol.has_moved = True
        movex.execute_move(self, side, move, events)

    def _can_act(self, side, user: BattlePokemon, move, events) -> bool:
        """Pre-move incapacity gauntlet: sleep/freeze -> flinch ->
        confusion -> paralysis."""
        if user.status == "sleep":
            # sleep_turns == failed turns remaining; -1 means re-entered
            # while asleep, so the counter re-rolls (Gen 5 behavior).
            if user.vol.sleep_turns < 0:
                user.vol.sleep_turns = self.rng.randint(1, 3)
            if user.vol.sleep_turns > 0:
                user.vol.sleep_turns -= 1
                events.append(Event(E.ASLEEP, side, {"pokemon": user.name}))
                return False
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

        if user.status == "paralysis" and self.rng.random() < 0.25:
            events.append(Event(E.FULLY_PARALYZED, side, {"pokemon": user.name}))
            return False
        return True

    def _do_switch(self, side: str, new_index: int, events) -> None:
        if new_index not in self.bench(side):
            raise BattleError(f"Illegal switch to index {new_index}")
        old = self.active(side)
        old.on_switch_out()
        events.append(Event(E.SWITCH_OUT, side, {"pokemon": old.name}))
        self.active_idx[side] = new_index
        events.append(self._send_in_event(side))

    def _do_item(self, side: str, action: ItemAction, events) -> None:
        item = self.data.item(action.item_id)
        if item is None:
            events.append(Event(E.ITEM_FAILED, side, {"item": action.item_id,
                                                      "reason": "unknown_item"}))
            return
        if item.category == "ball":
            self._do_catch(side, CatchAction(item.id), events)
            return
        idx = action.target_index if action.target_index >= 0 else self.active_idx[side]
        target = self.parties[side][idx]
        events.append(Event(E.ITEM_USED, side, {"item": item.name,
                                                "pokemon": target.name}))
        did = False
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
        # Gen 5 capture math.
        m, h = target.max_hp, max(1, target.current_hp)
        status_bonus = {"sleep": 2.5, "freeze": 2.5, "paralysis": 1.5,
                        "burn": 1.5, "poison": 1.5, "toxic": 1.5}.get(target.status, 1.0)
        a = ((3 * m - 2 * h) * target.species.catch_rate * ball_rate) / (3 * m)
        a *= status_bonus
        if a >= 255:
            caught = True
            shakes = 3
        else:
            b = int(65536 / ((255 / max(a, 1e-9)) ** 0.1875))
            shakes = 0
            caught = True
            for _ in range(4):
                if self.rng.randint(0, 65535) < b:
                    shakes += 1
                else:
                    caught = False
                    break
        for s in range(min(shakes, 3)):
            events.append(Event(E.CATCH_SHAKE, side, {"shake": s + 1}))
        if caught:
            events.append(Event(E.CATCH_SUCCESS, side, {"pokemon": target.name}))
            self.caught_pokemon = target.state
            self._end_battle("caught", events)
        else:
            events.append(Event(E.CATCH_FAIL, side, {"shakes": shakes}))

    # ── end of turn ──────────────────────────────────────────────────
    def _end_of_turn(self, events) -> None:
        order = sorted(SIDES, key=lambda s: self.active(s).effective_speed(),
                       reverse=True)
        for side in order:
            bp = self.active(side)
            if bp.fainted:
                continue
            if bp.status == "burn":
                dmg = max(1, bp.max_hp // 8)
            elif bp.status == "poison":
                dmg = max(1, bp.max_hp // 8)
            elif bp.status == "toxic":
                bp.vol.toxic_counter += 1
                dmg = max(1, bp.max_hp * min(bp.vol.toxic_counter, 15) // 16)
            else:
                continue
            bp.take_damage(dmg)
            events.append(Event(E.STATUS_DAMAGE, side,
                                {"pokemon": bp.name, "status": bp.status,
                                 "amount": dmg, "remaining_hp": bp.current_hp}))
            self.announce_faint(bp, events)
        # Phase 2 hooks: weather, Leftovers, entry-hazard bookkeeping.

    def _resolve_faints(self, events) -> None:
        if self.phase == Phase.OVER:
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
