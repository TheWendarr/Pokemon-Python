"""Full-catalog dataset integrity (skipped without generated game/data)
plus pure unit tests for the REST normalizers and engine item mechanics."""
import os

import pytest

from pkmn.battle.engine import BattleEngine
from pkmn.battle.events import E
from pkmn.battle.state import ItemAction, MoveAction, P1, P2
from pkmn.data.repository import GameData
from pkmn.datagen.mechanics import (ability_record_from_rest,
                                    item_record_from_rest)

needs_data = pytest.mark.skipif(
    not os.path.exists("game/data/abilities.json"),
    reason="needs the generated full dataset")


@pytest.fixture(scope="module")
def full():
    return GameData("game/data")


# ── catalog shape ────────────────────────────────────────────────────

@needs_data
def test_catalog_counts(full):
    assert len(full.all_species_ids()) == 649
    assert len(full.all_ability_ids()) == 164          # every Gen 1-5 ability
    assert len(full.all_item_ids()) >= 600             # full item catalog
    assert full.has_move("tackle") and full.has_move("v-create")


@needs_data
def test_cross_references_all_resolve(full):
    assert full.validate() == []


@needs_data
def test_gen5_typing_restored(full):
    assert tuple(full.species("jigglypuff").types) == ("normal",)  # not fairy
    assert tuple(full.species("marill").types) == ("water",)
    assert tuple(full.species("gardevoir").types) == ("psychic",)


@needs_data
def test_post_gen5_abilities_filtered(full):
    assert "protean" not in full.species("kecleon").abilities
    assert "color-change" in full.species("kecleon").abilities
    assert "slush-rush" not in full.species("beartic").abilities


@needs_data
def test_item_catalog_fields(full):
    lo = full.item("leftovers")
    assert lo.holdable and lo.pocket == "misc" or lo.holdable
    assert full.item("ultra-ball").is_ball
    assert full.item("ultra-ball").ball_rate == 2.0
    assert full.item("master-ball").ball_rate == 255.0
    assert full.item("potion").heal == 20
    assert full.item("max-potion").heal == -1
    assert full.item("revive").revive == 0.5
    assert dict(full.item("x-attack").stages) == {"attack": 1}
    assert full.item("tm01") is not None                # machines: data-only


@needs_data
def test_ability_and_move_effect_text(full):
    intim = full.ability("intimidate")
    assert intim and intim["generation"] == 3 and intim["short_effect"]
    assert full.ability("teravolt")["generation"] == 5
    assert full.ability("protean") is None              # Gen 6: not in a Gen 5 game


# ── REST normalizers (pure, no network) ──────────────────────────────

def test_rest_ability_normalizer():
    sample = {"name": "static", "is_main_series": True,
              "generation": {"name": "generation-iii"},
              "effect_entries": [
                  {"language": {"name": "de"}, "short_effect": "nein"},
                  {"language": {"name": "en"},
                   "short_effect": "Has a 30% chance of paralyzing."}]}
    ident, rec = ability_record_from_rest(sample)
    assert ident == "static" and rec["generation"] == 3
    assert "30%" in rec["short_effect"]
    assert ability_record_from_rest(
        {"name": "protean", "is_main_series": True,
         "generation": {"name": "generation-vi"}, "effect_entries": []}) is None


def test_rest_item_normalizer():
    sample = {"name": "leftovers", "cost": 200, "fling_power": 10,
              "category": {"name": "held-items"},
              "attributes": [{"name": "holdable"}, {"name": "countable"}],
              "game_indices": [{"generation": {"name": "generation-ii"}}],
              "effect_entries": [{"language": {"name": "en"},
                                  "short_effect": "Restores 1/16 max HP."}]}
    ident, rec = item_record_from_rest(sample, "misc")
    assert ident == "leftovers" and rec["holdable"]
    assert rec["short_effect"].startswith("Restores")
    gen9 = dict(sample, name="ability-shield",
                game_indices=[{"generation": {"name": "generation-ix"}}])
    assert item_record_from_rest(gen9, "misc") is None


# ── engine bag mechanics (fixture data) ──────────────────────────────

def test_x_attack_dire_hit_guard_spec(data, make_mon, maxroll):
    eng = BattleEngine(data, [make_mon("pikachu")],
                       [make_mon("squirtle", level=100)], rng=maxroll)
    eng.submit_turn(ItemAction("x-attack"), MoveAction("recover"))
    assert eng.active(P1).stages["attack"] == 1
    eng.submit_turn(ItemAction("dire-hit"), MoveAction("recover"))
    assert eng.active(P1).vol.crit_bonus == 2
    ev = eng.submit_turn(ItemAction("guard-spec"), MoveAction("recover"))
    assert eng.sides[P1].mist == 4                       # set to 5, 1 tick elapsed
    assert any(e.type == E.SCREEN_START for e in ev)


def test_revive_restores_fainted_bench_member(data, make_mon, maxroll):
    fainted = make_mon("charmander")
    eng = BattleEngine(data, [make_mon("pikachu"), fainted],
                       [make_mon("squirtle", level=100)], rng=maxroll)
    eng.parties[P1][1].take_damage(99999)
    assert eng.parties[P1][1].fainted
    ev = eng.submit_turn(ItemAction("revive"), MoveAction("recover"))
    bp = eng.parties[P1][1]
    assert not bp.fainted and bp.current_hp == bp.max_hp // 2
    assert any(e.type == E.HEAL for e in ev)


def test_full_restore_heals_and_cures(data, make_mon, maxroll):
    eng = BattleEngine(data, [make_mon("squirtle")],
                       [make_mon("pikachu", moves=["splash"])], rng=maxroll)
    bp = eng.active(P1)
    bp.take_damage(40)
    bp.status = "burn"
    eng.submit_turn(ItemAction("full-restore"), MoveAction("splash"))
    assert bp.current_hp == bp.max_hp and bp.status is None
