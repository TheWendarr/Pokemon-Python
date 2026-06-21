"""Polish & extensibility: feature toggles, the expanded script command
set (choice/shop/give_pokemon/money), per-map weather, held items in
trainer specs, move-replacement prompts, and the Triad showcase region."""
import os

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pytest

pytest.importorskip("pygame")
pytest.importorskip("pytmx")

from pkmn.core.experience import exp_total          # noqa: E402
from pkmn.core.pokemon import PokemonState, gain_exp  # noqa: E402
from pkmn.data.repository import GameData           # noqa: E402
from pkmn.cli.lint import Lint                      # noqa: E402
from pkmn.game.battle_scene import BattleScene      # noqa: E402
from pkmn.game.config import A, B, DOWN, START, UP  # noqa: E402
from pkmn.game.menus import ChoiceScene, PauseScene, ShopScene  # noqa: E402
from pkmn.game.overworld import OverworldScene      # noqa: E402
from pkmn.game.scene import Game                    # noqa: E402
from pkmn.game.script import DONE, ScriptRunner, parse_party  # noqa: E402

pytestmark = pytest.mark.skipif(
    not os.path.exists("game/data/species"),
    reason="needs the generated full dataset")

TRIAD = "examples/triad"


@pytest.fixture
def game():
    g = Game(headless=True, seed=99, game_dir=TRIAD)
    g.push(OverworldScene(g))
    yield g
    import pygame
    pygame.quit()


def press(g, key):
    g.input.press(key)
    g.tick()
    g.input.release(key)


def mash_until(g, predicate, frames=6000):
    for _ in range(frames):
        if predicate():
            return True
        press(g, A)
        g.draw()
    return False


# ── the showcase region itself ───────────────────────────────────────

def test_triad_lints_clean():
    assert Lint(TRIAD, GameData("game/data")).run() == 0


def test_triad_manifest_drives_everything(game):
    st = game.state
    assert st.party[0].species_id == "tepig" and st.party[0].level == 12
    assert [s.move_id for s in st.party[0].moves] == \
        ["ember", "tackle", "defense-curl"]          # designer-chosen moves
    assert st.money == 2000
    assert game.manifest["name"].startswith("Triad")


def test_form_aliases_resolve():
    d = GameData("game/data")
    assert d.species("basculin").id == "basculin-red-striped"
    assert d.species("frillish").id == "frillish-male"


def test_per_map_weather_reaches_battles(game):
    ow = game.scenes[0]
    ow.load_map("route_shoreline")
    assert ow.map.props.get("weather") == "rain"
    ow._wild_encounter()
    assert isinstance(game.top, BattleScene)
    assert game.top.eng.weather == "rain"            # raining before turn 1
    game.draw()                                      # tint overlay renders
    while isinstance(game.top, BattleScene):
        game.scenes.pop()                            # discard for the test
    ow.load_map("route_mirage")
    assert int(ow.map.props["encounter_chance"]) == 6


def test_trainer_spec_held_items(game):
    party = parse_party("roggenrola:11@oran-berry|drilbur:11",
                        game.data, game.state.rng)
    assert party[0].held_item == "oran-berry"
    assert party[1].held_item is None


def test_roadblock_npc_visible_unless_flag(game):
    ow = game.scenes[0]
    ow.load_map("route_mirage")
    assert ow.find_npc("Ranger Dune") is not None    # blocking the pass
    game.state.flags.add("beat_fern")
    ow.load_map("route_mirage")
    assert ow.find_npc("Ranger Dune") is None        # storm cleared


# ── feature toggles ──────────────────────────────────────────────────

def test_features_disable_systems(game):
    ow = game.scenes[0]
    game.manifest["features"]["encounters"] = False
    ow.load_map("route_canopy")
    game.state.tile = (5, 5)                         # inside tall grass
    for _ in range(300):
        for d in ("left", "right"):
            press(game, d); press(game, d); press(game, d); press(game, d)
            press(game, d); press(game, d); press(game, d); press(game, d)
        assert isinstance(game.top, OverworldScene)  # never a battle
    game.manifest["features"]["trainers"] = False
    game.state.tile = (8, 7)                         # in Nino's sight line
    press(game, UP)
    for _ in range(20):
        game.tick()
    assert ow.cutscene is None                       # nobody spotted us


def test_pause_menu_options_follow_features(game):
    game.manifest["features"].update({"menu_bag": False, "saving": False,
                                      "pokedex": False, "controls": False})
    press(game, START)
    assert isinstance(game.top, PauseScene)
    assert game.top.OPTIONS == ("POKEMON", "CLOSE")
    press(game, B)


def test_running_doubles_step_speed(game):
    ow = game.scenes[0]
    game.state.tile = (11, 8)
    game.state.facing = "up"
    g = game
    g.input.press(UP)
    g.tick()                                          # step begins (walk)
    walk_px = ow.move_px
    g.input.press(B)                                  # now hold B: run
    g.tick()
    run_px = ow.move_px - walk_px
    g.input.release(B)
    g.input.release(UP)
    assert run_px == walk_px * 2                      # 4px vs 2px per frame
    for _ in range(20):
        g.tick()


# ── new script commands ──────────────────────────────────────────────

def test_choice_command_branches(game):
    ow = game.scenes[0]
    runner = ScriptRunner(game, ow, [
        {"choice": {"prompt": "Pick one", "options": [
            {"label": "Left", "then": [{"set_flag": "went_left"}]},
            {"label": "Right", "then": [{"set_flag": "went_right"}]}]}},
        {"set_flag": "after_choice"},
    ])
    assert runner.advance() == "wait"
    assert isinstance(game.top, ChoiceScene)
    press(game, DOWN)                                 # cursor -> Right
    press(game, A)
    assert runner.resume() == DONE
    assert "went_right" in game.state.flags
    assert "went_left" not in game.state.flags
    assert "after_choice" in game.state.flags


def test_shop_buys_with_money(game):
    ow = game.scenes[0]
    st = game.state
    runner = ScriptRunner(game, ow, [
        {"shop": {"items": ["potion", "great-ball"],
                  "prices": {"great-ball": 500}}}])
    runner.advance()
    assert isinstance(game.top, ShopScene)
    press(game, A)                                    # choose BUY
    money, potions = st.money, st.bag.get("potion", 0)
    press(game, A)                                    # buy potion (first row)
    assert st.bag["potion"] == potions + 1
    assert st.money == money - game.data.item("potion").cost
    press(game, DOWN)
    press(game, A)                                    # great-ball @ override 500
    assert st.money == money - game.data.item("potion").cost - 500
    st.money = 0
    press(game, A)
    assert "afford" in game.top.note                  # refuses politely
    press(game, B)                                    # back to BUY/SELL menu
    press(game, B)                                    # leave the shop
    assert runner.resume() == DONE


def test_give_pokemon_take_money_if_money(game):
    ow = game.scenes[0]
    st = game.state
    runner = ScriptRunner(game, ow, [
        {"give_pokemon": {"species": "frillish", "level": 10,
                          "item": "oran-berry"}},
        {"take_money": 500},
        {"if_money": {"amount": 10**9,
                      "then": [{"set_flag": "rich"}],
                      "else": [{"set_flag": "modest"}]}},
    ])
    assert runner.advance() == DONE
    assert st.party[-1].species_id == "frillish-male"
    assert st.party[-1].held_item == "oran-berry"
    assert st.money == 1500 and "modest" in st.flags


# ── move-replacement prompt ──────────────────────────────────────────

def test_move_replacement_prompt(game):
    d, st = game.data, game.state
    sp = d.species("tepig")
    nxt = next(e for e in sp.learnset["level_up"] if e.level > 12)
    four = [m for m in ("tackle", "growl", "ember", "defense-curl",
                        "tail-whip") if m != nxt.move][:4]
    full = PokemonState.generate(d, "tepig", nxt.level - 1, rng=st.rng,
                                 moves=four)
    st.party[0] = full
    full.exp = exp_total(sp.growth_rate, nxt.level) - 1
    wild = PokemonState.generate(d, "sewaddle", 3, rng=st.rng)
    game.push(BattleScene(game, [wild], wild=True))
    b = game.top
    assert mash_until(game, lambda: b.mode == "learn", 3000)
    game.draw()                                       # render the prompt
    press(game, DOWN)                                 # forget slot 1
    forgotten = full.moves[1].move_id
    press(game, A)
    assert full.move_slot(nxt.move) is not None
    assert full.move_slot(forgotten) is None
    assert mash_until(game, lambda: not isinstance(game.top, BattleScene))


# ── a slice of the showcase, played ──────────────────────────────────

def test_sheriff_gates_then_falls(game):
    ow = game.scenes[0]
    st = game.state
    st.party[0] = PokemonState.generate(game.data, "tepig", 30,
                                        rng=st.rng, moves=["flamethrower"])
    ow.load_map("duston")
    sheriff = ow.find_npc("Sheriff Cinder")
    st.tile = (sheriff.tile[0], sheriff.tile[1] + 1)
    st.facing = "up"
    press(game, A)                                    # gated: no wardens yet
    mash_until(game, lambda: ow.script is None, 200)
    assert "beat_cinder" not in st.flags
    st.flags.update({"beat_fern", "beat_gale"})
    money = st.money
    press(game, A)                                    # now the real fight
    assert mash_until(game, lambda: isinstance(game.top, BattleScene), 400)
    b = game.top
    assert b.eng.active("p2").held_item == "focus-sash"
    assert mash_until(game, lambda: ow.script is None
                      and isinstance(game.top, OverworldScene), 8000)
    assert b.eng.winner == "p1"
    assert "beat_cinder" in st.flags and "finished_triad" in st.flags
    assert st.money == money + 1500 + 1000            # prize + champion bonus
    press(game, A)                                    # post-victory line
    mash_until(game, lambda: ow.script is None, 200)
