"""Overworld scene: tile-grid movement with smooth interpolation,
collision, NPC interaction, warps, and tall-grass encounters."""
from __future__ import annotations

import json
import os

import pygame

from ..core.pokemon import PokemonState
from .battle_scene import BattleScene
from .config import (A, ASSET_DIR, DIRS, DOWN, ENCOUNTER_CHANCE, LEFT,
                     LOGICAL_H, LOGICAL_W, RIGHT, TILE, TURN_FRAMES, UP,
                     WALK_SPEED)
from .dialog import DialogScene
from .scene import Scene
from .tilemap import TileMap


class Npc:
    def __init__(self, spawn):
        self.tile = spawn.tile
        self.name = spawn.name
        self.facing = spawn.facing
        self.dialog = spawn.dialog
        self.heal = spawn.heal


class OverworldScene(Scene):
    def __init__(self, game):
        super().__init__(game)
        self._encounters = json.load(open(os.path.join(ASSET_DIR,
                                                       "encounters.json")))
        self.map: TileMap = None
        self.npcs: list[Npc] = []
        self.moving = False
        self.move_px = 0
        self.turn_cool = 0
        self.load_map(game.state.map_id, game.state.tile)

    # ── world management ─────────────────────────────────────────────
    def load_map(self, map_id: str, tile=None) -> None:
        self.map = TileMap(map_id)
        self.game.state.map_id = map_id
        self.game.state.tile = tuple(tile if tile is not None else self.map.spawn)
        self.npcs = [Npc(s) for s in self.map.npcs]
        self.moving = False
        self.move_px = 0

    def _occupied(self, x, y) -> bool:
        return any(n.tile == (x, y) for n in self.npcs)

    def _walkable(self, x, y) -> bool:
        return not self.map.blocked(x, y) and not self._occupied(x, y)

    # ── input ────────────────────────────────────────────────────────
    def handle(self, inp) -> None:
        """Authentic grid movement: a step, once started, always
        completes the full tile; tapping a new direction turns in place
        first; holding walks tile by tile."""
        st = self.game.state
        if self.moving:
            return  # committed to the current grid step
        if A in inp.pressed:
            self._interact()
            return
        d = next((n for n in (UP, DOWN, LEFT, RIGHT) if n in inp.held), None)
        if d is None:
            return
        if st.facing != d:
            st.facing = d
            self.turn_cool = TURN_FRAMES  # tap-to-turn, no step yet
            return
        if self.turn_cool > 0:
            return  # still pivoting; hold to start walking
        dx, dy = DIRS[d]
        nx, ny = st.tile[0] + dx, st.tile[1] + dy
        if self._walkable(nx, ny):
            self.moving = True
            self.move_px = 0
            self._dest = (nx, ny)

    def _interact(self) -> None:
        st = self.game.state
        dx, dy = DIRS[st.facing]
        front = (st.tile[0] + dx, st.tile[1] + dy)
        for npc in self.npcs:
            if npc.tile == front:
                opposite = {"up": "down", "down": "up",
                            "left": "right", "right": "left"}
                npc.facing = opposite[st.facing]

                def close(npc=npc):
                    if npc.heal:
                        self.game.state.heal_party()
                self.game.push(DialogScene(self.game, npc.dialog, on_close=close))
                return
        sign = self.map.signs.get(front)
        if sign:
            self.game.push(DialogScene(self.game, sign.dialog))

    # ── simulation ───────────────────────────────────────────────────
    def update(self) -> None:
        if self.turn_cool > 0 and not self.moving:
            self.turn_cool -= 1
        if not self.moving:
            return
        self.move_px += WALK_SPEED
        if self.move_px >= TILE:
            self.game.state.tile = self._dest
            self.moving = False
            self.move_px = 0
            self._on_arrive()

    def _on_arrive(self) -> None:
        st = self.game.state
        warp = self.map.warps.get(st.tile)
        if warp:
            st.facing = warp.facing
            self.load_map(warp.to_map, warp.to_tile)
            return
        if self.map.is_grass(*st.tile) and st.first_able():
            if st.rng.randint(1, ENCOUNTER_CHANCE) == 1:
                self._wild_encounter()

    def _wild_encounter(self) -> None:
        st = self.game.state
        table = self._encounters.get(self.map.id)
        if not table:
            return
        weights = [e["weight"] for e in table]
        entry = st.rng.choices(table, weights=weights, k=1)[0]
        level = st.rng.randint(entry["min"], entry["max"])
        wild = PokemonState.generate(st.data, entry["species"], level, rng=st.rng)
        self.game.push(BattleScene(self.game, [wild], wild=True))

    # ── render ───────────────────────────────────────────────────────
    def _player_px(self) -> tuple:
        st = self.game.state
        x, y = st.tile[0] * TILE, st.tile[1] * TILE
        if self.moving:
            dx, dy = DIRS[st.facing]
            x += dx * self.move_px
            y += dy * self.move_px
        return x, y

    def draw(self, surf) -> None:
        px, py = self._player_px()
        mw, mh = self.map.px_size
        cam_x = max(0, min(px - LOGICAL_W // 2 + TILE // 2, mw - LOGICAL_W))
        cam_y = max(0, min(py - LOGICAL_H // 2 + TILE // 2, mh - LOGICAL_H))
        self.map.draw(surf, cam_x, cam_y)
        npc_img = self.game.assets.npc
        for npc in self.npcs:
            surf.blit(npc_img[npc.facing],
                      (npc.tile[0] * TILE - cam_x, npc.tile[1] * TILE - cam_y))
        surf.blit(self.game.assets.player[self.game.state.facing],
                  (px - cam_x, py - cam_y))
