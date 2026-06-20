"""Asset loading: overworld art is procedural (tools/make_assets.py),
while species *battlers* are real Gen 5 sprites fetched and cached by
pkmn/game/sprites.py, with the original hashed-hue blob as an offline
fallback. The repository itself still ships no third-party assets — the
sprite cache is populated on demand (or via `python -m pkmn.cli.sprites`).
"""
from __future__ import annotations

import os

import pygame

from . import sprites
from .config import ASSET_DIR, BASE_TILE, SCALE, SPRITE_PX, TILE


class Assets:
    def __init__(self, root: str = ASSET_DIR):
        self.root = root
        self.player, self.player_h = self._char_sheet(
            os.path.join(root, "player.png"))
        self.npc, self.npc_h = self._char_sheet(os.path.join(root, "npc.png"))
        self.font = pygame.font.Font(None, 14 * SCALE)
        self.font_big = pygame.font.Font(None, 18 * SCALE)
        self._battlers: dict[tuple, pygame.Surface] = {}

    @staticmethod
    def _char_sheet(path):
        """Load a character sheet -> ({facing: [frames]}, frame_height).

        Sheets are authored on the BASE_TILE grid (16px cells): a grid of
        4 rows (down, up, left, right) x N walk frames, each cell 16 wide
        x (height/4) tall. Frames are upscaled to the render TILE size at
        load (nearest, crisp). The legacy 64x16 single-frame strip is
        still accepted."""
        sheet = pygame.image.load(path).convert_alpha()
        w, h = sheet.get_size()
        facings = ("down", "up", "left", "right")
        bt = BASE_TILE
        scale = pygame.transform.scale
        if h == bt and w == 4 * bt:                       # legacy strip
            return ({f: [scale(sheet.subsurface((i * bt, 0, bt, bt)),
                               (TILE, TILE))]
                     for i, f in enumerate(facings)}, TILE)
        cols, fh = w // bt, h // 4                        # animated grid
        return ({f: [scale(sheet.subsurface((c * bt, r * fh, bt, fh)),
                           (bt * SCALE, fh * SCALE))
                     for c in range(cols)]
                 for r, f in enumerate(facings)}, fh * SCALE)

    def battler(self, species_id: str, name: str, *, dex: int | None = None,
                back: bool = False) -> pygame.Surface:
        """Real Gen 5 sprite (front, or back for the player's side),
        cached in memory and on disk. Falls back to a hashed-hue blob
        when the sprite isn't available (offline, or no dex given)."""
        key = (species_id, back)
        if key in self._battlers:
            return self._battlers[key]
        surf = self._real_sprite(dex, back) if dex else None
        if surf is None:
            surf = self._placeholder(species_id, name)
        self._battlers[key] = surf
        return surf

    @staticmethod
    def _real_sprite(dex: int, back: bool):
        path = sprites.sprite_path(dex, back=back)
        if not path:
            return None
        try:
            img = pygame.image.load(path).convert_alpha()
        except Exception:
            return None
        w = img.get_width()
        if w != SPRITE_PX:
            if SPRITE_PX > w and SPRITE_PX % w == 0:
                # crisp integer upscale (e.g. 96 -> 192); no detail lost
                img = pygame.transform.scale(img, (SPRITE_PX, SPRITE_PX))
            else:
                img = pygame.transform.smoothscale(img, (SPRITE_PX, SPRITE_PX))
        return img

    @staticmethod
    def _placeholder(species_id: str, name: str) -> pygame.Surface:
        h = sum(ord(c) * (i + 7) for i, c in enumerate(species_id))
        color = pygame.Color(0)
        color.hsva = (h % 360, 65, 85, 100)
        dark = pygame.Color(0)
        dark.hsva = (h % 360, 70, 50, 100)
        s = pygame.Surface((SPRITE_PX, SPRITE_PX), pygame.SRCALPHA)
        pygame.draw.circle(s, dark, (96, 104), 84)
        pygame.draw.circle(s, color, (96, 104), 72)
        pygame.draw.circle(s, (255, 255, 255), (68, 80), 16)
        pygame.draw.circle(s, (255, 255, 255), (120, 80), 16)
        pygame.draw.circle(s, (20, 20, 30), (72, 84), 8)
        pygame.draw.circle(s, (20, 20, 30), (124, 84), 8)
        letter = pygame.font.Font(None, 20 * SCALE).render(
            name[:1], True, (255, 255, 255))
        s.blit(letter, letter.get_rect(center=(96, 144)))
        return s
