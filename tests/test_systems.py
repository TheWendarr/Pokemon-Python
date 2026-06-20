"""Phase 5: experience, evolution, move learning, save/load, menus, PC."""
import os

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import random

import pytest

pytest.importorskip("pygame")
pytest.importorskip("pytmx")

from pkmn.core.experience import battle_exp, exp_total, level_for_exp  # noqa: E402
from pkmn.core.pokemon import PokemonState, evolve, gain_exp  # noqa: E402
from pkmn.game.battle_scene import BattleScene      # noqa: E402
from pkmn.game.config import A, B, DOWN, RIGHT, START      # noqa: E402
from pkmn.game.menus import (BagScene, PartyScene, PauseScene, PCScene,
                             SummaryScene)          # noqa: E402
from pkmn.game.overworld import OverworldScene      # noqa: E402
from pkmn.game.save import load_game, save_game    # noqa: E402
from pkmn.game.scene import Game                    # noqa: E402

pytestmark = pytest.mark.skipif(
    not os.path.exists("game/data/species"),
    reason="needs the generated full dataset")


@pytest.fixture
def game():
    g = Game(headless=True, seed=31)
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


# ── experience math ──────────────────────────────────────────────────

def test_exp_curves_and_inverse():
    assert exp_total("medium", 10) == 1000
    assert exp_total("slow", 100) == 1_250_000
    assert exp_total("medium-slow", 100) == 1_059_860
    for rate in ("medium", "fast", "slow", "medium-slow",
                 "slow-then-very-fast", "fast-then-very-slow"):
        for lvl in (5, 17, 50, 99):
            assert level_for_exp(rate, exp_total(rate, lvl)) == lvl
    assert battle_exp(60, 7) == 60
    assert battle_exp(60, 7, trainer=True) == 90


def test_gain_exp_levels_and_learns_moves(game):
    d = game.data
    p = PokemonState.generate(d, "oshawott", 6, rng=random.Random(2),
                              moves=["tackle"])
    sp = d.species("oshawott")
    nxt = next(e for e in sp.learnset["level_up"] if e.level > 6)
    need = exp_total(sp.growth_rate, nxt.level) - p.exp
    old_atk = p.stats["attack"]
    res = gain_exp(p, d, need)
    assert res["levels"] and p.level == nxt.level
    assert nxt.move in res["moves"]
    assert p.move_slot(nxt.move) is not None
    assert p.stats["attack"] > old_atk


def test_evolution_at_level(game):
    d = game.data
    p = PokemonState.generate(d, "oshawott", 16, rng=random.Random(3))
    res = gain_exp(p, d, exp_total(d.species("oshawott").growth_rate, 17)
                   - p.exp)
    assert res["evolution"] == "dewott"
    evolve(p, d, "dewott")
    assert p.species_id == "dewott" and p.level == 17


def test_battle_awards_exp_and_evolves(game):
    d, st = game.data, game.state
    starter = st.party[0]
    starter.level = 16
    starter.current_hp = -1
    starter.exp = -1
    starter.bind(d)
    starter.exp = exp_total(d.species("oshawott").growth_rate, 17) - 1
    wild = PokemonState.generate(d, "patrat", 3, rng=st.rng)
    game.push(BattleScene(game, [wild], wild=True))
    b = game.top
    assert mash_until(game, lambda: isinstance(game.top, OverworldScene))
    assert b.eng.winner == "p1"
    assert starter.level >= 17
    assert starter.species_id == "dewott"          # evolved after the win


# ── save / load ──────────────────────────────────────────────────────

def test_save_load_roundtrip(game, tmp_path):
    st = game.state
    st.flags.add("beat_rival")
    st.money = 4321
    st.bag["great-ball"] = 2
    st.pc.append(PokemonState.generate(game.data, "pidove", 4, rng=st.rng))
    st.map_id, st.tile, st.facing = "route1", (11, 6), "up"
    gain_exp(st.party[0], game.data, 500)
    path = str(tmp_path / "save.json")
    save_game(st, path)
    loaded = load_game(game.data, path)
    assert loaded.money == 4321 and "beat_rival" in loaded.flags
    assert loaded.bag["great-ball"] == 2
    assert loaded.map_id == "route1" and loaded.tile == (11, 6)
    assert loaded.party[0].exp == st.party[0].exp
    assert loaded.party[0].level == st.party[0].level
    assert loaded.pc[0].species_id == "pidove"
    # Game(save_path=...) resumes from the file (the acceptance reload)
    g2 = Game(headless=True, save_path=path)
    assert g2.state.money == 4321 and g2.state.map_id == "route1"


# ── menus ────────────────────────────────────────────────────────────

def test_pause_party_summary_chain(game):
    press(game, START)
    assert isinstance(game.top, PauseScene)
    press(game, A)                                   # POKEMON
    assert isinstance(game.top, PartyScene)
    press(game, A)                                   # open the slot action menu
    press(game, A)                                   # SUMMARY -> summary of slot 0
    assert isinstance(game.top, SummaryScene)
    game.draw()
    press(game, B)
    press(game, B)
    assert isinstance(game.top, PauseScene)
    press(game, B)
    assert isinstance(game.top, OverworldScene)


def test_party_reorder_swaps_slots(game):
    st = game.state
    if len(st.party) < 2:
        st.party.append(PokemonState.generate(game.data, "pidgey", 5))
    first, second = st.party[0].species_id, st.party[1].species_id
    press(game, START)
    press(game, A)                                   # PartyScene
    assert isinstance(game.top, PartyScene)
    ps = game.top
    press(game, A)                                   # open the action menu
    press(game, DOWN)                                # SUMMARY -> MOVE
    press(game, A)                                   # pick up slot 0
    assert ps.held == 0
    press(game, DOWN)                                # cursor -> slot 1
    press(game, A)                                   # swap into slot 1
    assert ps.held is None
    assert st.party[0].species_id == second
    assert st.party[1].species_id == first


def test_pause_menu_saves(game, tmp_path):
    game.save_path = str(tmp_path / "s.json")
    press(game, START)
    press(game, DOWN); press(game, DOWN)             # -> SAVE
    press(game, A)
    assert os.path.exists(game.save_path)
    assert load_game(game.data, game.save_path).money == game.state.money


def test_overworld_bag_heals(game):
    game.state.party[0].current_hp = 5
    game.push(BagScene(game))
    bag = game.top
    # cursor 0 is alphabetically first: poke-ball -> move to potion
    items = [k for k, _ in bag.items()]
    while items[bag.cursor] != "potion":
        press(game, DOWN)
    press(game, A)                                   # pick potion
    press(game, A)                                   # target slot 0
    assert game.state.party[0].current_hp == 25
    assert game.state.bag["potion"] == 4


def test_pc_deposit_withdraw(game):
    st = game.state
    st.party.append(PokemonState.generate(game.data, "patrat", 4, rng=st.rng))
    game.push(PCScene(game))
    press(game, DOWN)                                # select slot 1
    press(game, A)                                   # deposit
    assert len(st.party) == 1 and len(st.pc) == 1
    from pkmn.game.config import RIGHT
    press(game, RIGHT)
    press(game, A)                                   # withdraw
    assert len(st.party) == 2 and len(st.pc) == 0


def test_battle_cursor_memory_and_switch_reset():
    from types import SimpleNamespace
    from pkmn.game.battle_scene import BattleScene
    g = Game(headless=True, seed=4)
    g.state.party.append(PokemonState.generate(g.data, "pidgey", 6))
    foe = PokemonState.generate(g.data, "rattata", 4)
    bs = BattleScene(g, [foe], wild=True)
    g.push(bs)

    def frame(press=()):
        bs.handle(SimpleNamespace(pressed=set(press), held=set()))
        bs.update()

    def run_until(cond, cap=4000):
        for _ in range(cap):
            p = {A} if (bs.cur and bs.cur.get("kind") == "text") else set()
            frame(p)
            if cond():
                return True
        return False

    assert run_until(lambda: bs.mode == "menu")
    frame({A})                                   # FIGHT -> moves
    assert bs.mode == "moves"
    if len(bs._move_actions()) >= 2:
        frame({RIGHT})                           # move to slot 1
        assert bs.cursor == 1
        frame({A})                               # use the slot-1 move
        assert run_until(lambda: bs.mode == "menu")
        frame({A})                               # re-open FIGHT
        assert bs.mode == "moves" and bs.cursor == 1   # remembered!
        frame({B})                               # back to the main menu
    # a switch wipes the remembered move slot (new mon, new moves)
    bs.cursors["moves"] = 1
    assert bs.mode == "menu"
    frame({DOWN})                                # FIGHT -> PKMN
    frame({A})                                   # open party
    assert bs.mode == "party"
    frame({DOWN})                                # -> benched mon
    frame({A})                                   # switch to it
    assert bs.cursors["moves"] == 0
