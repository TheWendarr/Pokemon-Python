"""Stat math, damage formula, and data-layer tests."""
import pytest

from pkmn.battle.damage import calc_damage
from pkmn.battle.engine import BattleEngine
from pkmn.battle.state import P1, P2
from pkmn.core.stats import (accuracy_multiplier, calc_stat, crit_chance,
                             stage_multiplier)
from pkmn.data.models import norm_stat


# ── stat formula ─────────────────────────────────────────────────────

def test_hp_formula():
    # Lv50 Pikachu (base 35 HP), 31 IV, 0 EV -> 110
    assert calc_stat("hp", 35, 31, 0, 50) == 110


def test_other_stat_formula_neutral():
    # Lv50 Pikachu SpA: base 50, 31 IV, 0 EV -> floor(131*50/100)+5 = 70
    assert calc_stat("special_attack", 50, 31, 0, 50) == 70


def test_nature_modifier_applied_after_floor():
    base = calc_stat("attack", 55, 31, 0, 50)            # 75
    assert calc_stat("attack", 55, 31, 0, 50, 1.1) == int(base * 1.1)
    assert calc_stat("attack", 55, 31, 0, 50, 0.9) == int(base * 0.9)


def test_ev_quarter_division():
    # 252 EVs add 252//4 = 63 to the pre-level term
    assert calc_stat("attack", 55, 31, 252, 50) > calc_stat("attack", 55, 31, 0, 50)


def test_shedinja_hp():
    assert calc_stat("hp", 1, 31, 252, 100) == 1


# ── stages ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("stage,expected", [
    (0, 1.0), (1, 1.5), (2, 2.0), (6, 4.0),
    (-1, 2 / 3), (-2, 0.5), (-6, 0.25),
])
def test_stage_multiplier_exact_fractions(stage, expected):
    assert stage_multiplier(stage) == pytest.approx(expected)


def test_accuracy_multiplier():
    assert accuracy_multiplier(0) == 1.0
    assert accuracy_multiplier(-1) == pytest.approx(0.75)
    assert accuracy_multiplier(1) == pytest.approx(4 / 3)


def test_gen5_crit_table():
    assert crit_chance(0) == pytest.approx(1 / 16)
    assert crit_chance(3) == pytest.approx(1 / 3)
    assert crit_chance(7) == pytest.approx(1 / 2)


# ── damage formula (hand-verified) ───────────────────────────────────

def test_thunderbolt_hand_calc(data, make_mon, maxroll):
    """Lv50 Pikachu Thunderbolt(95) vs Lv50 Squirtle, 31 IV / 0 EV /
    neutral, max roll, no crit: base 36 -> STAB 54 -> x2 water = 108."""
    eng = BattleEngine(data, [make_mon("pikachu")], [make_mon("squirtle")],
                       rng=maxroll)
    dmg, detail = calc_damage(data, eng.active(P1), eng.active(P2),
                              data.move("thunderbolt"), rng=maxroll)
    assert dmg == 108
    assert detail["stab"] is True
    assert detail["effectiveness"] == 2.0


def test_burn_halves_physical_only(data, make_mon, maxroll):
    eng = BattleEngine(data, [make_mon("pikachu")], [make_mon("squirtle")],
                       rng=maxroll)
    atk, dfn = eng.active(P1), eng.active(P2)
    tackle = data.move("tackle")
    base, _ = calc_damage(data, atk, dfn, tackle, rng=maxroll)
    atk.status = "burn"
    burned, _ = calc_damage(data, atk, dfn, tackle, rng=maxroll)
    assert burned == base // 2
    tb = data.move("thunderbolt")
    full, _ = calc_damage(data, atk, dfn, tb, rng=maxroll)
    assert full == 108  # special damage untouched by burn


def test_crit_doubles_and_ignores_stages(data, make_mon, maxroll):
    eng = BattleEngine(data, [make_mon("pikachu")], [make_mon("squirtle")],
                       rng=maxroll)
    atk, dfn = eng.active(P1), eng.active(P2)
    tackle = data.move("tackle")
    atk.stages["attack"] = -2          # crit ignores attacker's debuff
    dfn.stages["defense"] = +2         # and defender's buff
    plain, _ = calc_damage(data, atk, dfn, tackle, rng=maxroll, crit=False)
    crit, d = calc_damage(data, atk, dfn, tackle, rng=maxroll, crit=True)
    neutral_atk = eng.active(P1)
    neutral_atk.stages["attack"] = 0
    dfn.stages["defense"] = 0
    neutral, _ = calc_damage(data, neutral_atk, dfn, tackle, rng=maxroll)
    assert d["crit"] is True
    assert crit == neutral * 2
    assert plain < neutral


def test_type_immunity_via_chart(data):
    assert data.effectiveness("electric", ("rock", "ground")) == 0
    assert data.effectiveness("water", ("rock", "ground")) == 4
    assert data.effectiveness("normal", ("ghost", "poison")) == 0


def test_min_damage_is_one(data, make_mon, maxroll):
    weak = make_mon("pikachu", level=5)
    tank = make_mon("geodude", level=100)
    eng = BattleEngine(data, [weak], [tank], rng=maxroll)
    dmg, _ = calc_damage(data, eng.active(P1), eng.active(P2),
                         data.move("quick-attack"), rng=maxroll)
    assert dmg >= 1


# ── data layer ───────────────────────────────────────────────────────

def test_norm_stat_aliases():
    assert norm_stat("special-attack") == "special_attack"
    assert norm_stat("Sp. Atk") == "special_attack"
    assert norm_stat("SPD") == "special_defense"


def test_species_lookup_by_name_and_dex(data):
    assert data.species("Pikachu").dex == 25
    assert data.species(25).id == "pikachu"
    assert data.species("025").id == "pikachu"


def test_pokemon_state_roundtrip(data, make_mon):
    p = make_mon("bulbasaur", level=37)
    p.take_damage(13)
    p.status = "poison"
    p.moves[0].pp -= 4
    from pkmn.core.pokemon import PokemonState
    q = PokemonState.from_dict(p.to_dict(), data)
    assert q.current_hp == p.current_hp
    assert q.status == "poison"
    assert q.moves[0].pp == p.moves[0].pp
    assert q.stats == p.stats
