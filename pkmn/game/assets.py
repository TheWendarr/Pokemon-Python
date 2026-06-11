"""Asset loading + procedural placeholder art.

All art is generated (tools/make_assets.py) or synthesized at runtime
(species battlers), so the repository ships zero third-party assets.
"""
from __future__ import annotations

import os

import pygame

from .config import ASSET_DIR, TILE


class Assets:
    def __init__(self, root: str = ASSET_DIR):
        self.root = root
        self.player = self._strip(os.path.join(root, "player.png"))
        self.npc = self._strip(os.path.join(root, "npc.png"))
        self.font = pygame.font.Font(None, 14)
        self.font_big = pygame.font.Font(None, 18)
        self._battlers: dict[str, pygame.Surface] = {}

    @staticmethod
    def _strip(path) -> dict[str, pygame.Surface]:
        """64x16 strip -> {facing: 16x16 frame}."""
        sheet = pygame.image.load(path).convert_alpha()
        out = {}
        for i, facing in enumerate(("down", "up", "left", "right")):
            out[facing] = sheet.subsurface((i * TILE, 0, TILE, TILE))
        return out

    def battler(self, species_id: str, name: str) -> pygame.Surface:
        """Deterministic placeholder sprite: hashed hue blob + initial."""
        if species_id in self._battlers:
            return self._battlers[species_id]
        h = sum(ord(c) * (i + 7) for i, c in enumerate(species_id))
        color = pygame.Color(0)
        color.hsva = (h % 360, 65, 85, 100)
        dark = pygame.Color(0)
        dark.hsva = (h % 360, 70, 50, 100)
        s = pygame.Surface((48, 48), pygame.SRCALPHA)
        pygame.draw.circle(s, dark, (24, 26), 21)
        pygame.draw.circle(s, color, (24, 26), 18)
        pygame.draw.circle(s, (255, 255, 255), (17, 20), 4)
        pygame.draw.circle(s, (255, 255, 255), (30, 20), 4)
        pygame.draw.circle(s, (20, 20, 30), (18, 21), 2)
        pygame.draw.circle(s, (20, 20, 30), (31, 21), 2)
        letter = pygame.font.Font(None, 20).render(name[:1], True, (255, 255, 255))
        s.blit(letter, letter.get_rect(center=(24, 36)))
        self._battlers[species_id] = s
        return s
