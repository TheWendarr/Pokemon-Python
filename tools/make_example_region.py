"""Build the Isleton example region into examples/isleton/ using ONLY
the game-folder format: its own tileset, sprites, maps, manifest,
scripts, and encounters. No engine code lives in the output folder —
this script is the 'authoring tool', the folder is the 'game'.

    python tools/make_example_region.py
"""
from __future__ import annotations

import json
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
import sys

import pygame  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import art  # noqa: E402

OUT = "examples/isleton"
T = 16

SAND, GRASS, SEA, PALM, PLANK, ROCK, SHELL, MAT = range(8)
BLOCKED = {SEA, PALM, ROCK, SHELL}


def make_tiles() -> None:
    sheet = pygame.Surface((8 * T, T))

    def cell(i):
        return sheet.subsurface((i * T, 0, T, T))

    SND = (236, 220, 178)
    art.sand(cell(SAND), SND, seed=SAND)
    art.grass(cell(GRASS), (110, 178, 110), seed=GRASS)
    art.water(cell(SEA), (52, 120, 190), seed=SEA)
    art.palm(cell(PALM), SND, seed=PALM)
    art.plank(cell(PLANK), base=(196, 156, 104))
    art.rock(cell(ROCK), SND, seed=ROCK)
    art.shell(cell(SHELL), SND, seed=SHELL)
    art.mat(cell(MAT), SND, color=(90, 130, 160))

    pygame.image.save(sheet, f"{OUT}/tiles.png")

    props = [f'  <tile id="{t}"><properties>'
             f'<property name="blocked" type="bool" value="true"/>'
             f'</properties></tile>' for t in sorted(BLOCKED)]
    props.append(f'  <tile id="{GRASS}"><properties>'
                 f'<property name="grass" type="bool" value="true"/>'
                 f'</properties></tile>')
    open(f"{OUT}/tiles.tsx", "w").write(
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<tileset version="1.10" name="isle" tilewidth="{T}" tileheight="{T}"'
        f' tilecount="8" columns="8">\n'
        f' <image source="tiles.png" width="{8*T}" height="{T}"/>\n'
        + "\n".join(props) + "\n</tileset>\n")


def make_sprites() -> None:
    pygame.image.save(art.character_sheet(
        skin=(224, 188, 150), hair=(38, 40, 46),
        shirt=(50, 160, 150), pants=(58, 80, 96)), f"{OUT}/player.png")
    pygame.image.save(art.character_sheet(
        skin=(210, 170, 134), hair=(70, 50, 40),
        shirt=(200, 120, 60), pants=(82, 70, 58)), f"{OUT}/npc.png")


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
        objs.append(f'  <object id="{i}" name="{oname}" x="{tx*T}" y="{ty*T}"'
                    f' width="{T}" height="{T}"><properties>{ps}</properties>'
                    f'</object>')
    open(f"{OUT}/maps/{name}.tmx", "w").write(
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<map version="1.10" orientation="orthogonal" renderorder="right-down"'
        f' width="{w}" height="{h}" tilewidth="{T}" tileheight="{T}"'
        f' infinite="0" nextobjectid="99">\n'
        f' <tileset firstgid="1" source="../tiles.tsx"/>\n'
        f' <layer id="1" name="ground" width="{w}" height="{h}">\n'
        f'  <data encoding="csv">\n{csv}\n</data>\n </layer>\n'
        f' <objectgroup id="2" name="objects">\n' + "\n".join(objs) +
        f'\n </objectgroup>\n</map>\n')


def make_isle_town() -> None:
    w, h = 18, 12
    g = [[SAND] * w for _ in range(h)]
    for x in range(w):
        g[0][x] = g[h - 1][x] = SEA
    for y in range(h):
        g[y][0] = g[y][w - 1] = SEA
    g[0][8] = g[0][9] = PLANK                       # pier north -> cove
    for x, y in ((3, 3), (14, 3), (3, 9), (14, 9), (12, 6)):
        g[y][x] = PALM
    g[5][5] = ROCK
    objects = [
        ("spawn", 8, 8, {}),
        ("warp", 8, 0, {"to_map": "cove", "to_x": 8, "to_y": 12,
                        "facing": "up"}),
        ("warp", 9, 0, {"to_map": "cove", "to_x": 9, "to_y": 12,
                        "facing": "up"}),
        ("npc", 6, 6, {"display": "Mira", "facing": "down",
                       "script": "isle_heal"}),
        ("sign", 10, 8, {"dialog": "ISLETON - Population: salty.|The cove"
                                   " north of here hides a champion."}),
    ]
    tmx("isle_town", g, objects)


def make_cove() -> None:
    w, h = 18, 14
    g = [[SAND] * w for _ in range(h)]
    for x in range(w):
        g[0][x] = g[h - 1][x] = SEA
    for y in range(h):
        g[y][0] = g[y][w - 1] = SEA
    g[h - 1][8] = g[h - 1][9] = PLANK               # pier south -> town
    for y in range(7, 10):                           # forced grass band
        for x in range(5, 13):
            g[y][x] = GRASS
    for x, y in ((3, 5), (14, 5), (4, 11), (13, 11)):
        g[y][x] = PALM
    g[2][8] = SHELL                                  # the goal marker
    g[3][6] = ROCK
    g[3][10] = ROCK
    objects = [
        ("spawn", 8, 12, {}),
        ("warp", 8, 13, {"to_map": "isle_town", "to_x": 8, "to_y": 1,
                         "facing": "down"}),
        ("warp", 9, 13, {"to_map": "isle_town", "to_x": 9, "to_y": 1,
                         "facing": "down"}),
        ("trainer", 8, 4, {"display": "Sailor Brom", "facing": "down",
                           "sight": 3, "party": "krabby:7|wingull:7",
                           "prize": 200, "flag": "beat_brom",
                           "before": "Brom: Nobody crosses my cove without"
                                     " a scrap!",
                           "after": "Brom: The shell shrine's all yours."}),
        ("sign", 8, 2, {"script": "isle_goal"}),
    ]
    tmx("cove", g, objects)


def make_data() -> None:
    json.dump({
        "name": "Isleton (example region)",
        "start": {"map": "isle_town", "facing": "down"},
        "starter": {"species": "totodile", "level": 14},
        "bag": {"potion": 3, "poke-ball": 5},
        "money": 800,
        "dex": ["totodile", "croconaw", "feraligatr", "krabby", "kingler",
                "wingull", "pelipper", "slowpoke", "slowbro"],
    }, open(f"{OUT}/game.json", "w"), indent=1)
    json.dump({
        "isle_heal": [
            {"say": "Mira: Sea air rough on the team?"},
            {"heal": True},
            {"say": "Mira: Good as new. Mind the sailor up north!"},
        ],
        "isle_goal": [
            {"if_flag": "beat_brom",
             "then": [{"say": "You touch the shell shrine.|A salty breeze"
                              " crowns you Champion of Isleton!"},
                      {"set_flag": "finished_isleton"},
                      {"give_money": 1000}],
             "else": [{"say": "A shell shrine. Something tells you to prove"
                              " yourself first."}]},
        ],
    }, open(f"{OUT}/scripts.json", "w"), indent=1)
    json.dump({
        "cove": [
            {"species": "krabby", "min": 5, "max": 7, "weight": 50},
            {"species": "wingull", "min": 5, "max": 7, "weight": 35},
            {"species": "slowpoke", "min": 6, "max": 8, "weight": 15},
        ],
    }, open(f"{OUT}/encounters.json", "w"), indent=1)


def main() -> None:
    pygame.init()
    pygame.display.set_mode((32, 32))
    os.makedirs(f"{OUT}/maps", exist_ok=True)
    make_tiles()
    make_sprites()
    make_isle_town()
    make_cove()
    make_data()
    print("example region written to", OUT)


if __name__ == "__main__":
    main()
