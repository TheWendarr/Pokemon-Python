"""Day/night cycle: phase math, the configurable time source, and
time-gated triggers."""
import os

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pytest                                              # noqa: E402

from pkmn.game import daytime                             # noqa: E402

_REAL = os.path.exists("game/data/species")


# ── phase math (no pygame needed) ────────────────────────────────────
def test_phase_for_hour_boundaries():
    assert daytime.phase_for_hour(0) == "night"
    assert daytime.phase_for_hour(4) == "night"
    assert daytime.phase_for_hour(5) == "morning"
    assert daytime.phase_for_hour(9) == "morning"
    assert daytime.phase_for_hour(10) == "day"
    assert daytime.phase_for_hour(17) == "day"
    assert daytime.phase_for_hour(18) == "evening"
    assert daytime.phase_for_hour(20) == "evening"
    assert daytime.phase_for_hour(21) == "night"
    assert daytime.phase_for_hour(23) == "night"


def test_current_phase_wraps_and_tints():
    assert daytime.current_phase(26) == daytime.phase_for_hour(2)   # 26 % 24
    assert daytime.tint("day")[3] == 0           # midday is untinted
    assert daytime.tint("night")[3] > 0          # night darkens
    assert daytime.is_night("night") and not daytime.is_night("day")
    assert set(daytime.PHASES) == {"morning", "day", "evening", "night"}


# ── configurable time source on the Game ─────────────────────────────
@pytest.mark.skipif(not _REAL, reason="needs full game data + region")
def test_game_time_phase_config():
    import pygame

    from pkmn.game.scene import Game

    for value, expected in [("night", "night"), ("morning", "morning"),
                            ("off", "day"), ("21", "night"), ("6", "morning"),
                            ("14", "day")]:
        g = Game(headless=True, seed=1, daynight=value)
        assert g.time_phase() == expected, value
        pygame.quit()


# ── time-gated triggers ──────────────────────────────────────────────
@pytest.mark.skipif(not _REAL, reason="needs full game data + region")
def test_trigger_time_gate():
    import pygame

    from pkmn.game.overworld import OverworldScene
    from pkmn.game.scene import Game

    def trig(time):
        return type("T", (), {"time": time})()

    g = Game(headless=True, seed=1, daynight="night")
    ow = OverworldScene(g)
    g.push(ow)
    assert ow._time_ok(trig("")) is True              # no restriction
    assert ow._time_ok(trig("night")) is True         # matches current phase
    assert ow._time_ok(trig("day")) is False          # wrong phase -> blocked
    assert ow._time_ok(trig("evening,night")) is True  # phase list
    pygame.quit()


@pytest.mark.skipif(not _REAL, reason="needs full game data + region")
def test_overworld_and_battle_render_at_night():
    """Tinting must not crash the overworld or the battle backdrop."""
    import pygame

    from pkmn.core.pokemon import PokemonState
    from pkmn.game.battle_scene import BattleScene
    from pkmn.game.overworld import OverworldScene
    from pkmn.game.scene import Game

    g = Game(headless=True, seed=1, daynight="night")
    ow = OverworldScene(g)
    g.push(ow)
    ow.draw(g.canvas)                                  # overworld tint path
    wild = PokemonState.generate(g.data, g.state.party[0].species_id, 5,
                                 rng=g.state.rng)
    bs = BattleScene(g, [wild], wild=True)
    bs._draw_backdrop(g.canvas)                        # battle tint path
    assert g.time_phase() == "night"
    pygame.quit()
