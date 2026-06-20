"""Build the Triad showcase region into examples/triad/.

Three cities on a triangle of three distinct routes, demonstrating the
full authoring surface: per-map weather, per-map encounter rates, shops
with real prices, a choice-driven gift Pokemon, trainers with held
items, ground-item triggers, a road-block NPC that disappears on a
flag, and a finale gated behind both wardens.

    Verdant City (forest) --Canopy Path-- Mistral City (lake)
            \\                                  /
        Mirage Crossing (sandstorm)   Shoreline Run (rain)
                  \\                      /
                     Duston City (desert)

    python tools/make_triad_region.py
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

OUT = "examples/triad"
T = 16

(GRASS, TALL, PATH, WATER, TREE, ROCK, DUNE, SAND, PLANK, FLOWER,
 SIGN, WALL, ROOF, DEAD, REED, MAT) = range(16)
BLOCKED = {WATER, TREE, ROCK, DUNE, SIGN, WALL, ROOF, DEAD}


def make_tiles() -> None:
    sheet = pygame.Surface((16 * T, T))

    def cell(i):
        return sheet.subsurface((i * T, 0, T, T))

    GR = (116, 180, 96)
    art.grass(cell(GRASS), GR, seed=GRASS)
    art.tall_grass(cell(TALL), GR, seed=TALL)
    art.path(cell(PATH), (210, 190, 140), seed=PATH)
    art.water(cell(WATER), (72, 132, 206), seed=WATER)
    art.tree(cell(TREE), GR, seed=TREE, leaf=(58, 132, 64))
    art.rock(cell(ROCK), (226, 204, 150), seed=ROCK)
    art.dune(cell(DUNE), (226, 204, 150), seed=DUNE)
    art.sand(cell(SAND), (226, 204, 150), seed=SAND)
    art.plank(cell(PLANK), base=(188, 148, 100))
    art.flower(cell(FLOWER), GR, seed=FLOWER)
    art.sign(cell(SIGN), GR, seed=SIGN)
    art.brick_wall(cell(WALL), base=(198, 198, 204))
    art.roof(cell(ROOF), base=(92, 122, 188))
    art.dead_tree(cell(DEAD), (226, 204, 150), seed=DEAD)
    art.reed(cell(REED), (96, 156, 170), seed=REED)
    art.mat(cell(MAT), (210, 190, 140), color=(120, 96, 150))

    pygame.image.save(sheet, f"{OUT}/tiles.png")

    props = [f'  <tile id="{t}"><properties>'
             f'<property name="blocked" type="bool" value="true"/>'
             f'</properties></tile>' for t in sorted(BLOCKED)]
    for t in (TALL, REED):
        props.append(f'  <tile id="{t}"><properties>'
                     f'<property name="grass" type="bool" value="true"/>'
                     f'</properties></tile>')
    open(f"{OUT}/tiles.tsx", "w").write(
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<tileset version="1.10" name="triad" tilewidth="{T}" tileheight="{T}"'
        f' tilecount="16" columns="16">\n'
        f' <image source="tiles.png" width="{16*T}" height="{T}"/>\n'
        + "\n".join(props) + "\n</tileset>\n")


def make_sprites() -> None:
    pygame.image.save(art.character_sheet(
        skin=(240, 206, 168), hair=(40, 36, 44),
        shirt=(178, 70, 90), pants=(56, 60, 86)), f"{OUT}/player.png")
    pygame.image.save(art.character_sheet(
        skin=(226, 186, 148), hair=(110, 78, 50),
        shirt=(84, 130, 96), pants=(74, 70, 64)), f"{OUT}/npc.png")


def tmx(name, grid, objects, map_props=None) -> None:
    h, w = len(grid), len(grid[0])
    csv = ",\n".join(",".join(str(c + 1) for c in row) for row in grid)
    mp = ""
    if map_props:
        mp = (" <properties>" + "".join(
            f'<property name="{k}"'
            + (f' type="int" value="{v}"/>' if isinstance(v, int)
               else f' value="{v}"/>') for k, v in map_props.items())
            + "</properties>\n")
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
        f' infinite="0" nextobjectid="99">\n{mp}'
        f' <tileset firstgid="1" source="../tiles.tsx"/>\n'
        f' <layer id="1" name="ground" width="{w}" height="{h}">\n'
        f'  <data encoding="csv">\n{csv}\n</data>\n </layer>\n'
        f' <objectgroup id="2" name="objects">\n' + "\n".join(objs) +
        f'\n </objectgroup>\n</map>\n')


def base(w, h, fill, border):
    g = [[fill] * w for _ in range(h)]
    for x in range(w):
        g[0][x] = g[h - 1][x] = border
    for y in range(h):
        g[y][0] = g[y][w - 1] = border
    return g


def house(g, x, y):
    for dx in range(4):
        g[y][x + dx] = ROOF
        g[y + 1][x + dx] = WALL


# ── cities ───────────────────────────────────────────────────────────

def make_verdant() -> None:
    w, h = 22, 14
    g = base(w, h, GRASS, TREE)
    for x in range(3, 19):
        g[7][x] = PATH
    for y in range(2, 8):
        g[y][16] = g[y][17] = PATH
    g[0][16] = g[0][17] = PATH                       # north-east -> canopy
    for y in range(7, h - 1):
        g[y][5] = g[y][6] = PATH
    g[h - 1][5] = g[h - 1][6] = PATH                 # south -> mirage
    house(g, 3, 3)
    house(g, 9, 3)
    for x, y in ((8, 10), (13, 10), (3, 9), (19, 4)):
        g[y][x] = FLOWER
    g[9][12] = SIGN
    objects = [
        ("spawn", 11, 8, {}),
        ("warp", 16, 0, {"to_map": "route_canopy", "to_x": 2, "to_y": 13,
                         "facing": "up"}),
        ("warp", 17, 0, {"to_map": "route_canopy", "to_x": 3, "to_y": 13,
                         "facing": "up"}),
        ("warp", 5, 13, {"to_map": "route_mirage", "to_x": 3, "to_y": 1,
                         "facing": "down"}),
        ("warp", 6, 13, {"to_map": "route_mirage", "to_x": 4, "to_y": 1,
                         "facing": "down"}),
        ("npc", 4, 5, {"display": "Nurse Ivy", "facing": "down",
                       "script": "heal_verdant"}),
        ("npc", 10, 5, {"display": "Clerk Pip", "facing": "down",
                        "script": "shop_verdant"}),
        ("npc", 14, 8, {"display": "Elder Rowan", "facing": "down",
                        "script": "rowan_hints"}),
        ("sign", 12, 9, {"dialog": "VERDANT CITY - Where the canopy"
                                   " sings.|NE: Canopy Path. S: Mirage"
                                   " Crossing."}),
        ("trainer", 18, 4, {"display": "Warden Fern", "facing": "left",
                            "sight": 3, "party": "sewaddle:9|petilil:9@oran-berry",
                            "prize": 400, "flag": "beat_fern",
                            "before": "Fern: The forest tests every"
                                      " traveler. En garde!",
                            "after": "Fern: The canopy bows to you."}),
    ]
    tmx("verdant", g, objects)


def make_mistral() -> None:
    w, h = 22, 14
    g = base(w, h, GRASS, WATER)
    for y in (1, 2):
        for x in range(1, w - 1):
            g[y][x] = WATER
    for x in range(3, 19):
        g[8][x] = PATH
    for y in range(8, h - 1):
        g[y][4] = g[y][5] = PATH
    g[h - 1][4] = g[h - 1][5] = PLANK                # south -> shoreline
    for y in range(3, 9):
        g[y][2] = g[y][3] = PATH
    g[3][2] = g[3][3] = PATH
    for y in range(3, 6):                            # west pier -> canopy
        pass
    g[5][1] = g[6][1] = PATH
    # west edge gap
    g[5][0] = g[6][0] = PATH
    house(g, 8, 4)
    house(g, 14, 4)
    g[3][18] = REED; g[3][19] = REED
    g[9][16] = SIGN
    objects = [
        ("warp", 0, 5, {"to_map": "route_canopy", "to_x": 24, "to_y": 7,
                        "facing": "left"}),
        ("warp", 0, 6, {"to_map": "route_canopy", "to_x": 24, "to_y": 8,
                        "facing": "left"}),
        ("warp", 4, 13, {"to_map": "route_shoreline", "to_x": 4, "to_y": 1,
                         "facing": "down"}),
        ("warp", 5, 13, {"to_map": "route_shoreline", "to_x": 5, "to_y": 1,
                         "facing": "down"}),
        ("spawn", 11, 9, {}),
        ("npc", 9, 6, {"display": "Nurse Brooke", "facing": "down",
                       "script": "heal_mistral"}),
        ("npc", 15, 6, {"display": "Clerk Moa", "facing": "down",
                        "script": "shop_mistral"}),
        ("npc", 12, 8, {"display": "Old Salt", "facing": "down",
                        "script": "frillish_gift"}),
        ("sign", 16, 8, {"dialog": "MISTRAL CITY - The lake keeps our"
                                   " secrets.|W: Canopy Path. S: Shoreline"
                                   " Run."}),
        ("trainer", 18, 10, {"display": "Captain Gale", "facing": "left",
                             "sight": 3,
                             "party": "ducklett:12@sitrus-berry|frillish:12",
                             "prize": 600, "flag": "beat_gale",
                             "before": "Gale: Wind and water answer only"
                                       " to me!",
                             "after": "Gale: The gusts carry your name"
                                      " now."}),
    ]
    tmx("mistral", g, objects)


def make_duston() -> None:
    w, h = 22, 14
    g = base(w, h, SAND, ROCK)
    for x in range(3, 19):
        g[7][x] = PATH
    for y in range(1, 8):
        g[y][3] = g[y][4] = PATH
    g[0][3] = g[0][4] = PATH                         # north-west -> mirage
    for y in range(1, 8):
        g[y][17] = g[y][18] = PATH
    g[0][17] = g[0][18] = PATH                       # north-east -> shoreline
    house(g, 7, 3)
    house(g, 13, 3)
    for x, y in ((6, 10), (15, 10), (10, 11)):
        g[y][x] = DEAD
    g[9][9] = SIGN
    g[10][11] = MAT                                  # the champion's mat
    objects = [
        ("warp", 3, 0, {"to_map": "route_mirage", "to_x": 22, "to_y": 14,
                        "facing": "up"}),
        ("warp", 4, 0, {"to_map": "route_mirage", "to_x": 23, "to_y": 14,
                        "facing": "up"}),
        ("warp", 17, 0, {"to_map": "route_shoreline", "to_x": 13, "to_y": 16,
                         "facing": "up"}),
        ("warp", 18, 0, {"to_map": "route_shoreline", "to_x": 14, "to_y": 16,
                         "facing": "up"}),
        ("spawn", 11, 8, {}),
        ("npc", 8, 5, {"display": "Nurse Opal", "facing": "down",
                       "script": "heal_duston"}),
        ("npc", 14, 5, {"display": "Clerk Rye", "facing": "down",
                        "script": "shop_duston"}),
        ("npc", 11, 9, {"display": "Sheriff Cinder", "facing": "down",
                        "script": "sheriff_cinder"}),
        ("sign", 9, 9, {"dialog": "DUSTON CITY - Last law before the"
                                  " badlands.|NW: Mirage Crossing. NE:"
                                  " Shoreline Run."}),
    ]
    tmx("duston", g, objects)


# ── routes ───────────────────────────────────────────────────────────

def make_route_canopy() -> None:
    """Forest switchbacks: tall grass pockets, two trainers, an item."""
    w, h = 26, 15
    g = base(w, h, GRASS, TREE)
    g[h - 1][2] = g[h - 1][3] = PATH                 # south -> verdant
    g[7][w - 1] = g[8][w - 1] = PATH                 # east -> mistral
    for y in range(7, h - 1):
        g[y][2] = g[y][3] = PATH
    for x in range(2, 12):
        g[7][x] = g[8][x] = PATH
    for y in range(3, 9):
        g[y][11] = g[y][12] = PATH
    for x in range(11, 25):
        g[3][x] = g[4][x] = PATH
    for y in range(3, 9):
        g[y][23] = g[y][24] = PATH
    for x in range(23, 26):
        g[7][x] = g[8][x] = PATH
    for yy in range(5, 7):
        for xx in range(4, 10):
            g[yy][xx] = TALL
    for yy in range(9, 12):
        for xx in range(14, 21):
            g[yy][xx] = TALL
    for x, y in ((7, 3), (16, 6), (20, 12), (6, 12)):
        g[y][x] = TREE
    g[10][6] = FLOWER
    objects = [
        ("warp", 2, 14, {"to_map": "verdant", "to_x": 16, "to_y": 1,
                         "facing": "down"}),
        ("warp", 3, 14, {"to_map": "verdant", "to_x": 17, "to_y": 1,
                         "facing": "down"}),
        ("warp", 25, 7, {"to_map": "mistral", "to_x": 1, "to_y": 5,
                         "facing": "right"}),
        ("warp", 25, 8, {"to_map": "mistral", "to_x": 1, "to_y": 6,
                         "facing": "right"}),
        ("spawn", 2, 13, {}),
        ("sign", 12, 5, {"dialog": "CANOPY PATH - Watch for falling"
                                   " caterpillars."}),
        ("trigger", 6, 10, {"script": "canopy_item",
                            "unless_flag": "got_canopy_potion"}),
        ("trainer", 8, 5, {"display": "Bug Catcher Nino", "facing": "down",
                           "sight": 2, "party": "sewaddle:8|venipede:8",
                           "prize": 160, "flag": "beat_nino",
                           "before": "Nino: My bugs never bug out!",
                           "after": "Nino: Back to the long grass..."}),
        ("trainer", 18, 4, {"display": "Pokefan Lila", "facing": "down",
                            "sight": 3, "party": "lillipup:10@oran-berry",
                            "prize": 240, "flag": "beat_lila",
                            "before": "Lila: My precious pup is"
                                      " undefeated!",
                            "after": "Lila: Such good sportsmanship!"}),
    ]
    tmx("route_canopy", g, objects)


def make_route_shoreline() -> None:
    """Rain-soaked piers over the lake: fishermen and water spawns."""
    w, h = 18, 17
    g = base(w, h, WATER, WATER)
    g[1][4] = g[1][5] = PLANK                        # north -> mistral
    g[h - 1][13] = g[h - 1][14] = PLANK              # south -> duston
    for y in range(1, 8):
        g[y][4] = g[y][5] = PLANK
    for x in range(4, 14):
        g[7][x] = g[8][x] = PLANK
    for y in range(8, 16):
        g[y][13] = g[y][14] = PLANK
    for yy in range(5, 7):
        for xx in (2, 3):
            g[yy][xx] = REED
    for yy in (10, 11):
        for xx in (15, 16):
            g[yy][xx] = REED
    for yy in (12, 13):
        for xx in (11, 12):
            g[yy][xx] = REED
    g[6][7] = SIGN
    objects = [
        ("warp", 4, 0, {"to_map": "mistral", "to_x": 4, "to_y": 12,
                        "facing": "up"}),
        ("warp", 5, 0, {"to_map": "mistral", "to_x": 5, "to_y": 12,
                        "facing": "up"}),
        ("warp", 13, 16, {"to_map": "duston", "to_x": 17, "to_y": 1,
                          "facing": "down"}),
        ("warp", 14, 16, {"to_map": "duston", "to_x": 18, "to_y": 1,
                          "facing": "down"}),
        ("spawn", 4, 2, {}),
        ("sign", 7, 6, {"dialog": "SHORELINE RUN - It always rains on the"
                                  " run."}),
        ("trainer", 8, 6, {"display": "Fisherman Wade", "facing": "down",
                           "sight": 2, "party": "basculin:11",
                           "prize": 280, "flag": "beat_wade",
                           "before": "Wade: Fresh catch, coming right up!",
                           "after": "Wade: Slippery one, you are."}),
        ("trainer", 13, 11, {"display": "Fisherman Otto", "facing": "up",
                             "sight": 3, "party": "tympole:10|tympole:11",
                             "prize": 260, "flag": "beat_otto",
                             "before": "Otto: The rain doubles my"
                                       " tadpoles' fun!",
                             "after": "Otto: Even swift swimmers sink."}),
    ]
    tmx("route_shoreline", g, objects, {"weather": "rain"})


def make_route_mirage() -> None:
    """A sandstorm-scoured rock maze; the ranger clears out after you
    defeat Warden Fern."""
    w, h = 26, 16
    g = base(w, h, SAND, ROCK)
    g[0][3] = g[0][4] = PATH                         # north -> verdant
    g[h - 1][22] = g[h - 1][23] = PATH               # south-east -> duston
    for y in range(0, 6):
        g[y][3] = g[y][4] = PATH
    for x in range(3, 13):
        g[5][x] = g[6][x] = PATH
    for y in range(5, 11):
        g[y][11] = g[y][12] = PATH
    for x in range(11, 23):
        g[9][x] = g[10][x] = PATH
    for y in range(9, h - 1):
        g[y][22] = g[y][23] = PATH
    for yy in (3, 4):
        for xx in range(7, 11):
            g[yy][xx] = TALL
    for yy in (12, 13):
        for xx in range(15, 20):
            g[yy][xx] = TALL
    for x, y in ((8, 8), (15, 7), (18, 6), (6, 12), (20, 12), (14, 3)):
        g[y][x] = DUNE
    for x, y in ((10, 12), (17, 4)):
        g[y][x] = DEAD
    g[8][13] = SIGN
    objects = [
        ("warp", 3, 0, {"to_map": "verdant", "to_x": 5, "to_y": 12,
                        "facing": "up"}),
        ("warp", 4, 0, {"to_map": "verdant", "to_x": 6, "to_y": 12,
                        "facing": "up"}),
        ("warp", 22, 15, {"to_map": "duston", "to_x": 3, "to_y": 1,
                          "facing": "down"}),
        ("warp", 23, 15, {"to_map": "duston", "to_x": 4, "to_y": 1,
                          "facing": "down"}),
        ("spawn", 3, 2, {}),
        ("sign", 13, 7, {"dialog": "MIRAGE CROSSING - If you can read"
                                   " this, it's not a mirage."}),
        ("npc", 3, 5, {"display": "Ranger Dune", "facing": "up",
                       "visible_unless": "beat_fern",
                       "dialog": "Ranger Dune: Storm's too fierce for"
                                 " rookies.|Prove yourself to Warden Fern"
                                 " first."}),
        ("trainer", 12, 8, {"display": "Hiker Bram", "facing": "down",
                            "sight": 2,
                            "party": "roggenrola:11@oran-berry|drilbur:11",
                            "prize": 320, "flag": "beat_bram",
                            "before": "Bram: These rocks LOVE a"
                                      " sandstorm!",
                            "after": "Bram: Solid as a... well, you"
                                     " know."}),
        ("trainer", 20, 10, {"display": "Backpacker Sage", "facing": "left",
                             "sight": 3, "party": "sandile:12",
                             "prize": 300, "flag": "beat_sage",
                             "before": "Sage: I crossed three deserts"
                                       " for this!",
                             "after": "Sage: Four deserts next time."}),
    ]
    tmx("route_mirage", g, objects, {"weather": "sandstorm",
                                     "encounter_chance": 6})


def make_data() -> None:
    json.dump({
        "name": "Triad (showcase region)",
        "start": {"map": "verdant", "facing": "down"},
        "starter": {"species": "tepig", "level": 12,
                    "moves": ["ember", "tackle", "defense-curl"]},
        "bag": {"potion": 4, "poke-ball": 8},
        "money": 2000,
        "features": {"encounters": True, "trainers": True,
                     "experience": True, "evolution": True,
                     "move_replacement": True, "running": True,
                     "menu_party": True, "menu_bag": True, "saving": True},
        "settings": {"encounter_chance": 9},
        "dex": ["tepig", "pignite", "emboar", "sewaddle", "venipede",
                "petilil", "lillipup", "pidove", "ducklett", "frillish",
                "basculin", "tympole", "sandile", "dwebble", "darumaka",
                "roggenrola", "drilbur", "trapinch", "maractus"],
    }, open(f"{OUT}/game.json", "w"), indent=1)

    heal = lambda who, line2: [  # noqa: E731
        {"say": f"{who}: Let's get that team rested."},
        {"heal": True},
        {"say": f"{who}: {line2}"}]
    json.dump({
        "heal_verdant": heal("Nurse Ivy", "Green and growing again!"),
        "heal_mistral": heal("Nurse Brooke", "Fresh as lake mist!"),
        "heal_duston": heal("Nurse Opal", "Tough as desert glass!"),
        "shop_verdant": [
            {"say": "Pip: Basics for the canopy, cheap and cheerful."},
            {"shop": {"items": ["potion", "poke-ball", "antidote"]}},
        ],
        "shop_mistral": [
            {"say": "Moa: Imports! Only the good stuff."},
            {"shop": {"items": ["super-potion", "great-ball", "awakening"],
                      "prices": {"great-ball": 500}}},
        ],
        "shop_duston": [
            {"say": "Rye: Storm gear and stronger medicine."},
            {"shop": {"items": ["super-potion", "great-ball", "revive",
                                "paralyze-heal"]}},
        ],
        "rowan_hints": [
            {"if_flag": "finished_triad",
             "then": [{"say": "Rowan: Champion of the Triad! The three"
                              " roads remember you."}],
             "else": [{"say": "Rowan: Three cities, three roads, three"
                              " wardens.|Beat Fern and Gale, then face the"
                              " Sheriff in Duston."}]},
        ],
        "canopy_item": [
            {"say": "There's a Super Potion tucked in the roots!"},
            {"give_item": {"item": "super-potion", "qty": 1}},
            {"set_flag": "got_canopy_potion"},
        ],
        "frillish_gift": [
            {"if_flag": "took_frillish",
             "then": [{"say": "Old Salt: How fares the little drifter?"}],
             "else": [
                {"say": "Old Salt: This Frillish followed my boat home."},
                {"choice": {"prompt": "Take the Frillish?",
                            "options": [
                                {"label": "Yes", "then": [
                                    {"give_pokemon": {"species": "frillish",
                                                      "level": 10}},
                                    {"set_flag": "took_frillish"},
                                    {"say": "You received a Frillish!"}]},
                                {"label": "No", "then": [
                                    {"say": "Old Salt: Suit yourself."
                                            " It'll keep drifting."}]}]}}]},
        ],
        "sheriff_cinder": [
            {"if_flag": "finished_triad",
             "then": [{"say": "Cinder: This town's in good hands,"
                              " Champion."}],
             "else": [
                {"if_flag": "beat_fern",
                 "then": [
                    {"if_flag": "beat_gale",
                     "then": [
                        {"say": "Cinder: Fern's woods. Gale's waters."
                                "|Now face Duston's fire!"},
                        {"battle": {"trainer": "Sheriff Cinder",
                                    "party": "sandile:13@focus-sash|"
                                             "dwebble:13|"
                                             "darumaka:13@oran-berry",
                                    "prize": 1500, "flag": "beat_cinder"}},
                        {"say": "Cinder: The Triad has a new"
                                " Champion!"},
                        {"give_money": 1000},
                        {"set_flag": "finished_triad"}],
                     "else": [{"say": "Cinder: Gale still rules the lake."
                                      " Come back stronger."}]}],
                 "else": [{"say": "Cinder: Start with Warden Fern in"
                                  " Verdant. Then we'll talk."}]}]},
        ],
    }, open(f"{OUT}/scripts.json", "w"), indent=1)

    json.dump({
        "route_canopy": [
            {"species": "sewaddle", "min": 7, "max": 9, "weight": 35},
            {"species": "venipede", "min": 7, "max": 9, "weight": 25},
            {"species": "petilil", "min": 8, "max": 10, "weight": 20},
            {"species": "pidove", "min": 7, "max": 10, "weight": 20},
        ],
        "route_shoreline": [
            {"species": "tympole", "min": 9, "max": 11, "weight": 45},
            {"species": "basculin", "min": 10, "max": 12, "weight": 30},
            {"species": "ducklett", "min": 9, "max": 11, "weight": 25},
        ],
        "route_mirage": [
            {"species": "sandile", "min": 10, "max": 12, "weight": 30},
            {"species": "dwebble", "min": 10, "max": 12, "weight": 30},
            {"species": "trapinch", "min": 10, "max": 12, "weight": 25},
            {"species": "maractus", "min": 11, "max": 13, "weight": 15},
        ],
    }, open(f"{OUT}/encounters.json", "w"), indent=1)


def main() -> None:
    pygame.init()
    pygame.display.set_mode((32, 32))
    os.makedirs(f"{OUT}/maps", exist_ok=True)
    make_tiles()
    make_sprites()
    make_verdant()
    make_mistral()
    make_duston()
    make_route_canopy()
    make_route_shoreline()
    make_route_mirage()
    make_data()
    print("showcase region written to", OUT)


if __name__ == "__main__":
    main()
