"""Acceptance tests for A3: EV-yield data flow and capping."""
from pkmn.data.repository import GameData
from pkmn.game.battle_scene import BattleScene

DATA = GameData("game/data")


def test_bulbasaur_has_ev_yield():
    sp = DATA.species("bulbasaur")
    assert sp.ev_yield == {"special_attack": 1}


def test_ev_yield_awards_on_knockout():
    """EV is added to winner.evs when a foe faints."""
    from pkmn.core.pokemon import PokemonState
    winner = PokemonState.generate(DATA, "charmander", 10)
    assert winner.evs.get("special_attack", 0) == 0

    bulbasaur_sp = DATA.species("bulbasaur")
    BattleScene._award_evs(winner, bulbasaur_sp.ev_yield)

    assert winner.evs["special_attack"] == 1


def test_ev_252_per_stat_cap():
    """Award is capped at 252 per stat."""
    from pkmn.core.pokemon import PokemonState
    winner = PokemonState.generate(DATA, "charmander", 10)
    winner.evs["special_attack"] = 251
    BattleScene._award_evs(winner, {"special_attack": 5})
    assert winner.evs["special_attack"] == 252


def test_ev_510_total_cap():
    """Award is capped once total EVs reach 510."""
    from pkmn.core.pokemon import PokemonState
    winner = PokemonState.generate(DATA, "charmander", 10)
    winner.evs = {"hp": 252, "attack": 255, "defense": 0,
                  "special_attack": 0, "special_defense": 0, "speed": 0}
    BattleScene._award_evs(winner, {"special_attack": 10})
    # total was 507, so only 3 can be added
    assert winner.evs["special_attack"] == 3
    assert sum(winner.evs.values()) == 510


def test_ev_yield_zero_species():
    """Species with no EV yield (ev_yield={}) award nothing."""
    from pkmn.core.pokemon import PokemonState
    winner = PokemonState.generate(DATA, "charmander", 10)
    before = dict(winner.evs)
    BattleScene._award_evs(winner, {})
    assert winner.evs == before
