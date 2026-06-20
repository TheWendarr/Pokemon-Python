"""Gen 5 sprite caching: path layout, cache hits, offline fallback, and
Assets.battler() loading real sprites vs. the placeholder blob. These
never touch the network (fetching is opt-in and left off); one live
download test is gated behind PKMN_TEST_NETWORK=1."""
import os

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pytest

pytest.importorskip("pygame")
import pygame  # noqa: E402

from pkmn.game import sprites                       # noqa: E402
from pkmn.game.assets import Assets                 # noqa: E402
from pkmn.game.config import SPRITE_PX              # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _pygame():
    pygame.init()
    pygame.display.set_mode((32, 32))
    pygame.font.init()
    yield
    pygame.quit()


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    monkeypatch.setattr(sprites, "FETCH_ENABLED", False)


def _seed(cache_dir, dex, *, back=False, size=96):
    """Write a fake sprite into the cache so loads need no network."""
    path = sprites.cache_path(dex, back=back, cache_dir=cache_dir)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    surf.fill((10, 20, 30, 255) if not back else (200, 60, 60, 255))
    pygame.image.save(surf, path)
    return path


# ── cache path + lookup ──────────────────────────────────────────────

def test_cache_path_layout(tmp_path):
    front = sprites.cache_path(498, cache_dir=str(tmp_path))
    back = sprites.cache_path(498, back=True, cache_dir=str(tmp_path))
    assert front.endswith(os.path.join("gen5", "front", "498.png"))
    assert back.endswith(os.path.join("gen5", "back", "498.png"))


def test_sprite_path_cache_hit_no_network(tmp_path, monkeypatch):
    monkeypatch.setenv("PKMN_SPRITE_CACHE", str(tmp_path))
    seeded = _seed(str(tmp_path), 498)
    assert sprites.sprite_path(498) == seeded            # found, no fetch
    assert sprites.sprite_path(498, back=True) is None   # not seeded, fetch off


def test_sprite_path_miss_without_fetch(tmp_path, monkeypatch):
    monkeypatch.setenv("PKMN_SPRITE_CACHE", str(tmp_path))
    assert sprites.sprite_path(999) is None
    assert sprites.sprite_path(0) is None                # no dex


def test_env_var_force_disables_fetch(tmp_path, monkeypatch):
    monkeypatch.setattr(sprites, "FETCH_ENABLED", True)
    monkeypatch.setenv("PKMN_NO_SPRITE_FETCH", "1")
    monkeypatch.setenv("PKMN_SPRITE_CACHE", str(tmp_path))
    assert sprites.sprite_path(498) is None              # would-be miss, no net


# ── Assets.battler() ─────────────────────────────────────────────────

def test_battler_loads_real_sprite_scaled(tmp_path, monkeypatch):
    monkeypatch.setenv("PKMN_SPRITE_CACHE", str(tmp_path))
    _seed(str(tmp_path), 498, back=False)
    _seed(str(tmp_path), 498, back=True)
    assets = Assets("game/assets")
    front = assets.battler("tepig", "Tepig", dex=498, back=False)
    back = assets.battler("tepig", "Tepig", dex=498, back=True)
    assert front.get_size() == (SPRITE_PX, SPRITE_PX)    # 96 -> 64
    assert back.get_size() == (SPRITE_PX, SPRITE_PX)
    # front and back are cached separately and differ
    assert front is not back
    assert assets.battler("tepig", "Tepig", dex=498) is front   # memoized


def test_battler_placeholder_when_uncached_and_offline(tmp_path, monkeypatch):
    monkeypatch.setenv("PKMN_SPRITE_CACHE", str(tmp_path))
    assets = Assets("game/assets")
    blob = assets.battler("zubat", "Zubat", dex=41)      # not cached, fetch off
    assert blob.get_size() == (SPRITE_PX, SPRITE_PX)     # hashed-hue blob
    # and with no dex at all
    assert assets.battler("nodex", "X").get_size() == (SPRITE_PX, SPRITE_PX)


def test_battler_distinct_sprites_per_species(tmp_path, monkeypatch):
    monkeypatch.setenv("PKMN_SPRITE_CACHE", str(tmp_path))
    assets = Assets("game/assets")
    a = assets.battler("abra", "Abra", dex=63)
    b = assets.battler("gastly", "Gastly", dex=92)
    assert a is not b                                    # different hue blobs


# ── opt-in live download (skipped unless PKMN_TEST_NETWORK=1) ─────────

@pytest.mark.skipif(os.environ.get("PKMN_TEST_NETWORK") != "1",
                    reason="set PKMN_TEST_NETWORK=1 to hit the network")
def test_live_fetch_real_gen5_sprite(tmp_path, monkeypatch):
    monkeypatch.setattr(sprites, "FETCH_ENABLED", True)
    monkeypatch.setenv("PKMN_SPRITE_CACHE", str(tmp_path))
    path = sprites.sprite_path(495)                      # Snivy, front
    assert path and os.path.exists(path)
    with open(path, "rb") as f:
        assert f.read(8).startswith(b"\x89PNG")
    # second call is a pure cache hit even with fetching off
    monkeypatch.setattr(sprites, "FETCH_ENABLED", False)
    assert sprites.sprite_path(495) == path


# ── animated character sheets (walk cycle) ───────────────────────────

def test_animated_character_sheet_layout():
    from pkmn.game.config import BASE_TILE, SCALE, TILE
    a = Assets("game/assets")                        # 16px-authored grid
    # frames are upscaled to the render size at load
    assert a.player_h == 24 * SCALE                   # 96 (taller than tile)
    fw, fh = BASE_TILE * SCALE, 24 * SCALE
    for facing in ("down", "up", "left", "right"):
        assert len(a.player[facing]) == 4             # 4 walk frames
        assert a.player[facing][0].get_size() == (fw, fh)
    assert a.player_h > TILE                           # stands above its tile
    assert len(a.npc["down"]) == 4


def test_legacy_strip_still_loads(tmp_path):
    import pygame
    strip = pygame.Surface((64, 16), pygame.SRCALPHA)
    strip.fill((10, 20, 30, 255))
    for name in ("player.png", "npc.png"):
        pygame.image.save(strip, str(tmp_path / name))
    from pkmn.game.config import TILE
    a = Assets(str(tmp_path))
    assert a.player_h == TILE                          # legacy frame -> render size
    assert len(a.player["down"]) == 1
    assert a.player["down"][0].get_size() == (TILE, TILE)


def test_walk_frame_cycle():
    from pkmn.game.overworld import OverworldScene
    from pkmn.game.config import TILE
    d = TILE // 2                                      # frame period (px)
    f = OverworldScene._frame_idx
    assert f(0.0, False, 4) == 0                       # idle -> stand
    assert f(100.0, True, 1) == 0                      # single-frame sheet
    assert f(0.0, True, 4) == 0                        # start of a step
    assert f(d * 1.0, True, 4) == 1                    # advances...
    assert f(d * 2.0, True, 4) == 2
    assert f(d * 3.0, True, 4) == 3
    assert f(d * 4.0, True, 4) == 0                    # wraps


# ── 1080p / resolution-independent presentation ──────────────────────

def test_fit_is_integer_and_aspect_correct():
    from pkmn.game.scene import Game
    from pkmn.game.config import LOGICAL_W, LOGICAL_H
    # 1080p, pixel-perfect: largest integer 4:3 fit of the 1024x768 canvas
    dw, dh, ox, oy = Game._fit(1920, 1080)
    assert (dw, dh) == (LOGICAL_W, LOGICAL_H)         # 1x at 1080p
    assert (ox, oy) == ((1920 - LOGICAL_W) // 2, (1080 - LOGICAL_H) // 2)
    for win in [(2048, 1536), (3840, 2160), (1024, 768), (5000, 4000)]:
        dw, dh, ox, oy = Game._fit(*win)
        scale = dw // LOGICAL_W
        assert dw == LOGICAL_W * scale and dh == LOGICAL_H * scale
        assert scale >= 1 and dw <= win[0] and dh <= win[1]
        assert abs(dw / dh - 4 / 3) < 1e-6           # never distorted
        assert ox == (win[0] - dw) // 2 and oy == (win[1] - dh) // 2
