"""Phase C: double battle resolves through the pure engine."""
import random

import pytest

from pkmn.battle.ai import RandomAI
from pkmn.battle.engine import BattleEngine
from pkmn.battle.events import E
from pkmn.battle.state import MoveAction, P1, P2


@pytest.fixture
def double_engine(data, make_mon):
    p1 = [make_mon("bulbasaur", 20), make_mon("charmander", 20)]
    p2 = [make_mon("squirtle", 20), make_mon("pikachu", 20)]
    return BattleEngine(data, p1, p2, format="double", rng=random.Random(42))


def _drive_replacements(eng):
    pending = list(eng.pending_replacements)
    for item in pending:
        s, slot = item if isinstance(item, tuple) else (item, 0)
        bench = eng.bench(s)
        if bench:
            eng.submit_replacement(s, bench[0], slot=slot)


def test_double_battle_resolves(double_engine):
    eng = double_engine
    ai1 = RandomAI(P1, random.Random(1))
    ai2 = RandomAI(P2, random.Random(2))
    for _ in range(200):
        if eng.over:
            break
        if eng.phase.value == "waiting_replacement":
            _drive_replacements(eng)
            continue
        actions_p1 = ai1.choose_actions(eng, n=2)
        actions_p2 = ai2.choose_actions(eng, n=2)
        eng.submit_turn(actions_p1, actions_p2)
    assert eng.over
    assert eng.winner in (P1, P2, "draw", "escaped", "caught")


def test_double_both_slots_act(double_engine):
    """Both sides field two active Pokemon at the start of a double battle."""
    eng = double_engine
    assert len(eng.actives(P1)) == 2
    assert len(eng.actives(P2)) == 2


def test_double_spread_move(data, make_mon):
    """Earthquake in doubles hits both foes (and the partner)."""
    p1 = [make_mon("geodude", 50, moves=["earthquake", "tackle"]),
          make_mon("charmander", 20)]
    p2 = [make_mon("squirtle", 20), make_mon("pikachu", 20)]
    eng = BattleEngine(data, p1, p2, format="double", rng=random.Random(99))
    # P1 slot 0 uses earthquake (spread); slot 1 tackles foe slot 0.
    actions_p1 = [MoveAction("earthquake"), MoveAction("tackle", target_slot=0)]
    actions_p2 = [MoveAction("tackle"), MoveAction("tackle")]
    events = eng.submit_turn(actions_p1, actions_p2)
    damage_events = [e for e in events if e.type == E.DAMAGE]
    # Earthquake should hit both P2 targets at minimum.
    assert len(damage_events) >= 2


def test_double_single_target_slot(data, make_mon):
    """A single-target move respects the requested foe slot."""
    p1 = [make_mon("pikachu", 50, moves=["tackle"]), make_mon("charmander", 20)]
    p2 = [make_mon("squirtle", 20), make_mon("pikachu", 20)]
    eng = BattleEngine(data, p1, p2, format="double", rng=random.Random(7))
    foe1_before = eng.actives(P2)[1].current_hp
    eng.submit_turn(
        [MoveAction("tackle", target_slot=1), MoveAction("tackle", target_slot=1)],
        [MoveAction("tackle"), MoveAction("tackle")],
    )
    # Foe slot 1 took damage from at least the slot-0 attacker.
    assert eng.actives(P2)[1].current_hp < foe1_before


def test_singles_unchanged(data, make_mon):
    """Existing singles behavior is unchanged."""
    p1 = [make_mon("bulbasaur", 20)]
    p2 = [make_mon("charmander", 20)]
    eng = BattleEngine(data, p1, p2, rng=random.Random(1))
    assert eng.format == "single"
    assert len(eng.actives(P1)) == 1
    assert len(eng.actives(P2)) == 1
    assert eng.active(P1) is eng.actives(P1)[0]


def test_doubles_replacement_slot(data, make_mon):
    """When a slot faints, its replacement targets that slot."""
    p1 = [make_mon("pikachu", 50, moves=["tackle"]), make_mon("charmander", 50),
          make_mon("bulbasaur", 50)]
    # Two paper-thin foes so they faint quickly.
    p2 = [make_mon("squirtle", 5), make_mon("pikachu", 5)]
    eng = BattleEngine(data, p1, p2, format="double", rng=random.Random(3))
    safety = 0
    while not eng.over and safety < 50:
        safety += 1
        if eng.phase.value == "waiting_replacement":
            # Replacement tokens are (side, slot) tuples in doubles.
            for item in list(eng.pending_replacements):
                assert isinstance(item, tuple)
                s, slot = item
                bench = eng.bench(s)
                if bench:
                    eng.submit_replacement(s, bench[0], slot=slot)
            continue
        eng.submit_turn(
            [MoveAction("tackle", target_slot=0),
             MoveAction("tackle", target_slot=1)],
            [MoveAction("tackle"), MoveAction("tackle")],
        )
    assert eng.over
