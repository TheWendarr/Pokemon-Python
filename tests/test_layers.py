"""Multi-layer map support (engine_version 2): collision is OR'd across
all tile layers, `over` tiles render in the above-player pass, and a
non-16px (e.g. 32px RMXP) tileset loads and scales correctly."""
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytest

from PIL import Image

from pkmn.game.config import TILE
from pkmn.game.tilemap import TileMap

GREEN = (10, 200, 10)
RED = (200, 10, 10)


def _build(tmp, tile_px=32):
    """A 3x3 map: a full GREEN ground layer plus an 'over' layer holding a
    single RED tile (flagged blocked + over) at (1,1)."""
    maps = tmp / "maps"
    maps.mkdir()
    # tileset image: tile 0 = green (plain), tile 1 = red (blocked + over)
    img = Image.new("RGB", (tile_px * 2, tile_px))
    for x in range(tile_px):
        for y in range(tile_px):
            img.putpixel((x, y), GREEN)
            img.putpixel((x + tile_px, y), RED)
    img.save(tmp / "tiles.png")
    (tmp / "tiles.tsx").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<tileset version="1.10" name="t" tilewidth="{tile_px}" '
        f'tileheight="{tile_px}" tilecount="2" columns="2">\n'
        f' <image source="tiles.png" width="{tile_px*2}" height="{tile_px}"/>\n'
        f' <tile id="1"><properties>'
        f'<property name="blocked" type="bool" value="true"/>'
        f'<property name="over" type="bool" value="true"/>'
        f'</properties></tile>\n</tileset>\n')
    ground = "\n".join("1,1,1," for _ in range(2)) + "\n1,1,1"
    over = "0,0,0,\n0,2,0,\n0,0,0"          # red tile at (1,1)
    (maps / "m.tmx").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<map version="1.10" orientation="orthogonal" renderorder="right-down" '
        f'width="3" height="3" tilewidth="{tile_px}" tileheight="{tile_px}" '
        f'infinite="0" nextobjectid="2">\n'
        f' <tileset firstgid="1" source="../tiles.tsx"/>\n'
        f' <layer id="1" name="ground" width="3" height="3"><data encoding="csv">\n'
        f'{ground}\n</data></layer>\n'
        f' <layer id="2" name="over" width="3" height="3"><data encoding="csv">\n'
        f'{over}\n</data></layer>\n'
        f' <objectgroup id="3" name="objects">\n'
        f'  <object id="1" name="spawn" x="0" y="0" width="{tile_px}" '
        f'height="{tile_px}"/>\n'
        f' </objectgroup>\n</map>\n')


@pytest.fixture
def tm(tmp_path):
    pygame.init()
    pygame.display.set_mode((64, 64))
    _build(tmp_path)
    return TileMap("m", root=str(tmp_path))


def test_all_tile_layers_loaded(tm):
    assert len(tm.tile_layers) == 2


def test_collision_ord_across_layers(tm):
    # blocked tile lives on the upper layer; the cell must still block.
    assert tm.blocked(1, 1) is True
    # ground-only cells are walkable.
    assert tm.blocked(0, 0) is False
    assert tm.blocked(2, 2) is False


def test_over_tile_renders_only_in_above_pass(tm):
    below = pygame.Surface((TILE, TILE))
    below.fill((0, 0, 0))
    tm.draw_cell(below, 1, 1, 0, 0, over=False)   # ground shows, red deferred

    above = pygame.Surface((TILE, TILE))
    above.fill((0, 0, 0))
    tm.draw_cell(above, 1, 1, 0, 0, over=True)    # only the red `over` tile

    c = TILE // 2
    assert below.get_at((c, c))[:3] == GREEN
    assert above.get_at((c, c))[:3] == RED


def test_non_16px_tiles_scale_to_render_size(tm):
    # tiles authored at 32px must upscale to the render TILE size.
    img = tm._cell_image(0, 0, tm.tile_layers[0])
    assert img is not None
    assert img.get_size() == (TILE, TILE)


def _build_dir(tmp, tile_px=32):
    """A 1x1 ground map plus a tile flagged `block_up` only."""
    maps = tmp / "maps"
    maps.mkdir()
    img = Image.new("RGB", (tile_px * 2, tile_px), GREEN)
    img.save(tmp / "tiles.png")
    (tmp / "tiles.tsx").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<tileset version="1.10" name="t" tilewidth="{tile_px}" '
        f'tileheight="{tile_px}" tilecount="2" columns="2">\n'
        f' <image source="tiles.png" width="{tile_px*2}" height="{tile_px}"/>\n'
        f' <tile id="1"><properties>'
        f'<property name="block_up" type="bool" value="true"/>'
        f'</properties></tile>\n</tileset>\n')
    (maps / "d.tmx").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<map version="1.10" orientation="orthogonal" renderorder="right-down" '
        f'width="1" height="1" tilewidth="{tile_px}" tileheight="{tile_px}" '
        f'infinite="0" nextobjectid="1">\n'
        f' <tileset firstgid="1" source="../tiles.tsx"/>\n'
        f' <layer id="1" name="ground" width="1" height="1">'
        f'<data encoding="csv">2</data></layer>\n'
        f' <objectgroup id="2" name="objects"/>\n</map>\n')


def test_directional_passability(tmp_path):
    pygame.init()
    pygame.display.set_mode((64, 64))
    _build_dir(tmp_path)
    tm = TileMap("d", root=str(tmp_path))
    # block_up: cannot cross upward, every other direction is open.
    assert tm.passable(0, 0, "up") is False
    assert tm.passable(0, 0, "down") is True
    assert tm.passable(0, 0, "left") is True
    assert tm.passable(0, 0, "right") is True
    # the tile is not fully solid -- a mover may still stand on it.
    assert tm.blocked(0, 0) is False
