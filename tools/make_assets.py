"""Generate every art/map asset the client needs, from code.

    python tools/make_assets.py

Outputs into game/assets/: tiles.png + tiles.tsx, player.png, npc.png,
maps/town.tmx, maps/route1.tmx, encounters.json. Maps are plain Tiled
files, so they stay editable in the Tiled editor afterward.
"""
from __future__ import annotations

import json
import os
import random

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import sys

import pygame  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import art  # noqa: E402

OUT = "game/assets"
T = 16

# tile ids (0-based in tsx; GID = id+1 in tmx)
(GRASS, TALL, PATH, WATER, TREE, WALL, ROOF, DOOR, FLOWER, FENCE, SIGN,
 SAND, FLOOR, WALL_INT, RUG, COUNTER) = range(16)
BLOCKED = {WATER, TREE, WALL, ROOF, FENCE, SIGN, WALL_INT, COUNTER}


def make_tiles() -> None:
    sheet = pygame.Surface((16 * T, T))

    def cell(i):
        return sheet.subsurface((i * T, 0, T, T))

    GR = (116, 180, 96)
    art.grass(cell(GRASS), GR, seed=GRASS)
    art.tall_grass(cell(TALL), GR, seed=TALL)
    art.path(cell(PATH), (210, 190, 140), seed=PATH)
    art.water(cell(WATER), (72, 132, 206), seed=WATER)
    art.tree(cell(TREE), GR, seed=TREE)
    art.brick_wall(cell(WALL))
    art.roof(cell(ROOF))
    door = cell(DOOR)
    art.brick_wall(door)
    pygame.draw.rect(door, (60, 40, 28), (5, 4, 6, 12))
    pygame.draw.rect(door, (94, 64, 44), (6, 5, 4, 11))
    pygame.draw.circle(door, (232, 200, 90), (9, 10), 1)
    art.flower(cell(FLOWER), GR, seed=FLOWER)
    art.fence(cell(FENCE), GR, seed=FENCE)
    art.sign(cell(SIGN), GR, seed=SIGN)
    art.sand(cell(SAND), (226, 204, 150), seed=SAND)
    art.floor(cell(FLOOR))
    art.brick_wall(cell(WALL_INT), base=(176, 154, 132))
    art.rug(cell(RUG))
    art.counter(cell(COUNTER))

    pygame.image.save(sheet, f"{OUT}/tiles.png")

    props = []
    for tid in sorted(BLOCKED):
        props.append(f'  <tile id="{tid}"><properties>'
                     f'<property name="blocked" type="bool" value="true"/>'
                     f'</properties></tile>')
    props.append(f'  <tile id="{TALL}"><properties>'
                 f'<property name="grass" type="bool" value="true"/>'
                 f'</properties></tile>')
    tsx = (f'<?xml version="1.0" encoding="UTF-8"?>\n'
           f'<tileset version="1.10" name="tiles" tilewidth="{T}" '
           f'tileheight="{T}" tilecount="16" columns="16">\n'
           f' <image source="tiles.png" width="{16*T}" height="{T}"/>\n'
           + "\n".join(props) + "\n</tileset>\n")
    open(f"{OUT}/tiles.tsx", "w").write(tsx)


def make_sprites() -> None:
    pygame.image.save(art.character_sheet(
        skin=(240, 206, 168), hair=(70, 50, 44),
        shirt=(196, 72, 72), pants=(60, 72, 110)), f"{OUT}/player.png")
    pygame.image.save(art.character_sheet(
        skin=(228, 186, 150), hair=(96, 72, 48),
        shirt=(70, 110, 200), pants=(70, 74, 86)), f"{OUT}/npc.png")


# ── maps ─────────────────────────────────────────────────────────────

def tmx(name, grid, objects) -> None:
    h, w = len(grid), len(grid[0])
    csv = ",\n".join(",".join(str(c + 1) for c in row) for row in grid)
    objs = []
    for i, (oname, tx, ty, props) in enumerate(objects, 1):
        ps = "".join(
            f'<property name="{k}"'
            + (f' type="int" value="{v}"' if isinstance(v, int) and not isinstance(v, bool)
               else f' type="bool" value="{str(v).lower()}"' if isinstance(v, bool)
               else f' value="{v}"') + "/>"
            for k, v in props.items())
        objs.append(f'  <object id="{i}" name="{oname}" x="{tx*T}" y="{ty*T}" '
                    f'width="{T}" height="{T}"><properties>{ps}</properties>'
                    f'</object>')
    doc = (f'<?xml version="1.0" encoding="UTF-8"?>\n'
           f'<map version="1.10" orientation="orthogonal" '
           f'renderorder="right-down" width="{w}" height="{h}" '
           f'tilewidth="{T}" tileheight="{T}" infinite="0" nextobjectid="99">\n'
           f' <tileset firstgid="1" source="../tiles.tsx"/>\n'
           f' <layer id="1" name="ground" width="{w}" height="{h}">\n'
           f'  <data encoding="csv">\n{csv}\n</data>\n </layer>\n'
           f' <objectgroup id="2" name="objects">\n' + "\n".join(objs) +
           f'\n </objectgroup>\n</map>\n')
    open(f"{OUT}/maps/{name}.tmx", "w").write(doc)


def make_town() -> None:
    w, h = 24, 18
    g = [[GRASS] * w for _ in range(h)]
    for x in range(w):
        g[0][x] = g[h - 1][x] = TREE
    for y in range(h):
        g[y][0] = g[y][w - 1] = TREE
    g[0][11] = g[0][12] = PATH                       # north gap -> route 1
    for y in range(1, 12):                            # main path
        g[y][11] = g[y][12] = PATH
    for x in range(4, 20):
        g[12][x] = PATH
    # house
    for x in range(4, 10):
        g[3][x] = ROOF
        g[4][x] = ROOF
        g[5][x] = WALL
        g[6][x] = WALL
    g[6][6] = DOOR
    g[7][6] = PATH
    # pond, flowers, fence, sign
    for y in (8, 9):
        for x in (16, 17, 18):
            g[y][x] = WATER
    for x, y in ((3, 14), (4, 15), (15, 14), (18, 14), (5, 9)):
        g[y][x] = FLOWER
    for x in range(14, 21):
        g[6][x] = FENCE
    g[8][9] = SIGN
    objects = [
        ("spawn", 11, 13, {}),
        ("warp", 11, 0, {"to_map": "route1", "to_x": 11, "to_y": 16,
                         "facing": "up"}),
        ("warp", 12, 0, {"to_map": "route1", "to_x": 12, "to_y": 16,
                         "facing": "up"}),
        ("npc", 8, 12, {"display": "Maple", "facing": "down",
                        "dialog": "Welcome to Hexton!|Tall grass north of "
                                  "town is full of wild Pokemon."}),
        ("warp", 6, 6, {"to_map": "house", "to_x": 4, "to_y": 4,
                        "facing": "up"}),
        ("sign", 9, 8, {"dialog": "HEXTON - Where small things add up."}),
    ]
    tmx("town", g, objects)


def make_route1() -> None:
    w, h = 24, 18
    g = [[GRASS] * w for _ in range(h)]
    for x in range(w):
        g[0][x] = g[h - 1][x] = TREE
    for y in range(h):
        g[y][0] = g[y][w - 1] = TREE
    g[h - 1][11] = g[h - 1][12] = PATH               # south gap -> town
    for y in range(2, h - 1):
        g[y][11] = g[y][12] = PATH
    for ys, xs in (((3, 7), (3, 9)), ((4, 8), (14, 21)),
                   ((9, 13), (2, 8)), ((10, 15), (15, 21))):
        for y in range(*ys):
            for x in range(*xs):
                g[y][x] = TALL
    for x, y in ((5, 8), (18, 3), (3, 15), (20, 13)):
        g[y][x] = TREE
    objects = [
        ("spawn", 11, 16, {}),
        ("warp", 11, 17, {"to_map": "town", "to_x": 11, "to_y": 1,
                          "facing": "down"}),
        ("warp", 12, 17, {"to_map": "town", "to_x": 12, "to_y": 1,
                          "facing": "down"}),
        ("sign", 11, 2, {"dialog": "ROUTE 1 - Hexton lies to the south."}),
        ("npc", 13, 5, {"display": "Hugh", "facing": "left",
                        "script": "rival_after"}),
        ("trigger", 11, 5, {"script": "rival_battle",
                            "unless_flag": "beat_rival"}),
        ("trigger", 12, 5, {"script": "rival_battle",
                            "unless_flag": "beat_rival"}),
        ("trainer", 18, 9, {"display": "Youngster Cole", "facing": "down",
                            "sight": 3, "party": "patrat:5|lillipup:5",
                            "prize": 300, "flag": "beat_cole",
                            "before": "Cole: My Pokemon and I never lose"
                                      " in the grass!",
                            "after": "Cole: I need to train more..."}),
    ]
    tmx("route1", g, objects)


def make_house() -> None:
    w, h = 9, 8
    g = [[FLOOR] * w for _ in range(h)]
    for x in range(w):
        g[0][x] = g[1][x] = WALL_INT
        g[h - 1][x] = WALL_INT
    for y in range(h):
        g[y][0] = g[y][w - 1] = WALL_INT
    for x in range(2, 7):
        g[3][x] = COUNTER
    g[6][4] = RUG                                    # exit mat
    objects = [
        ("spawn", 4, 4, {}),
        ("warp", 4, 6, {"to_map": "town", "to_x": 6, "to_y": 7,
                        "facing": "down"}),
        ("npc", 4, 2, {"display": "Nurse Hazel", "facing": "down",
                       "script": "nurse_heal"}),
        ("sign", 3, 3, {"dialog": "Hexton free clinic. All Pokemon welcome."}),
        ("sign", 6, 3, {"script": "pc_access"}),
    ]
    tmx("house", g, objects)


def make_scripts() -> None:
    json.dump({
        "nurse_heal": [
            {"say": "Nurse Hazel: Welcome!|Shall I heal your Pokemon?"},
            {"heal": True},
            {"say": "Nurse Hazel: There you go!|They're fighting fit again."},
        ],
        "rival_battle": [
            {"face_npc": {"name": "Hugh", "facing": "left"}},
            {"say": "Hugh: Hey! Hold up!|You got a Pokemon from the lab"
                    " too, right?|Let's see what it can do!"},
            {"battle": {"trainer": "Rival Hugh", "party": "snivy:8",
                        "prize": 500, "flag": "beat_rival"}},
            {"say": "Hugh: Hmph. Not bad at all.|Take care of that"
                    " partner of yours."},
            {"give_item": {"item": "potion", "qty": 2}},
            {"say": "Hugh handed over two Potions!"},
        ],
        "pc_access": [
            {"say": "Booting up the storage PC..."},
            {"pc": True},
        ],
        "rival_after": [
            {"if_flag": "beat_rival",
             "then": [{"say": "Hugh: I'm off to train.|Next time will be"
                              " different."}],
             "else": [{"say": "Hugh: ..."}]},
        ],
    }, open(f"{OUT}/scripts.json", "w"), indent=1)


def make_manifest() -> None:
    json.dump({
        "name": "Hexton (reference region)",
        "start": {"map": "town", "facing": "down"},
        "starter": {"species": "oshawott", "level": 12},
        "bag": {"potion": 5, "poke-ball": 10},
        "money": 1500,
    }, open(f"{OUT}/game.json", "w"), indent=1)


def make_encounters() -> None:
    json.dump({
        "route1": [
            {"species": "patrat", "min": 3, "max": 5, "weight": 35},
            {"species": "lillipup", "min": 3, "max": 5, "weight": 35},
            {"species": "purrloin", "min": 4, "max": 6, "weight": 20},
            {"species": "pidove", "min": 4, "max": 6, "weight": 10},
        ],
    }, open(f"{OUT}/encounters.json", "w"), indent=1)


def main() -> None:
    pygame.init()
    pygame.display.set_mode((32, 32))
    os.makedirs(f"{OUT}/maps", exist_ok=True)
    make_tiles()
    make_sprites()
    make_town()
    make_route1()
    make_house()
    make_scripts()
    make_manifest()
    make_encounters()
    print("assets written to", OUT)


if __name__ == "__main__":
    main()
