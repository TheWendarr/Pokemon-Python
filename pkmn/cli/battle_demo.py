"""Terminal battle demo.

Proof that the engine runs end-to-end with no UI dependency.

    pkmn-demo --data game/data --auto --seed 42      # AI vs AI spectate
    pkmn-demo --data game/data                       # you vs greedy AI

`format_event` is the canonical event -> message-log translator; the
pygame renderer in Phase 3 reuses it for its text box.
"""
from __future__ import annotations

import argparse
import random
import sys

from ..battle.ai import GreedyAI, RandomAI
from ..battle.engine import BattleEngine, Phase
from ..battle.events import E, Event
from ..battle.state import MoveAction, P1, P2, SwitchAction
from ..core.pokemon import PokemonState
from ..data.repository import GameData

WHO = {P1: "", P2: "Foe "}


def format_event(ev: Event) -> str | None:
    d, s = ev.data, WHO.get(ev.side, "")
    t = ev.type
    if t == E.BATTLE_START:
        return "A wild battle begins!" if d.get("wild") else "Battle start!"
    if t == E.TURN_START:
        return f"\n-- Turn {d['turn']} --"
    if t == E.SEND_IN:
        return f"{s}{d['pokemon']} (Lv.{d['level']}) was sent in! [{d['hp']}/{d['max_hp']} HP]"
    if t == E.SWITCH_OUT:
        return f"{s}{d['pokemon']} was withdrawn!"
    if t == E.MOVE_USED:
        return f"{s}{d['pokemon']} used {d['move']}!"
    if t == E.MOVE_MISSED:
        return "But it missed!"
    if t == E.MOVE_FAILED:
        return "But it failed!"
    if t == E.MOVE_IMMUNE:
        return f"It doesn't affect {s}{d['pokemon']}..."
    if t == E.DAMAGE:
        extra = ""
        if d.get("crit"):
            extra += " A critical hit!"
        eff = d.get("effectiveness", 1.0)
        if eff > 1:
            extra += " It's super effective!"
        elif 0 < eff < 1:
            extra += " It's not very effective..."
        return (f"{s}{d['pokemon']} took {d['amount']} damage."
                f" [{d['remaining_hp']}/{d['max_hp']} HP]{extra}")
    if t == E.MULTI_HIT:
        return f"Hit {d['hits']} time(s)!"
    if t == E.HEAL:
        return f"{s}{d['pokemon']} recovered {d['amount']} HP! [{d['remaining_hp']} HP]"
    if t == E.DRAIN:
        return f"{s}{d['pokemon']} drained {d['amount']} HP!"
    if t == E.RECOIL:
        return f"{s}{d['pokemon']} is hit with recoil ({d['amount']})!"
    if t == E.STATUS_APPLIED:
        names = {"burn": "was burned", "poison": "was poisoned",
                 "toxic": "was badly poisoned", "paralysis": "is paralyzed",
                 "sleep": "fell asleep", "freeze": "was frozen solid"}
        return f"{s}{d['pokemon']} {names.get(d['status'], d['status'])}!"
    if t == E.STATUS_CURED:
        return f"{s}{d['pokemon']}'s {d['status']} was cured!"
    if t == E.STATUS_DAMAGE:
        return f"{s}{d['pokemon']} is hurt by its {d['status']}! ({d['amount']})"
    if t == E.STAT_CHANGE:
        direction = "rose" if d["change"] > 0 else "fell"
        mag = {1: "", 2: " sharply", -1: "", -2: " harshly"}.get(d["change"], "")
        return f"{s}{d['pokemon']}'s {d['stat'].replace('_', ' ')} {direction}{mag}!"
    if t == E.STAT_CHANGE_FAILED:
        return (f"{s}{d['pokemon']}'s {d['stat'].replace('_', ' ')} won't go any "
                f"{'higher' if d['direction'] == 'raise' else 'lower'}!")
    if t == E.FULLY_PARALYZED:
        return f"{s}{d['pokemon']} is fully paralyzed!"
    if t == E.ASLEEP:
        return f"{s}{d['pokemon']} is fast asleep."
    if t == E.WOKE_UP:
        return f"{s}{d['pokemon']} woke up!"
    if t == E.FROZEN:
        return f"{s}{d['pokemon']} is frozen solid!"
    if t == E.THAWED:
        return f"{s}{d['pokemon']} thawed out!"
    if t == E.FLINCHED:
        return f"{s}{d['pokemon']} flinched and couldn't move!"
    if t == E.CONFUSED:
        return (f"{s}{d['pokemon']} became confused!" if d.get("start")
                else f"{s}{d['pokemon']} is confused!")
    if t == E.CONFUSION_SELF_HIT:
        return f"It hurt itself in its confusion! ({d['amount']})"
    if t == E.CONFUSION_ENDED:
        return f"{s}{d['pokemon']} snapped out of confusion!"
    if t == E.FAINT:
        return f"{s}{d['pokemon']} fainted!"
    if t == E.ITEM_USED:
        return f"{s}Used {d['item']} on {d['pokemon']}."
    if t == E.ITEM_FAILED:
        return "It won't have any effect."
    if t == E.RUN_ATTEMPT:
        return "Trying to run away..."
    if t == E.RUN_SUCCESS:
        return "Got away safely!"
    if t == E.RUN_FAIL:
        return "Can't escape!"
    if t == E.CATCH_ATTEMPT:
        return f"Threw a {d['ball'].replace('-', ' ').title()} at {d['target']}!"
    if t == E.CATCH_SHAKE:
        return "*shake*"
    if t == E.CATCH_SUCCESS:
        return f"Gotcha! {d['pokemon']} was caught!"
    if t == E.CATCH_FAIL:
        return "Oh no! It broke free!"
    if t == E.BATTLE_END:
        return f"\n=== Battle over: {d['winner']} ==="
    if t == E.WEATHER_START:
        return {"rain": "It started to rain!", "sun": "The sunlight turned harsh!",
                "sandstorm": "A sandstorm kicked up!",
                "hail": "It started to hail!"}[d["weather"]]
    if t == E.WEATHER_DAMAGE:
        w = "the sandstorm" if d["weather"] == "sandstorm" else "the hail"
        return f"{s}{d['pokemon']} is buffeted by {w}! ({d['amount']})"
    if t == E.WEATHER_END:
        return {"rain": "The rain stopped.", "sun": "The sunlight faded.",
                "sandstorm": "The sandstorm subsided.",
                "hail": "The hail stopped."}[d["weather"]]
    if t == E.HAZARD_SET:
        nice = d["hazard"].replace("-", " ")
        return f"{nice.title()} scattered around {WHO.get(ev.side, 'the')} side!"
    if t == E.HAZARD_DAMAGE:
        return (f"{s}{d['pokemon']} is hurt by {d['hazard'].replace('-', ' ')}!"
                f" ({d['amount']})")
    if t == E.HAZARD_CLEARED:
        return f"The {d['hazard'].replace('-', ' ')} disappeared!"
    if t == E.SCREEN_START:
        return ("Reflect raised physical defense!" if d["screen"] == "reflect"
                else "Light Screen raised special defense!")
    if t == E.SCREEN_END:
        return f"The {d['screen'].replace('-', ' ').title()} wore off!"
    if t == E.PROTECTED:
        return (f"{s}{d['pokemon']} protected itself!" if d.get("setup")
                else f"{s}{d['pokemon']} protected itself from the attack!")
    if t == E.CHARGING:
        return f"{s}{d['pokemon']} is charging {d['move']}!"
    if t == E.RECHARGING:
        return f"{s}{d['pokemon']} must recharge!"
    if t == E.DRAGGED:
        return f"{s}{d['pokemon']} was dragged out!"
    if t == E.LEECH_SEED:
        return f"{s}{d['pokemon']} was seeded!"
    if t == E.LEECH_DRAIN:
        return f"{s}{d['pokemon']}'s health is sapped by Leech Seed! ({d['amount']})"
    if t == E.TRAPPED:
        return f"{s}{d['pokemon']} was trapped by {d['move']}!"
    if t == E.TRAP_DAMAGE:
        return f"{s}{d['pokemon']} is hurt by {d['move']}! ({d['amount']})"
    if t == E.TRAP_END:
        return f"{s}{d['pokemon']} was freed!"
    if t == E.STAGES_RESET:
        return "All stat changes were eliminated!"
    if t == E.ABILITY:
        extra = " It endured the hit!" if d.get("endure") else ""
        return f"[{s}{d['pokemon']}'s {d['ability'].replace('-', ' ').title()}]{extra}"
    if t == E.ITEM_HELD:
        extra = " It hung on!" if d.get("endure") else ""
        return f"[{s}{d['pokemon']}'s {d['item'].replace('-', ' ').title()}]{extra}"
    if t == E.EFFECT_SKIPPED:
        return f"({d['move']}: effect '{d['effect']}' not implemented yet)"
    return None


def print_events(events) -> None:
    for ev in events:
        line = format_event(ev)
        if line:
            print(line)


def random_party(data: GameData, n: int, level: int, rng: random.Random):
    ids = [s for s in data.all_species_ids()]
    party = []
    while len(party) < n:
        sid = rng.choice(ids)
        try:
            p = PokemonState.generate(data, sid, level, rng=rng)
        except Exception:
            continue
        if p.moves:
            party.append(p)
    return party


def auto_battle(data: GameData, seed: int | None, size: int, level: int) -> None:
    rng = random.Random(seed)
    eng = BattleEngine(data, random_party(data, size, level, rng),
                       random_party(data, size, level, rng),
                       rng=random.Random(rng.random()))
    ais = {P1: GreedyAI(P1, random.Random(rng.random())),
           P2: GreedyAI(P2, random.Random(rng.random()))}
    print_events(eng._start_events)
    while not eng.over and eng.turn < 200:
        if eng.phase == Phase.WAITING_REPLACEMENT:
            for side in list(eng.pending_replacements):
                print_events(eng.submit_replacement(side, ais[side].choose_replacement(eng)))
            continue
        print_events(eng.submit_turn(ais[P1].choose_action(eng),
                                     ais[P2].choose_action(eng)))


def interactive_battle(data: GameData, seed: int | None, size: int, level: int) -> None:
    rng = random.Random(seed)
    eng = BattleEngine(data, random_party(data, size, level, rng),
                       random_party(data, size, level, rng),
                       rng=random.Random(rng.random()))
    foe = GreedyAI(P2, random.Random(rng.random()))
    print_events(eng._start_events)
    while not eng.over:
        if eng.phase == Phase.WAITING_REPLACEMENT:
            if P2 in eng.pending_replacements:
                print_events(eng.submit_replacement(P2, foe.choose_replacement(eng)))
            if P1 in eng.pending_replacements:
                idx = _pick_replacement(eng)
                print_events(eng.submit_replacement(P1, idx))
            continue
        action = _pick_action(eng)
        print_events(eng.submit_turn(action, foe.choose_action(eng)))


def _pick_action(eng: BattleEngine):
    me = eng.active(P1)
    print(f"\nYour {me.name}: {me.current_hp}/{me.max_hp} HP"
          + (f" [{me.status}]" if me.status else ""))
    options = eng.legal_actions(P1)
    for i, a in enumerate(options):
        if isinstance(a, MoveAction):
            slot = me.state.move_slot(a.move_id)
            pp = f"{slot.pp}/{slot.pp_max}" if slot else "--"
            print(f"  {i}: {a.move_id} (PP {pp})")
        elif isinstance(a, SwitchAction):
            bp = eng.parties[P1][a.party_index]
            print(f"  {i}: switch -> {bp.name} ({bp.current_hp}/{bp.max_hp})")
        else:
            print(f"  {i}: {type(a).__name__}")
    while True:
        raw = input("> ").strip()
        if raw.isdigit() and int(raw) < len(options):
            return options[int(raw)]
        print("Pick a number from the list.")


def _pick_replacement(eng: BattleEngine) -> int:
    print("\nChoose your next Pokemon:")
    for i in eng.bench(P1):
        bp = eng.parties[P1][i]
        print(f"  {i}: {bp.name} ({bp.current_hp}/{bp.max_hp})")
    while True:
        raw = input("> ").strip()
        if raw.isdigit() and int(raw) in eng.bench(P1):
            return int(raw)
        print("Pick a listed index.")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Run a demo battle in the terminal")
    ap.add_argument("--data", default="game/data", help="game data directory")
    ap.add_argument("--auto", action="store_true", help="AI vs AI spectate mode")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--size", type=int, default=3, help="party size")
    ap.add_argument("--level", type=int, default=50)
    args = ap.parse_args(argv)
    try:
        data = GameData(args.data)
    except Exception as e:
        print(f"Could not load game data: {e}\n"
              f"Run `pkmn-fetch-data --out {args.data}` first.", file=sys.stderr)
        return 1
    if args.auto:
        auto_battle(data, args.seed, args.size, args.level)
    else:
        interactive_battle(data, args.seed, args.size, args.level)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
