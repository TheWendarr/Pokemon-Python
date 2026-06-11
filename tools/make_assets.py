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
import pygame  # noqa: E402

OUT = "game/assets"
T = 16

# tile ids (0-based in tsx; GID = id+1 in tmx)
GRASS, TALL, PATH, WATER, TREE, WALL, ROOF, DOOR, FLOWER, FENCE, SIGN, SAND = range(12)
BLOCKED = {WATER, TREE, WALL, ROOF, FENCE, SIGN}


def make_tiles() -> None:
    rng = random.Random(7)
    sheet = pygame.Surface((12 * T, T))

    def tile(i):
        return sheet.subsurface((i * T, 0, T, T))

    def speckle(s, color, n=10):
        for _ in range(n):
            s.set_at((rng.randrange(T), rng.randrange(T)), color)

    g = tile(GRASS); g.fill((124, 188, 92)); speckle(g, (108, 172, 80), 14)
    tg = tile(TALL); tg.fill((84, 152, 68))
    for x in range(2, T, 5):
        pygame.draw.lines(tg, (56, 118, 48), False,
                          [(x, 13), (x + 1, 6), (x + 2, 13)])
    p = tile(PATH); p.fill((216, 196, 144)); speckle(p, (200, 180, 128), 12)
    w = tile(WATER); w.fill((84, 140, 216))
    for y in (4, 10):
        pygame.draw.line(w, (140, 188, 240), (2, y), (7, y))
        pygame.draw.line(w, (140, 188, 240), (9, y + 3), (14, y + 3))
    tr = tile(TREE); tr.fill((124, 188, 92))
    pygame.draw.rect(tr, (110, 80, 48), (6, 10, 4, 6))
    pygame.draw.circle(tr, (44, 108, 52), (8, 7), 7)
    pygame.draw.circle(tr, (60, 132, 64), (6, 5), 4)
    wl = tile(WALL); wl.fill((196, 196, 200))
    for y in (5, 11):
        pygame.draw.line(wl, (150, 150, 158), (0, y), (15, y))
    for x in (4, 9, 13):
        pygame.draw.line(wl, (150, 150, 158), (x, 0), (x, 5))
        pygame.draw.line(wl, (150, 150, 158), ((x + 3) % 16, 6), ((x + 3) % 16, 11))
    rf = tile(ROOF); rf.fill((196, 84, 76))
    for y in (4, 9, 14):
        pygame.draw.line(rf, (160, 60, 56), (0, y), (15, y))
    d = tile(DOOR); d.fill((196, 196, 200))
    pygame.draw.rect(d, (124, 84, 52), (3, 2, 10, 14))
    pygame.draw.rect(d, (92, 60, 36), (3, 2, 10, 14), 1)
    d.set_at((11, 9), (232, 208, 96))
    fl = tile(FLOWER); fl.fill((124, 188, 92))
    for cx, cy, col in ((4, 4, (232, 120, 152)), (11, 8, (240, 220, 110)),
                        (5, 12, (232, 120, 152))):
        pygame.draw.circle(fl, col, (cx, cy), 2)
    fn = tile(FENCE); fn.fill((124, 188, 92))
    pygame.draw.rect(fn, (148, 110, 70), (1, 6, 14, 3))
    for x in (2, 7, 12):
        pygame.draw.rect(fn, (124, 90, 56), (x, 4, 2, 9))
    sg = tile(SIGN); sg.fill((124, 188, 92))
    pygame.draw.rect(sg, (124, 90, 56), (7, 8, 2, 7))
    pygame.draw.rect(sg, (172, 132, 84), (3, 2, 10, 7))
    pygame.draw.rect(sg, (120, 88, 52), (3, 2, 10, 7), 1)
    sd = tile(SAND); sd.fill((232, 216, 168)); speckle(sd, (214, 196, 148), 10)

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
           f'tileheight="{T}" tilecount="12" columns="12">\n'
           f' <image source="tiles.png" width="{12*T}" height="{T}"/>\n'
           + "\n".join(props) + "\n</tileset>\n")
    open(f"{OUT}/tiles.tsx", "w").write(tsx)


def make_sprites() -> None:
    def strip(shirt, hair):
        s = pygame.Surface((4 * T, T), pygame.SRCALPHA)
        for i, facing in enumerate(("down", "up", "left", "right")):
            x0 = i * T
            pygame.draw.rect(s, shirt, (x0 + 4, 8, 8, 6))           # body
            pygame.draw.rect(s, (44, 48, 64), (x0 + 4, 14, 3, 2))   # feet
            pygame.draw.rect(s, (44, 48, 64), (x0 + 9, 14, 3, 2))
            pygame.draw.circle(s, (244, 212, 176), (x0 + 8, 5), 4)  # head
            pygame.draw.rect(s, hair, (x0 + 4, 1, 9, 3))            # hair
            eye = (32, 32, 40)
            if facing == "down":
                s.set_at((x0 + 6, 5), eye); s.set_at((x0 + 10, 5), eye)
            elif facing == "left":
                s.set_at((x0 + 5, 5), eye)
            elif facing == "right":
                s.set_at((x0 + 11, 5), eye)
        return s

    pygame.image.save(strip((200, 60, 60), (60, 40, 32)), f"{OUT}/player.png")
    pygame.image.save(strip((70, 110, 200), (96, 72, 48)), f"{OUT}/npc.png")


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
        ("npc", 7, 7, {"display": "Nurse Hazel", "facing": "down",
                       "heal": True,
                       "dialog": "Your Pokemon look tired.|There. "
                                 "They're fighting fit again!"}),
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
    ]
    tmx("route1", g, objects)


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
    make_encounters()
    print("assets written to", OUT)


if __name__ == "__main__":
    main()
