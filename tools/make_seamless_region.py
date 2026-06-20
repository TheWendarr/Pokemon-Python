"""Build the 'Vale' demo region: three small maps stitched into one
continuous overworld with edge connections + offsets (the seamless
primitive from docs/ENGINE_PHILOSOPHY.md). Open grass seams let you walk
between maps with no transition; unconnected edges show a grass border.

    meadow  --south/north-->  glade  --east(+1)/west(-1)-->  dell

Authoring-only: writes the game-folder format (tileset, sprites, maps,
manifest). No engine code lives in the output.

    python tools/make_seamless_region.py
"""
from __future__ import annotations

import json
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
import pygame  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import art  # noqa: E402

OUT = "examples/seamless"
T = 16
GRASS, PATH, TREE, FLOWER, TALL, WATER, LEDGE, CUT = range(8)
BLOCKED = {TREE, WATER, CUT}                            # CUT blocks until cut
GRASS_GID = GRASS + 1                                   # for the border prop


def _ledge(s):
    """A grassy tile with a shadowed drop at its base (a one-way ledge)."""
    GRND = (104, 170, 104)
    art.grass(s, GRND, seed=LEDGE)
    w = s.get_width()
    lip = int(w * 0.6)
    for x in range(w):
        s.set_at((x, lip), (214, 228, 204))            # bright edge
    for y in range(lip + 1, w):
        for x in range(w):
            c = s.get_at((x, y))
            s.set_at((x, y), (max(0, c[0] - 64), max(0, c[1] - 58),
                              max(0, c[2] - 46)))


def make_tiles() -> None:
    sheet = pygame.Surface((8 * T, T))
    cell = lambda i: sheet.subsurface((i * T, 0, T, T))
    GRND = (104, 170, 104)
    art.grass(cell(GRASS), GRND, seed=GRASS)
    art.path(cell(PATH), (202, 182, 134), seed=PATH)
    art.tree(cell(TREE), GRND, seed=TREE)
    art.flower(cell(FLOWER), GRND, seed=FLOWER)
    art.tall_grass(cell(TALL), (86, 148, 86), seed=TALL)
    art.water(cell(WATER), (60, 122, 192), seed=WATER)
    _ledge(cell(LEDGE))
    art.tree(cell(CUT), GRND, seed=CUT, leaf=(126, 196, 96))   # cuttable bush
    pygame.image.save(sheet, f"{OUT}/tiles.png")

    flags = {TREE: ["blocked"], WATER: ["blocked", "surf"],
             CUT: ["blocked", "cuttable"], TALL: ["grass"],
             LEDGE: ["ledge_down"]}
    props = []
    for t in sorted(flags):
        ps = "".join(f'<property name="{f}" type="bool" value="true"/>'
                     for f in flags[t])
        props.append(f'  <tile id="{t}"><properties>{ps}</properties></tile>')
    open(f"{OUT}/tiles.tsx", "w").write(
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<tileset version="1.10" name="vale" tilewidth="{T}" tileheight="{T}"'
        f' tilecount="8" columns="8">\n'
        f' <image source="tiles.png" width="{8*T}" height="{T}"/>\n'
        + "\n".join(props) + "\n</tileset>\n")


def make_sprites() -> None:
    pygame.image.save(art.character_sheet(
        skin=(226, 190, 152), hair=(54, 40, 32),
        shirt=(70, 130, 196), pants=(56, 72, 96)), f"{OUT}/player.png")
    pygame.image.save(art.character_sheet(
        skin=(208, 168, 132), hair=(40, 44, 50),
        shirt=(196, 96, 96), pants=(70, 64, 70)), f"{OUT}/npc.png")


def blank(w, h):
    """A grass field walled with trees on every edge."""
    g = [[GRASS] * w for _ in range(h)]
    for x in range(w):
        g[0][x] = g[h - 1][x] = TREE
    for y in range(h):
        g[y][0] = g[y][w - 1] = TREE
    return g


def open_edge(g, edge):
    """Reopen one walled edge to grass so a seam can be crossed."""
    w, h = len(g[0]), len(g)
    if edge == "north":
        for x in range(1, w - 1):
            g[0][x] = GRASS
    elif edge == "south":
        for x in range(1, w - 1):
            g[h - 1][x] = GRASS
    elif edge == "west":
        for y in range(1, h - 1):
            g[y][0] = GRASS
    elif edge == "east":
        for y in range(1, h - 1):
            g[y][w - 1] = GRASS


def tmx(name, grid, objects, map_props) -> None:
    h, w = len(grid), len(grid[0])
    csv = ",\n".join(",".join(str(c + 1) for c in row) for row in grid)
    mp = "".join(
        f'<property name="{k}"'
        + (f' type="int" value="{v}"' if isinstance(v, int)
           and not isinstance(v, bool) else f' value="{v}"') + "/>"
        for k, v in map_props.items())
    objs = []
    for i, (oname, tx, ty, props) in enumerate(objects, 1):
        ps = "".join(
            f'<property name="{k}"'
            + (f' type="int" value="{v}"' if isinstance(v, int)
               and not isinstance(v, bool) else f' value="{v}"') + "/>"
            for k, v in props.items())
        objs.append(f'  <object id="{i}" name="{oname}" x="{tx*T}" y="{ty*T}"'
                    f' width="{T}" height="{T}"><properties>{ps}</properties>'
                    f'</object>')
    open(f"{OUT}/maps/{name}.tmx", "w").write(
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<map version="1.10" orientation="orthogonal" renderorder="right-down"'
        f' width="{w}" height="{h}" tilewidth="{T}" tileheight="{T}"'
        f' infinite="0" nextobjectid="99">\n'
        f' <properties>{mp}</properties>\n'
        f' <tileset firstgid="1" source="../tiles.tsx"/>\n'
        f' <layer id="1" name="ground" width="{w}" height="{h}">\n'
        f'  <data encoding="csv">\n{csv}\n</data>\n </layer>\n'
        f' <objectgroup id="2" name="objects">\n' + "\n".join(objs) +
        f'\n </objectgroup>\n</map>\n')


def make_meadow() -> None:                              # 20x16, top
    g = blank(20, 16)
    open_edge(g, "south")                               # seam down to glade
    for x in range(8, 12):                              # path to the seam
        g[14][x] = g[15][x] = PATH
    for x, y in ((4, 4), (15, 5), (5, 11), (16, 11)):
        g[y][x] = FLOWER
    for y in range(3, 6):                               # a little grove
        for x in range(13, 16):
            g[y][x] = TALL
    for x in range(8, 12):                              # one-way ledge (jump S)
        g[9][x] = LEDGE
    objects = [("spawn", 10, 6, {}),
               ("sign", 13, 6, {"dialog": "VALE MEADOW.|Hop the ledge, keep"
                                          " south - the world doesn't stop."})]
    tmx("meadow", g, objects,
        {"connect_south": "glade", "offset_south": 0, "border": GRASS_GID})


def make_glade() -> None:                               # 20x16, middle
    g = blank(20, 16)
    open_edge(g, "north")                               # seam up to meadow
    open_edge(g, "east")                                # seam right to dell
    for x in range(8, 12):
        g[0][x] = g[1][x] = PATH
    for y in range(6, 11):                              # encounter band
        for x in range(5, 14):
            g[y][x] = TALL
    for y in range(11, 14):                             # surfable pond (SW)
        for x in range(2, 6):
            g[y][x] = WATER
    objects = [("spawn", 10, 8, {}),
               ("npc", 6, 4, {"display": "Ranger", "facing": "down",
                              "dialog": "Ranger: Meadow's north, dell's east."
                                        "|Same continuous world."})]
    tmx("glade", g, objects,
        {"connect_north": "meadow", "offset_north": 0,
         "connect_east": "dell", "offset_east": 1, "border": GRASS_GID})


def make_dell() -> None:                                # 16x14, east, shifted
    g = blank(16, 14)
    open_edge(g, "west")                                # seam left to glade
    for y in range(5, 9):
        for x in range(3, 9):
            g[y][x] = FLOWER if (x + y) % 2 else GRASS
    for x, y in ((11, 3), (12, 9), (4, 11)):
        g[y][x] = TALL
    g[6][10] = CUT                                      # cut to reach the east
    g[7][10] = CUT
    objects = [("spawn", 3, 6, {}),
               ("sign", 3, 4, {"dialog": "DELL.|A bush blocks the east."
                                         " Face it and Cut."})]
    tmx("dell", g, objects,
        {"connect_west": "glade", "offset_west": -1, "border": GRASS_GID})


def make_data() -> None:
    json.dump({
        "engine_version": 1,
        "name": "Vale (seamless demo)",
        "start": {"map": "meadow", "tile": [10, 6], "facing": "down"},
        "starter": {"species": "chikorita", "level": 8},
        "bag": {"potion": 3, "poke-ball": 5},
        "money": 600,
        "flags": ["can_surf", "can_cut"],
        "dex": ["chikorita", "bayleef", "sentret", "hoothoot", "caterpie",
                "pidgey", "rattata", "sunkern", "hoppip"],
    }, open(f"{OUT}/game.json", "w"), indent=1)
    json.dump({
        "meadow": [{"species": "sentret", "min": 3, "max": 5, "weight": 60},
                   {"species": "hoothoot", "min": 3, "max": 5, "weight": 40}],
        "glade": [{"species": "hoppip", "min": 4, "max": 6, "weight": 50},
                  {"species": "sunkern", "min": 4, "max": 6, "weight": 50}],
        "dell": [{"species": "pidgey", "min": 4, "max": 6, "weight": 55},
                 {"species": "caterpie", "min": 3, "max": 5, "weight": 45}],
    }, open(f"{OUT}/encounters.json", "w"), indent=1)


def main() -> None:
    pygame.init()
    pygame.display.set_mode((32, 32))
    os.makedirs(f"{OUT}/maps", exist_ok=True)
    make_tiles()
    make_sprites()
    make_meadow()
    make_glade()
    make_dell()
    make_data()
    print("seamless demo region written to", OUT)


if __name__ == "__main__":
    main()
