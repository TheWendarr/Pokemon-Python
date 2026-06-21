"""Location/terrain battle backdrops: palette table, the map -> game ->
battle wiring, and crash-free rendering for every biome."""
import os

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pytest                                              # noqa: E402

from pkmn.game.battle_scene import _BACKDROPS, _WEATHER_SKY   # noqa: E402

_REAL = os.path.exists("game/data/species")


def test_backdrop_palette_table():
    for key in ("field", "forest", "cave", "water", "sand", "snow"):
        assert key in _BACKDROPS
    for sky, ground in _BACKDROPS.values():
        assert len(sky) == 3 and len(ground) == 3
    assert set(_WEATHER_SKY) == {"rain", "sun", "sandstorm", "hail"}


@pytest.mark.skipif(not _REAL, reason="needs full game data + region")
def test_battle_scene_reads_game_battle_bg():
    import pygame

    from pkmn.core.pokemon import PokemonState
    from pkmn.game.battle_scene import BattleScene
    from pkmn.game.scene import Game

    g = Game(headless=True, seed=1)
    assert g.battle_bg == "field"
    wild = PokemonState.generate(g.data, g.state.party[0].species_id, 5,
                                 rng=g.state.rng)
    g.battle_bg = "cave"
    assert BattleScene(g, [wild], wild=True).backdrop == "cave"
    # an explicit backdrop overrides the game default
    assert BattleScene(g, [wild], wild=True, backdrop="snow").backdrop == "snow"
    pygame.quit()


@pytest.mark.skipif(not _REAL, reason="needs full game data + region")
def test_overworld_sets_battle_bg_from_map():
    import pygame

    from pkmn.game.overworld import OverworldScene
    from pkmn.game.scene import Game

    g = Game(headless=True, seed=1, game_dir="examples/triad")
    ow = OverworldScene(g)
    g.push(ow)
    ow.load_map("route_shoreline")
    assert g.battle_bg == "water"           # from the map's battle_bg property
    ow.load_map("verdant")                  # a map without the property
    assert g.battle_bg == "field"           # falls back to the default
    pygame.quit()


@pytest.mark.skipif(not _REAL, reason="needs full game data + region")
def test_every_biome_renders():
    import pygame

    from pkmn.core.pokemon import PokemonState
    from pkmn.game import sprites
    from pkmn.game.battle_scene import BattleScene
    from pkmn.game.overworld import OverworldScene
    from pkmn.game.scene import Game

    sprites.FETCH_ENABLED = False
    g = Game(headless=True, seed=1)
    g.push(OverworldScene(g))
    wild = PokemonState.generate(g.data, g.state.party[0].species_id, 5,
                                 rng=g.state.rng)
    for bg in _BACKDROPS:
        BattleScene(g, [wild], wild=True, backdrop=bg)._draw_backdrop(g.canvas)
    pygame.quit()
