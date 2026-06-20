"""Shared procedural art for the default game folders.

One place for the *detailed* default look: shaded, textured 16x16 tile
painters and a 4-direction / 4-frame animated character walk-cycle.
Every bundled region (the Hexton reference plus the Isleton and Triad
examples) composes its tileset and sprites from these, parameterised by
palette, so the engine still ships no third-party image files while the
defaults look hand-pixelled rather than flat.

Character sheets are laid out as a grid: 4 rows (down, up, left, right)
x 4 columns (walk frames 0..3), each cell 16 wide x 24 tall so the
sprite stands a head above its tile. Frame 0 is the idle stance; 1 and
3 are opposite stepping poses; 2 is a mid stride. Assets auto-detects
this grid vs. the legacy 64x16 single-frame strip.
"""
from __future__ import annotations

import random

import pygame

T = 16                      # tile size
FW, FH = 16, 24             # character frame size
DIRS = ("down", "up", "left", "right")


# ── colour helpers ───────────────────────────────────────────────────

def shade(c, amt: float):
    """Lighten (amt>0, toward white) or darken (amt<0) an RGB colour."""
    if amt >= 0:
        return tuple(min(255, int(v + (255 - v) * amt)) for v in c[:3])
    return tuple(max(0, int(v * (1 + amt))) for v in c[:3])


def _rng(seed):
    return random.Random(seed)


def _speckle(s, color, n, seed, *, area=(0, 0, T, T)):
    rng = _rng(seed)
    x0, y0, w, h = area
    for _ in range(n):
        s.set_at((x0 + rng.randrange(w), y0 + rng.randrange(h)), color)


# ── tile painters (each fills a 16x16 surface) ───────────────────────

def grass(s, base, *, seed=1):
    dark, light = shade(base, -0.16), shade(base, 0.14)
    s.fill(base)
    rng = _rng(seed)
    for _ in range(30):
        s.set_at((rng.randrange(T), rng.randrange(T)),
                 dark if rng.random() < 0.5 else light)
    for _ in range(5):
        x, y = rng.randrange(2, T - 2), rng.randrange(5, T - 1)
        pygame.draw.line(s, dark, (x, y), (x, y - 3))
        s.set_at((x + 1, y - 1), light)


def tall_grass(s, base, *, seed=2):
    grass(s, shade(base, -0.05), seed=seed)
    dark, light = shade(base, -0.30), shade(base, 0.22)
    rng = _rng(seed + 9)
    for bx in range(1, T, 3):
        h = rng.randint(6, 10)
        for i in range(h):
            y = T - 1 - i
            s.set_at((bx, y), dark if i < 2 else base)
            if i >= h - 3:
                s.set_at((bx, y), light)
        s.set_at((bx + 1, T - 2), dark)


def path(s, base, *, seed=3):
    dark, light = shade(base, -0.18), shade(base, 0.13)
    s.fill(base)
    _speckle(s, dark, 18, seed)
    _speckle(s, light, 12, seed + 1)
    rng = _rng(seed + 5)
    for _ in range(3):                       # little pebbles
        x, y = rng.randrange(2, T - 3), rng.randrange(2, T - 3)
        pygame.draw.rect(s, shade(base, -0.28), (x, y, 2, 2))
        s.set_at((x, y), light)


def water(s, base, *, seed=4):
    dark, light = shade(base, -0.20), shade(base, 0.30)
    s.fill(base)
    for y in (3, 4, 9, 10, 14):
        for x in range(T):
            if (x + y) % 6 < 3:
                s.set_at((x, y), dark if y % 2 else shade(base, -0.08))
    rng = _rng(seed)
    for _ in range(6):                       # foam glints
        s.set_at((rng.randrange(T), rng.randrange(T)), light)


def sand(s, base, *, seed=5):
    dark, light = shade(base, -0.12), shade(base, 0.10)
    s.fill(base)
    _speckle(s, dark, 16, seed)
    _speckle(s, light, 10, seed + 1)
    for y in (5, 11):                        # faint ripples
        for x in range(1, T - 1, 2):
            s.set_at((x, y), dark)


def tree(s, ground, *, seed=6, leaf=(46, 120, 58), trunk=(110, 78, 46)):
    grass(s, ground, seed=seed)
    leafD, leafL = shade(leaf, -0.28), shade(leaf, 0.22)
    pygame.draw.rect(s, shade(trunk, -0.2), (7, 11, 3, 5))
    pygame.draw.rect(s, trunk, (7, 11, 1, 5))
    pygame.draw.circle(s, leafD, (8, 6), 7)
    pygame.draw.circle(s, leaf, (8, 6), 6)
    for cx, cy in ((5, 4), (10, 5), (8, 2)):
        pygame.draw.circle(s, leafL, (cx, cy), 2)


def rock(s, ground, *, seed=7, stone=(132, 128, 122)):
    if ground is not None:
        sand(s, ground, seed=seed) if False else s.fill(ground)
    pygame.draw.circle(s, shade(stone, -0.3), (8, 9), 6)
    pygame.draw.circle(s, stone, (8, 9), 5)
    pygame.draw.circle(s, shade(stone, 0.25), (6, 7), 2)


def flower(s, ground, *, seed=8, petal=(236, 120, 150), petal2=(244, 222, 110)):
    grass(s, ground, seed=seed)
    for (cx, cy, col) in ((5, 5, petal), (11, 9, petal2)):
        pygame.draw.circle(s, shade(col, -0.2), (cx, cy), 2)
        s.set_at((cx, cy), shade(col, 0.4))


def sign(s, ground, *, seed=9, wood=(168, 128, 82)):
    grass(s, ground, seed=seed)
    pygame.draw.rect(s, shade(wood, -0.3), (7, 8, 2, 7))
    pygame.draw.rect(s, shade(wood, -0.25), (2, 2, 12, 7))
    pygame.draw.rect(s, wood, (3, 3, 10, 5))
    for y in (4, 6):
        pygame.draw.line(s, shade(wood, -0.35), (4, y), (11, y))


def brick_wall(s, base=(196, 198, 206)):
    s.fill(base)
    mortar = shade(base, -0.22)
    for y in range(0, T, 5):
        pygame.draw.line(s, mortar, (0, y), (T - 1, y))
    for y in range(0, T, 10):
        for x in range(0, T, 8):
            pygame.draw.line(s, mortar, (x, y), (x, y + 4))
    for x in range(4, T, 8):
        for y in range(5, T, 10):
            pygame.draw.line(s, mortar, (x, y), (x, y + 4))
    s.fill(shade(base, 0.12), (0, 0, T, 1))


def roof(s, base=(92, 122, 188)):
    s.fill(base)
    dark, light = shade(base, -0.22), shade(base, 0.2)
    for y in range(0, T, 4):
        pygame.draw.line(s, dark, (0, y + 3), (T - 1, y + 3))
        for x in range((y // 4 % 2) * 4, T, 8):
            pygame.draw.line(s, light, (x, y), (x, y + 2))
    s.fill(light, (0, 0, T, 1))


def floor(s, base=(214, 192, 156)):
    s.fill(base)
    seam = shade(base, -0.16)
    for y in (5, 11):
        pygame.draw.line(s, seam, (0, y), (T - 1, y))
    _speckle(s, shade(base, -0.08), 10, 31)
    for x in (4, 12):
        s.set_at((x, 2), seam)
        s.set_at((x, 8), seam)


def rug(s, floor_base=(214, 192, 156), color=(96, 140, 110)):
    floor(s, floor_base)
    pygame.draw.rect(s, shade(color, -0.2), (2, 1, 12, 14))
    pygame.draw.rect(s, color, (3, 2, 10, 12))
    pygame.draw.rect(s, shade(color, 0.2), (5, 4, 6, 8), 1)


def counter(s, floor_base=(214, 192, 156), wood=(172, 132, 84)):
    floor(s, floor_base)
    pygame.draw.rect(s, wood, (0, 4, T, 9))
    pygame.draw.rect(s, shade(wood, 0.18), (0, 4, T, 1))
    pygame.draw.rect(s, shade(wood, -0.3), (0, 11, T, 2))


def mat(s, base, color=(120, 96, 150)):
    s.fill(base)
    pygame.draw.rect(s, shade(color, -0.2), (2, 2, 12, 12))
    pygame.draw.rect(s, color, (3, 3, 10, 10))
    pygame.draw.rect(s, shade(color, 0.25), (3, 3, 10, 10), 1)


def fence(s, ground, *, seed=10, wood=(176, 142, 96)):
    grass(s, ground, seed=seed)
    pygame.draw.rect(s, shade(wood, -0.3), (3, 4, 2, 10))
    pygame.draw.rect(s, shade(wood, -0.3), (11, 4, 2, 10))
    pygame.draw.rect(s, wood, (0, 6, T, 2))
    pygame.draw.rect(s, wood, (0, 10, T, 2))


def dead_tree(s, ground, *, seed=11, wood=(120, 96, 66)):
    sand(s, ground, seed=seed)
    pygame.draw.rect(s, shade(wood, -0.2), (7, 5, 2, 10))
    pygame.draw.line(s, wood, (8, 8), (4, 4), 2)
    pygame.draw.line(s, wood, (8, 7), (12, 4), 2)
    pygame.draw.line(s, wood, (8, 6), (10, 2), 1)


def dune(s, base, *, seed=12):
    sand(s, base, seed=seed)
    dark = shade(base, -0.16)
    pygame.draw.arc(s, dark, (-4, 4, 18, 12), 0, 3.14, 2)
    pygame.draw.arc(s, dark, (6, 8, 18, 12), 0, 3.14, 2)


def reed(s, base, *, seed=13, stalk=(70, 130, 96)):
    water(s, base, seed=seed)
    for x in range(2, T, 4):
        h = _rng(seed + x).randint(7, 11)
        pygame.draw.line(s, shade(stalk, -0.2), (x, T - 1), (x, T - 1 - h))
        s.set_at((x, T - 1 - h), shade(stalk, 0.3))


def plank(s, base=(190, 150, 100)):
    s.fill(base)
    seam = shade(base, -0.24)
    for y in (5, 11):
        pygame.draw.line(s, seam, (0, y), (T - 1, y))
    pygame.draw.rect(s, shade(base, 0.12), (0, 0, T, 1))
    _speckle(s, seam, 6, 21)


def palm(s, ground, *, seed=14, frond=(54, 150, 78), trunk=(146, 108, 64)):
    sand(s, ground, seed=seed)
    pygame.draw.rect(s, shade(trunk, -0.25), (7, 8, 2, 8))
    pygame.draw.line(s, trunk, (7, 8), (7, 15))
    frondD, frondL = shade(frond, -0.26), shade(frond, 0.24)
    for dx, dy in ((-5, -2), (5, -2), (-3, -5), (3, -5), (0, -6)):
        pygame.draw.line(s, frondD, (8, 7), (8 + dx, 7 + dy), 2)
        pygame.draw.line(s, frond, (8, 7), (8 + dx, 6 + dy), 1)
    s.set_at((8, 6), frondL)
    pygame.draw.circle(s, shade(trunk, 0.2), (8, 7), 1)   # coconuts hub


def shell(s, ground, *, seed=15, color=(236, 170, 190)):
    sand(s, ground, seed=seed)
    base, dark = color, shade(color, -0.24)
    pygame.draw.polygon(s, dark, [(3, 10), (8, 2), (13, 10)])
    pygame.draw.polygon(s, base, [(4, 10), (8, 3), (12, 10)])
    for x0 in (6, 8, 10):                                  # ribs
        pygame.draw.line(s, dark, (8, 4), (x0, 10))
    pygame.draw.rect(s, dark, (6, 10, 5, 2))
    s.set_at((8, 4), shade(color, 0.4))


# ── animated character sheet ─────────────────────────────────────────

def _char_cell(s, ox, oy, facing, frame, skin, hair, shirt, pants, shoe,
               outline):
    shirtL, shirtD = shade(shirt, 0.22), shade(shirt, -0.26)
    pantsD = shade(pants, -0.24)
    hairL = shade(hair, 0.22)
    skinD = shade(skin, -0.16)
    draw_facing = "right" if facing == "left" else facing

    def rect(x, y, w, h, c):
        if w > 0 and h > 0:
            pygame.draw.rect(s, c, (ox + x, oy + y, w, h))

    def px(x, y, c):
        if 0 <= x < FW and 0 <= y < FH:
            s.set_at((ox + x, oy + y), c)

    bob = 1 if frame in (1, 3) else 0
    lf = 1 if frame == 1 else 0          # left foot strides
    rf = 1 if frame == 3 else 0          # right foot strides

    # soft contact shadow on the ground
    pygame.draw.ellipse(s, (0, 0, 0, 70), (ox + 4, oy + 21, 8, 3))

    # legs (outlined) + shoes
    for x, ext in ((6, lf), (9, rf)):
        rect(x, 17 + bob, 2, 4 + ext, outline)
        rect(x, 17 + bob, 2, 3 + ext, pants)
        px(x, 19 + bob + ext, pantsD)
        rect(x, 21 + bob + ext, 2, 1, shoe)

    # torso: outline, shirt, side shading, collar highlight, belt
    rect(4, 10 + bob, 9, 8, outline)
    rect(5, 11 + bob, 7, 6, shirt)
    rect(5, 11 + bob, 1, 6, shirtL)
    rect(11, 11 + bob, 1, 6, shirtD)
    rect(6, 11 + bob, 5, 1, shirtL)      # collar/shoulder highlight
    rect(5, 16 + bob, 7, 1, pantsD)      # belt

    # arms hang against the torso and swing opposite the legs
    al = 1 if frame == 3 else 0
    ar = 1 if frame == 1 else 0
    rect(3, 11 + bob + al, 2, 5, outline)
    rect(4, 12 + bob + al, 1, 3, shirtL)
    rect(12, 11 + bob + ar, 2, 5, outline)
    rect(12, 12 + bob + ar, 1, 3, shirtD)

    # head
    hy = 2 + bob
    pygame.draw.circle(s, outline, (ox + 8, oy + hy + 4), 5)
    pygame.draw.circle(s, skin, (ox + 8, oy + hy + 4), 4)
    if draw_facing == "up":
        pygame.draw.circle(s, hair, (ox + 8, oy + hy + 4), 4)
        rect(4, hy, 9, 4, hair)
        px(5, hy + 1, hairL)
        px(10, hy + 1, hairL)
    elif draw_facing == "down":
        rect(4, hy, 8, 3, hair)          # fringe
        px(4, hy + 3, hair)
        px(11, hy + 3, hair)
        px(4, hy + 4, hair)              # side locks
        px(11, hy + 4, hair)
        px(5, hy + 1, hairL)
        px(6, hy + 5, outline)           # eyes
        px(10, hy + 5, outline)
        px(8, hy + 7, skinD)             # mouth
    else:                                 # right (left mirrors below)
        rect(4, hy, 8, 3, hair)
        rect(4, hy, 2, 6, hair)          # back-of-head hair
        px(5, hy + 1, hairL)
        px(10, hy + 5, outline)          # front eye
        px(9, hy + 7, skinD)

    if facing == "left":
        cell = s.subsurface((ox, oy, FW, FH)).copy()
        cell = pygame.transform.flip(cell, True, False)
        s.fill((0, 0, 0, 0), (ox, oy, FW, FH))
        s.blit(cell, (ox, oy))


def character_sheet(skin, hair, shirt, pants, shoe=(64, 64, 78),
                    outline=(30, 30, 40)) -> pygame.Surface:
    sheet = pygame.Surface((4 * FW, len(DIRS) * FH), pygame.SRCALPHA)
    for r, facing in enumerate(DIRS):
        for frame in range(4):
            _char_cell(sheet, frame * FW, r * FH, facing, frame,
                       skin, hair, shirt, pants, shoe, outline)
    return sheet
