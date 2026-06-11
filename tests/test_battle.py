"""Battle engine behavior tests."""
import pytest

from pkmn.battle.engine import BattleEngine, Phase
from pkmn.battle.events import E
from pkmn.battle.state import (CatchAction, ItemAction, MoveAction, P1, P2,
                               RunAction, SwitchAction)


def types_of(events):
    return [e.type for e in events]


def first(events, etype, side=None):
    for e in events:
        if e.type == etype and (side is None or e.side == side):
            return e
    return None


# ── ordering ─────────────────────────────────────────────────────────

def test_faster_pokemon_moves_first(data, make_mon, nochance):
    eng = BattleEngine(data, [make_mon("pikachu")], [make_mon("geodude")],
                       rng=nochance)
    ev = eng.submit_turn(MoveAction("tackle"), MoveAction("tackle"))
    moves = [e for e in ev if e.type == E.MOVE_USED]
    assert [m.side for m in moves] == [P1, P2]  # pikachu (90) before geodude (20)


def test_priority_beats_speed(data, make_mon, nochance):
    slow = make_mon("geodude", moves=["tackle"])
    fast = make_mon("pikachu", moves=["tackle"])
    eng = BattleEngine(data, [slow], [fast], rng=nochance)
    # Give geodude quick-attack manually for a clean priority test
    eng2 = BattleEngine(data, [make_mon("geodude", moves=["quick-attack"])],
                        [make_mon("pikachu", moves=["tackle"])], rng=nochance)
    ev = eng2.submit_turn(MoveAction("quick-attack"), MoveAction("tackle"))
    moves = [e for e in ev if e.type == E.MOVE_USED]
    assert moves[0].side == P1


def test_paralysis_quarters_speed(data, make_mon, nochance):
    eng = BattleEngine(data, [make_mon("pikachu")], [make_mon("charmander")],
                       rng=nochance)
    pika = eng.active(P1)
    base = pika.effective_speed()
    pika.status = "paralysis"
    assert pika.effective_speed() == base // 4


def test_switch_resolves_before_moves(data, make_mon, nochance):
    eng = BattleEngine(data, [make_mon("geodude"), make_mon("squirtle")],
                       [make_mon("pikachu")], rng=nochance)
    ev = eng.submit_turn(SwitchAction(1), MoveAction("tackle"))
    t = types_of(ev)
    assert t.index(E.SWITCH_OUT) < t.index(E.MOVE_USED)
    # tackle hits the incoming squirtle
    dmg = first(ev, E.DAMAGE)
    assert dmg.data["pokemon"] == "Squirtle"


# ── statuses ─────────────────────────────────────────────────────────

def test_thunderbolt_secondary_paralysis(data, make_mon, maxroll):
    eng = BattleEngine(data, [make_mon("pikachu")], [make_mon("squirtle")],
                       rng=maxroll)  # all chance rolls succeed
    ev = eng.submit_turn(MoveAction("thunderbolt"), MoveAction("recover"))
    assert first(ev, E.STATUS_APPLIED, P2).data["status"] == "paralysis"
    assert eng.active(P2).status == "paralysis"


def test_thunder_wave_blocked_by_ground(data, make_mon, maxroll):
    eng = BattleEngine(data, [make_mon("pikachu")], [make_mon("geodude")],
                       rng=maxroll)
    ev = eng.submit_turn(MoveAction("thunder-wave"), MoveAction("rest"))
    assert first(ev, E.MOVE_IMMUNE) is not None
    assert eng.active(P2).status != "paralysis"


def test_burn_immunity_for_fire_types(data, make_mon, maxroll):
    eng = BattleEngine(data, [make_mon("charmander")], [make_mon("charmander")],
                       rng=maxroll)
    ev = eng.submit_turn(MoveAction("will-o-wisp"), MoveAction("growl"))
    assert first(ev, E.STATUS_APPLIED) is None
    assert first(ev, E.MOVE_FAILED) is not None


def test_poison_immunity_for_poison_types(data, make_mon, maxroll):
    eng = BattleEngine(data, [make_mon("bulbasaur")], [make_mon("gengar")],
                       rng=maxroll)
    ev = eng.submit_turn(MoveAction("toxic"), MoveAction("giga-drain"))
    assert eng.active(P2).status is None


def test_toxic_damage_ramps(data, make_mon, nochance):
    eng = BattleEngine(data, [make_mon("bulbasaur")],
                       [make_mon("squirtle", level=100)], rng=nochance)
    eng.active(P2).status = "toxic"
    hp_max = eng.active(P2).max_hp
    ev1 = eng.submit_turn(MoveAction("growl"), MoveAction("recover"))
    ev2 = eng.submit_turn(MoveAction("growl"), MoveAction("recover"))
    d1 = first(ev1, E.STATUS_DAMAGE).data["amount"]
    d2 = first(ev2, E.STATUS_DAMAGE).data["amount"]
    assert d1 == hp_max // 16
    assert d2 == hp_max * 2 // 16


def test_sleep_blocks_then_wakes(data, make_mon, maxroll):
    eng = BattleEngine(data, [make_mon("gengar")],
                       [make_mon("squirtle", level=100)], rng=maxroll)
    ev = eng.submit_turn(MoveAction("hypnosis"), MoveAction("tackle"))
    # gengar (110 speed) puts squirtle to sleep before it moves
    assert first(ev, E.STATUS_APPLIED, P2).data["status"] == "sleep"
    assert first(ev, E.MOVE_USED, P2) is None
    # MaxRoll sleep counter = 3 failed turns; turn 1 already consumed one
    for _ in range(2):
        ev = eng.submit_turn(MoveAction("confuse-ray"), MoveAction("tackle"))
        assert first(ev, E.ASLEEP, P2) is not None
        assert first(ev, E.MOVE_USED, P2) is None
    ev = eng.submit_turn(MoveAction("giga-drain"), MoveAction("tackle"))
    assert first(ev, E.WOKE_UP, P2) is not None
    assert first(ev, E.MOVE_USED, P2) is not None


def test_rest_full_heals_and_sleeps_two_turns(data, make_mon, nochance):
    eng = BattleEngine(data, [make_mon("geodude", level=100)],
                       [make_mon("bulbasaur")], rng=nochance)
    geo = eng.active(P1)
    geo.take_damage(60)
    geo.status = "poison"
    ev = eng.submit_turn(MoveAction("rest"), MoveAction("growl"))
    assert geo.current_hp == geo.max_hp
    assert geo.status == "sleep"
    for _ in range(2):
        ev = eng.submit_turn(MoveAction("tackle"), MoveAction("growl"))
        assert first(ev, E.ASLEEP, P1) is not None
    ev = eng.submit_turn(MoveAction("tackle"), MoveAction("growl"))
    assert first(ev, E.WOKE_UP, P1) is not None
    assert first(ev, E.MOVE_USED, P1) is not None


def test_confusion_applied_as_volatile(data, make_mon, maxroll):
    eng = BattleEngine(data, [make_mon("gengar")], [make_mon("squirtle")],
                       rng=maxroll)
    eng.submit_turn(MoveAction("confuse-ray"), MoveAction("recover"))
    assert eng.active(P2).vol.confusion_turns > 0
    assert eng.active(P2).status is None


def test_flinch_blocks_slower_target(data, make_mon, maxroll):
    eng = BattleEngine(data,
                       [make_mon("pikachu", moves=["headbutt"])],
                       [make_mon("geodude", moves=["tackle"])], rng=maxroll)
    ev = eng.submit_turn(MoveAction("headbutt"), MoveAction("tackle"))
    assert first(ev, E.FLINCHED, P2) is not None
    assert first(ev, E.MOVE_USED, P2) is None


# ── damaging move bookkeeping ────────────────────────────────────────

def test_pp_spent_even_on_miss_and_struggle_when_empty(data, make_mon, nochance):
    p = make_mon("pikachu", moves=["thunderbolt"])
    p.moves[0].pp = 1
    eng = BattleEngine(data, [p], [make_mon("squirtle")], rng=nochance)
    eng.submit_turn(MoveAction("thunderbolt"), MoveAction("growl"))
    assert p.moves[0].pp == 0
    assert [a for a in eng.legal_actions(P1) if isinstance(a, MoveAction)] == \
        [MoveAction("struggle")]
    ev = eng.submit_turn(MoveAction("struggle"), MoveAction("growl"))
    used = first(ev, E.MOVE_USED, P1)
    assert used.data["move"] == "Struggle"
    assert first(ev, E.RECOIL, P1) is not None


def test_multi_hit_double_kick(data, make_mon, nochance):
    eng = BattleEngine(data, [make_mon("pikachu", moves=["double-kick"])],
                       [make_mon("squirtle", level=100)], rng=nochance)
    ev = eng.submit_turn(MoveAction("double-kick"), MoveAction("recover"))
    assert first(ev, E.MULTI_HIT).data["hits"] == 2
    assert len([e for e in ev if e.type == E.DAMAGE]) == 2


def test_drain_and_recoil(data, make_mon, nochance):
    eng = BattleEngine(data, [make_mon("gengar")],
                       [make_mon("squirtle", level=100)], rng=nochance)
    gengar = eng.active(P1)
    gengar.take_damage(40)
    ev = eng.submit_turn(MoveAction("giga-drain"), MoveAction("recover"))
    drain = first(ev, E.DRAIN, P1)
    dmg = first(ev, E.DAMAGE, P2)
    assert drain.data["amount"] == max(1, dmg.data["amount"] // 2)

    ev = eng.submit_turn(MoveAction("double-edge"), MoveAction("recover"))
    rec = first(ev, E.RECOIL, P1)
    dmg = first(ev, E.DAMAGE, P2)
    assert rec.data["amount"] == max(1, dmg.data["amount"] * 33 // 100)


def test_fixed_and_level_damage(data, make_mon, nochance):
    eng = BattleEngine(data, [make_mon("geodude", level=42,
                                       moves=["seismic-toss"])],
                       [make_mon("squirtle", level=100)], rng=nochance)
    ev = eng.submit_turn(MoveAction("seismic-toss"), MoveAction("recover"))
    assert first(ev, E.DAMAGE, P2).data["amount"] == 42


def test_ohko_fails_on_higher_level(data, make_mon, maxroll):
    eng = BattleEngine(data, [make_mon("geodude", level=40)],
                       [make_mon("squirtle", level=60)], rng=maxroll)
    ev = eng.submit_turn(MoveAction("fissure"), MoveAction("recover"))
    assert first(ev, E.MOVE_FAILED, P1) is not None
    assert not eng.active(P2).fainted


def test_stat_stage_caps(data, make_mon, maxroll):
    eng = BattleEngine(data, [make_mon("pikachu", moves=["swords-dance"])],
                       [make_mon("squirtle")], rng=maxroll)
    for _ in range(3):
        eng.submit_turn(MoveAction("swords-dance"), MoveAction("recover"))
    assert eng.active(P1).stages["attack"] == 6
    ev = eng.submit_turn(MoveAction("swords-dance"), MoveAction("recover"))
    assert first(ev, E.STAT_CHANGE_FAILED, P1) is not None


# ── faints, replacement, battle end ──────────────────────────────────

def test_faint_replacement_flow(data, make_mon, maxroll):
    eng = BattleEngine(data,
                       [make_mon("pikachu", level=100)],
                       [make_mon("charmander", level=5),
                        make_mon("squirtle", level=5)], rng=maxroll)
    ev = eng.submit_turn(MoveAction("thunderbolt"), MoveAction("growl"))
    assert first(ev, E.FAINT, P2) is not None
    assert eng.phase == Phase.WAITING_REPLACEMENT
    assert eng.pending_replacements == {P2}
    with pytest.raises(Exception):
        eng.submit_turn(MoveAction("thunderbolt"), MoveAction("growl"))
    ev = eng.submit_replacement(P2, 1)
    assert first(ev, E.SEND_IN, P2).data["pokemon"] == "Squirtle"
    assert eng.phase == Phase.WAITING_ACTIONS


def test_battle_ends_when_side_out(data, make_mon, maxroll):
    eng = BattleEngine(data, [make_mon("pikachu", level=100)],
                       [make_mon("charmander", level=5)], rng=maxroll)
    ev = eng.submit_turn(MoveAction("thunderbolt"), MoveAction("growl"))
    assert eng.over
    assert eng.winner == P1
    assert first(ev, E.BATTLE_END).data["winner"] == P1


def test_stages_reset_on_switch(data, make_mon, maxroll):
    eng = BattleEngine(data, [make_mon("pikachu", moves=["swords-dance"]),
                              make_mon("squirtle")],
                       [make_mon("bulbasaur")], rng=maxroll)
    eng.submit_turn(MoveAction("swords-dance"), MoveAction("growl"))
    pika = eng.active(P1)
    assert pika.stages["attack"] == 1  # +2 dance, -1 growl
    eng.submit_turn(SwitchAction(1), MoveAction("growl"))
    eng.submit_turn(SwitchAction(0), MoveAction("growl"))
    assert eng.active(P1) is pika
    assert pika.stages["attack"] == -1  # only the fresh growl


# ── items, run, catch ────────────────────────────────────────────────

def test_potion_and_status_heal(data, make_mon, nochance):
    p = make_mon("pikachu")
    eng = BattleEngine(data, [p], [make_mon("bulbasaur")], rng=nochance)
    eng.active(P1).take_damage(30)
    eng.active(P1).status = "paralysis"
    ev = eng.submit_turn(ItemAction("potion"), MoveAction("growl"))
    assert first(ev, E.HEAL, P1).data["amount"] == 20
    ev = eng.submit_turn(ItemAction("paralyze-heal"), MoveAction("growl"))
    assert first(ev, E.STATUS_CURED, P1).data["status"] == "paralysis"
    assert eng.active(P1).status is None


def test_run_only_in_wild(data, make_mon, maxroll):
    trainer = BattleEngine(data, [make_mon("pikachu")], [make_mon("geodude")],
                           rng=maxroll)
    assert not any(isinstance(a, RunAction) for a in trainer.legal_actions(P1))
    wild = BattleEngine(data, [make_mon("pikachu")], [make_mon("geodude")],
                        wild=True, rng=maxroll)
    ev = wild.submit_turn(RunAction(), MoveAction("tackle"))
    assert first(ev, E.RUN_SUCCESS, P1) is not None  # pikachu outspeeds
    assert wild.over and wild.winner == "escaped"


def test_catch_with_overwhelming_ball(data, make_mon, maxroll):
    wild = BattleEngine(data, [make_mon("pikachu")], [make_mon("geodude")],
                        wild=True, rng=maxroll)
    ev = wild.submit_turn(ItemAction("master-ball-ish"), MoveAction("tackle"))
    assert first(ev, E.CATCH_SUCCESS, P1) is not None
    assert wild.over and wild.winner == "caught"
    assert wild.caught_pokemon is not None
    assert wild.caught_pokemon.species_id == "geodude"


def test_catch_fails_in_trainer_battle(data, make_mon, maxroll):
    eng = BattleEngine(data, [make_mon("pikachu")], [make_mon("geodude")],
                       rng=maxroll)
    ev = eng.submit_turn(CatchAction("poke-ball"), MoveAction("tackle"))
    assert first(ev, E.CATCH_FAIL, P1).data["reason"] == "trainer_battle"
    assert not eng.over


# ── persistence ──────────────────────────────────────────────────────

def test_hp_status_pp_persist_after_battle(data, make_mon, maxroll):
    mine = make_mon("squirtle", level=100)
    foe = make_mon("charmander", level=5)
    eng = BattleEngine(data, [mine], [foe], rng=maxroll)
    eng.submit_turn(MoveAction("recover"), MoveAction("ember"))   # take a hit + burn
    eng.submit_turn(MoveAction("water-gun"), MoveAction("ember"))  # then KO
    # battle over (foe fainted); the original PokemonState reflects it all
    assert eng.over
    assert mine.current_hp < mine.max_hp           # took the ember
    assert mine.status == "burn"                   # maxroll: 10% burn procs
    assert mine.move_slot("water-gun").pp == mine.move_slot("water-gun").pp_max - 1
    assert foe.current_hp == 0


def test_self_debuff_moves_hit_user_not_target(data, make_mon, maxroll):
    """PokeAPI 'damage+raise' stat changes (Superpower-style) apply to
    the user; 'damage+lower' (Iron Tail-style) apply to the target."""
    import json, os
    superpower = {
        "id": "superpower", "type": "fighting", "category": "physical",
        "power": 120, "accuracy": 100, "pp": 5, "priority": 0,
        "target": "selected-pokemon", "crit_stage": 0, "flags": [],
        "effect": {"kind": "damage+raise", "ailment": None, "ailment_chance": 0,
                   "stat_changes": [{"stat": "attack", "change": -1},
                                    {"stat": "defense", "change": -1}],
                   "stat_chance": 100, "flinch_chance": 0, "drain": 0,
                   "healing": 0, "min_hits": None, "max_hits": None}}
    path = os.path.join(data.data_dir, "moves", "superpower.json")
    with open(path, "w") as f:
        json.dump(superpower, f)
    eng = BattleEngine(data, [make_mon("geodude", moves=["superpower"])],
                       [make_mon("squirtle", level=100)], rng=maxroll)
    eng.submit_turn(MoveAction("superpower"), MoveAction("recover"))
    assert eng.active(P1).stages["attack"] == -1
    assert eng.active(P1).stages["defense"] == -1
    assert eng.active(P2).stages["defense"] == 0

    eng2 = BattleEngine(data, [make_mon("pikachu", moves=["iron-tail"])],
                        [make_mon("squirtle", level=100)], rng=maxroll)
    eng2.submit_turn(MoveAction("iron-tail"), MoveAction("recover"))
    assert eng2.active(P2).stages["defense"] == -1
    assert eng2.active(P1).stages["defense"] == 0
