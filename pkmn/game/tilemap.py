"""Tiled (.tmx) map wrapper: tile rendering plus the gameplay queries
the overworld needs (collision, tall grass, warps, NPC spawns)."""
from __future__ import annotations

import os
from dataclasses import dataclass

import pygame
from pytmx.util_pygame import load_pygame

from .config import ASSET_DIR, TILE


@dataclass
class Warp:
    tile: tuple
    to_map: str
    to_tile: tuple
    facing: str


@dataclass
class NpcSpawn:
    tile: tuple
    name: str
    facing: str
    dialog: list
    heal: bool


@dataclass
class SignSpawn:
    tile: tuple
    dialog: list


class TileMap:
    def __init__(self, map_id: str, root: str = ASSET_DIR):
        self.id = map_id
        self.tmx = load_pygame(os.path.join(root, "maps", f"{map_id}.tmx"))
        self.width = self.tmx.width
        self.height = self.tmx.height
        self.ground = self.tmx.get_layer_by_name("ground")
        self.warps: dict[tuple, Warp] = {}
        self.npcs: list[NpcSpawn] = []
        self.signs: dict[tuple, SignSpawn] = {}
        self.spawn = (1, 1)
        for obj in self.tmx.objects:
            t = (int(obj.x // TILE), int(obj.y // TILE))
            p = obj.properties
            if obj.name == "warp":
                self.warps[t] = Warp(t, p["to_map"],
                                     (int(p["to_x"]), int(p["to_y"])),
                                     p.get("facing", "down"))
            elif obj.name == "npc":
                self.npcs.append(NpcSpawn(
                    t, p.get("display", "NPC"), p.get("facing", "down"),
                    [s for s in p.get("dialog", "...").split("|")],
                    bool(p.get("heal", False))))
            elif obj.name == "sign":
                self.signs[t] = SignSpawn(t, p.get("dialog", "...").split("|"))
            elif obj.name == "spawn":
                self.spawn = t

    # ── queries ──────────────────────────────────────────────────────
    def _props(self, x: int, y: int) -> dict:
        if not (0 <= x < self.width and 0 <= y < self.height):
            return {"blocked": True}
        return self.tmx.get_tile_properties(x, y, 0) or {}

    def blocked(self, x: int, y: int) -> bool:
        return bool(self._props(x, y).get("blocked"))

    def is_grass(self, x: int, y: int) -> bool:
        return bool(self._props(x, y).get("grass"))

    # ── drawing ──────────────────────────────────────────────────────
    def draw(self, surf: pygame.Surface, cam_x: int, cam_y: int) -> None:
        x0 = max(0, cam_x // TILE)
        y0 = max(0, cam_y // TILE)
        x1 = min(self.width, (cam_x + surf.get_width()) // TILE + 2)
        y1 = min(self.height, (cam_y + surf.get_height()) // TILE + 2)
        for y in range(y0, y1):
            for x in range(x0, x1):
                img = self.tmx.get_tile_image(x, y, 0)
                if img:
                    surf.blit(img, (x * TILE - cam_x, y * TILE - cam_y))

    @property
    def px_size(self) -> tuple:
        return self.width * TILE, self.height * TILE
