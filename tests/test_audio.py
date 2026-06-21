"""Audio: procedural synthesis, the AudioManager, MIDI export, and the
scene hooks. SDL is forced to dummy drivers so the mixer initializes (and
runs silently) without a soundcard."""
import os

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import struct                                              # noqa: E402

import numpy as np                                         # noqa: E402
import pytest                                              # noqa: E402

pytest.importorskip("pygame")

from pkmn.game import audio                                # noqa: E402
from pkmn.game.audio import (AudioManager, SFX_NAMES, SONGS, cry_buffer,  # noqa: E402
                             export_songs_to_midi, note_midi, render_song,
                             _sfx)

_REAL = os.path.exists("game/data/species")


# ── note math ────────────────────────────────────────────────────────
def test_note_midi():
    assert note_midi("C4") == 60
    assert note_midi("A4") == 69
    assert note_midi("C5") == 72
    assert note_midi("F#3") == 54
    assert note_midi("Bb3") == 58


# ── synthesis buffers ────────────────────────────────────────────────
def test_cry_buffer_unique_deterministic_and_shaped():
    a, b = cry_buffer(1), cry_buffer(2)
    assert a.ndim == 1 and a.size > 1000
    assert float(np.abs(a).max()) > 0.1
    assert not np.array_equal(a, b)               # different dex -> different cry
    assert np.array_equal(cry_buffer(7), cry_buffer(7))   # same dex -> identical


def test_all_sfx_generate():
    for name in SFX_NAMES:
        buf = _sfx(name, np.random.RandomState(0))
        assert buf.size > 0, name
        assert np.isfinite(buf).all(), name
        assert float(np.abs(buf).max()) <= 1.0001, name


def test_all_songs_render_normalized_stereo():
    for name in SONGS:
        st = render_song(name)
        assert st.ndim == 2 and st.shape[1] == 2, name
        assert st.shape[0] > 1000, name
        assert float(np.abs(st).max()) <= 1.0, name


# ── MIDI export ──────────────────────────────────────────────────────
def test_midi_export_is_valid_smf(tmp_path):
    paths = export_songs_to_midi(str(tmp_path))
    assert len(paths) == len(SONGS)
    for p in paths:
        with open(p, "rb") as fh:
            raw = fh.read()
        assert raw[:4] == b"MThd"
        size, fmt, ntrk, div = struct.unpack(">IHHH", raw[4:14])
        assert (size, fmt, div) == (6, 1, 480)
        assert ntrk >= 2                          # tempo track + >=1 part
        assert raw.count(b"MTrk") == ntrk
        assert raw.endswith(b"\xff\x2f\x00")      # ends on end-of-track


# ── the manager ──────────────────────────────────────────────────────
@pytest.fixture
def am():
    return AudioManager(game_dir="", manifest={})


def test_manager_enabled_under_dummy(am):
    assert am.enabled
    assert audio.RATE > 0 and audio.CHANNELS in (1, 2)


def test_manager_play_paths_no_crash(am):
    am.play_sfx("hit")
    am.play_sfx("menu_move")
    am.play_cry(25)
    am.play_music("battle_wild")
    assert am._music_name == "battle_wild"
    am.play_music("route")
    assert am._music_name == "route"
    am.stop_music()
    assert am._music_name is None


def test_manager_unknown_song_is_safe(am):
    am.play_music("does-not-exist")               # no file, not in SONGS -> no-op
    am.play_sfx("")                               # empty name -> no-op


def test_manager_caches_sounds(am):
    am.play_sfx("hit")
    am.play_sfx("hit")
    assert "hit" in am._sfx_cache
    am.play_cry(7)
    assert 7 in am._cry_cache


def test_manager_mute(am):
    am.set_muted(True)
    assert am.muted
    am.play_sfx("hit")                            # muted -> silent, no crash
    am.play_cry(1)
    assert am.toggle_mute() is False


def test_disabled_manager_is_no_op():
    am = AudioManager(game_dir="", manifest={})
    am.enabled = False                            # emulate a device-less host
    am.play_sfx("hit")
    am.play_cry(1)
    am.play_music("route")
    am.stop_music()                               # all must be safe no-ops


# ── scene hooks ──────────────────────────────────────────────────────
@pytest.mark.skipif(not _REAL, reason="needs full game data + region")
def test_battle_scene_requests_music_and_fires_cries():
    import pygame

    from pkmn.core.pokemon import PokemonState
    from pkmn.game.battle_scene import BattleScene
    from pkmn.game.overworld import OverworldScene
    from pkmn.game.scene import Game

    g = Game(headless=True, seed=5)
    g.push(OverworldScene(g))                      # triggers map music (real mgr)
    calls = {"music": [], "cry": [], "sfx": []}
    g.audio.play_music = lambda name, loop=True: calls["music"].append(name)
    g.audio.play_cry = lambda seed: calls["cry"].append(seed)
    g.audio.play_sfx = lambda name: calls["sfx"].append(name)

    wild = PokemonState.generate(g.data, g.state.party[0].species_id, 5,
                                 rng=g.state.rng)
    bs = BattleScene(g, [wild], wild=True)
    g.push(bs)
    assert "battle_wild" in calls["music"]         # wild battle music started
    assert any(s.get("cry") for s in bs.steps)     # send-out cries are queued

    for _ in range(2000):                          # drive the opening timeline
        bs.update()
        if calls["cry"]:
            break
    assert calls["cry"], "send-out cry never fired"
    pygame.quit()


@pytest.mark.skipif(not _REAL, reason="needs full game data + region")
def test_overworld_plays_map_music():
    import pygame

    from pkmn.game.overworld import OverworldScene
    from pkmn.game.scene import Game

    g = Game(headless=True, seed=5)
    calls = []
    ow = OverworldScene(g)
    g.audio.play_music = lambda name, loop=True: calls.append(name)
    g.push(ow)
    ow.on_resume()                                 # e.g. returning from a menu
    assert calls, "overworld did not request map music on resume"
    pygame.quit()


@pytest.mark.skipif(not _REAL, reason="needs full game data + region")
def test_overworld_bump_sound_is_throttled():
    import pygame

    from pkmn.game.config import DOWN
    from pkmn.game.overworld import OverworldScene
    from pkmn.game.scene import Game

    g = Game(headless=True, seed=5)
    ow = OverworldScene(g)
    g.push(ow)
    calls = []
    g.audio.play_sfx = lambda name: calls.append(name)
    ow._walkable = lambda x, y: False                  # everything is solid
    ow._has_ledge = lambda x, y, d: False
    ow.moving, ow.bump_cool, ow.turn_cool = False, 0, 0
    g.state.facing = DOWN
    inp = type("I", (), {"pressed": set(), "held": {DOWN}})()
    ow.handle(inp)
    assert calls.count("bump") == 1                    # bumped the wall once
    ow.handle(inp)
    assert calls.count("bump") == 1                    # throttled: no rapid repeat
    pygame.quit()


@pytest.mark.skipif(not _REAL, reason="needs full game data + region")
def test_overworld_talk_sound_on_interact():
    import pygame

    from pkmn.game.config import DIRS, DOWN
    from pkmn.game.overworld import Npc, OverworldScene
    from pkmn.game.scene import Game

    g = Game(headless=True, seed=5)
    ow = OverworldScene(g)
    g.push(ow)
    calls = []
    g.audio.play_sfx = lambda name: calls.append(name)
    st = g.state
    st.facing = DOWN
    dx, dy = DIRS[DOWN]
    front = (st.tile[0] + dx, st.tile[1] + dy)
    spawn = type("S", (), {"tile": front, "name": "Greeter", "facing": "up",
                           "dialog": ["Hi!"], "heal": False, "script": ""})()
    ow.npcs = [Npc(spawn)]
    ow._interact()
    assert "confirm" in calls                          # speaking blips
    pygame.quit()


@pytest.mark.skipif(not _REAL, reason="needs full game data + region")
def test_dialogue_advance_blip():
    import pygame

    from pkmn.game.config import A
    from pkmn.game.dialog import DialogScene
    from pkmn.game.scene import Game

    g = Game(headless=True, seed=5)
    calls = []
    g.audio.play_sfx = lambda name: calls.append(name)
    dlg = DialogScene(g, ["First page.", "Second page."])
    g.push(dlg)
    dlg.handle(type("I", (), {"pressed": {A}, "held": set()})())
    assert "menu_move" in calls                         # advancing text blips
    pygame.quit()
