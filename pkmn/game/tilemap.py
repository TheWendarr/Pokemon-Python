"""Tiled (.tmx) map wrapper: tile rendering plus the gameplay queries
the overworld needs (collision, tall grass, warps, NPC spawns)."""
from __future__ import annotations

import os
from dataclasses import dataclass

import pygame
from pytmx import TiledTileLayer
from pytmx.util_pygame import load_pygame

from .config import ASSET_DIR, TILE
from .contract import (BASE_LAYER, DIR_BLOCK_FLAGS, DIRECTIONS,
                       LEDGE_FLAGS, rebase)


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
    script: str = ""               # id in scripts.json (preferred)
    visible_unless: str = ""       # hide NPC when this flag is set


@dataclass
class TrainerSpawn:
    tile: tuple
    name: str
    facing: str
    sight: int
    party: str                     # "species:lv|species:lv"
    prize: int
    flag: str                      # defeat flag
    before: list
    after: list


@dataclass
class TriggerSpawn:
    tile: tuple
    script: str
    unless_flag: str = ""
    when: str = "step"             # 'step' | 'enter' (map load)
    time: str = ""                 # phases it may fire in (e.g. "night,evening")


@dataclass
class SignSpawn:
    tile: tuple
    dialog: list
    script: str = ""


class TileMap:
    def __init__(self, map_id: str, root: str = ASSET_DIR):
        self.id = map_id
        self.tmx = load_pygame(os.path.join(root, "maps", f"{map_id}.tmx"))
        self.props = dict(getattr(self.tmx, "properties", {}) or {})
        self.width = self.tmx.width
        self.height = self.tmx.height
        # seamless-overworld metadata: per-edge neighbour + alignment offset.
        # A map with no connections is a discrete, warp-linked map.
        self.connections: dict[str, tuple] = {}
        for d in DIRECTIONS:
            nb = self.props.get(f"connect_{d}")
            if nb:
                self.connections[d] = (nb,
                                       int(self.props.get(f"offset_{d}") or 0))
        self.is_seamless = bool(self.connections)
        self.border = self.props.get("border")     # gid filling open edges
        self._border_img = None
        self.cut: set[tuple] = set()                # tiles cleared by Cut
        # All tile layers, in draw order (bottom -> top). pytmx indexes
        # tile lookups by the layer's position among *all* layers, so we
        # keep the global indices. BASE_LAYER must be present.
        self.tile_layers = [i for i, lyr in enumerate(self.tmx.layers)
                            if isinstance(lyr, TiledTileLayer)]
        self.ground = self.tmx.get_layer_by_name(BASE_LAYER)   # base (required)
        # animated tiles: base gid -> [(frame_gid, duration_ms), ...]
        self.anim: dict[int, list] = {}
        for gid, props in (getattr(self.tmx, "tile_properties", {}) or {}).items():
            frames = props.get("frames") if props else None
            if frames:
                self.anim[gid] = [(f.gid, f.duration) for f in frames]
        self.warps: dict[tuple, Warp] = {}
        self.npcs: list[NpcSpawn] = []
        self.trainers: list[TrainerSpawn] = []
        self.triggers: list[TriggerSpawn] = []
        self.signs: dict[tuple, SignSpawn] = {}
        self.spawn = (1, 1)
        self._tile_cache: dict = {}                 # native tile img -> scaled
        tw, th = self.tmx.tilewidth, self.tmx.tileheight
        for obj in self.tmx.objects:
            t = (int(obj.x // tw), int(obj.y // th))
            p = obj.properties
            if obj.name == "warp":
                self.warps[t] = Warp(t, p["to_map"],
                                     (int(p["to_x"]), int(p["to_y"])),
                                     p.get("facing", "down"))
            elif obj.name == "npc":
                self.npcs.append(NpcSpawn(
                    t, p.get("display", "NPC"), p.get("facing", "down"),
                    [s for s in p.get("dialog", "...").split("|")],
                    bool(p.get("heal", False)),
                    p.get("script", ""), p.get("visible_unless", "")))
            elif obj.name == "trainer":
                self.trainers.append(TrainerSpawn(
                    t, p.get("display", "Trainer"), p.get("facing", "down"),
                    int(p.get("sight", 3)), p.get("party", "patrat:3"),
                    int(p.get("prize", 100)), p.get("flag", f"beat_{t[0]}_{t[1]}"),
                    p.get("before", "...").split("|"),
                    p.get("after", "...").split("|")))
            elif obj.name == "trigger":
                self.triggers.append(TriggerSpawn(
                    t, p.get("script", ""), p.get("unless_flag", ""),
                    p.get("when", "step"), p.get("time", "")))
            elif obj.name == "sign":
                self.signs[t] = SignSpawn(t, p.get("dialog", "...").split("|"),
                                          p.get("script", ""))
            elif obj.name == "spawn":
                self.spawn = t

    # ── queries ──────────────────────────────────────────────────────
    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def _merged(self, x: int, y: int) -> dict:
        """Behaviour flags OR'd across every tile layer at a cell.

        A cell is blocked/grass/surf/... if *any* layer's tile carries
        that flag -- so an overhead tree on an upper layer still blocks,
        and tall grass painted over a path still triggers encounters.
        """
        if not self.in_bounds(x, y):
            return {"blocked": True}
        out: dict = {}
        for li in self.tile_layers:
            tp = self.tmx.get_tile_properties(x, y, li)
            if tp:
                for k, v in tp.items():
                    if v:
                        out[k] = v
        return out

    def blocked(self, x: int, y: int) -> bool:
        if (x, y) in self.cut:                      # cut down -> walkable
            return False
        p = self._merged(x, y)
        if p.get("blocked"):
            return True
        return any(p.get(f) for f in LEDGE_FLAGS.values())   # ledges block

    def is_grass(self, x: int, y: int) -> bool:
        return bool(self._merged(x, y).get("grass"))

    def is_surf(self, x: int, y: int) -> bool:
        return bool(self._merged(x, y).get("surf"))

    def is_cuttable(self, x: int, y: int) -> bool:
        return ((x, y) not in self.cut
                and bool(self._merged(x, y).get("cuttable")))

    def has_ledge(self, x: int, y: int, facing: str) -> bool:
        """True if a tile is a ledge jumped over by moving `facing`."""
        return bool(self._merged(x, y).get(LEDGE_FLAGS.get(facing, "")))

    def passable(self, x: int, y: int, direction: str) -> bool:
        """Is this tile's edge open for crossing in `direction`? This is the
        *directional* (partial) check only -- full solidity and surf access
        are decided by the walkability path, so a blocked+surf water tile is
        still crossable here. Out-of-bounds is never crossable."""
        if (x, y) in self.cut:
            return True
        if not self.in_bounds(x, y):
            return False
        m = self._merged(x, y)
        return not m.get(DIR_BLOCK_FLAGS.get(direction, ""))

    def do_cut(self, x: int, y: int) -> bool:
        if self.is_cuttable(x, y):
            self.cut.add((x, y))
            return True
        return False

    def border_image(self):
        """The scaled tile that fills this map's unconnected edges, or
        None to leave them empty (the GB 'creepy tall grass' effect)."""
        if self.border is None:
            return None
        if self._border_img is None:
            img = self.tmx.get_tile_image_by_gid(int(self.border))
            self._border_img = self._scaled(img) if img else None
        return self._border_img

    def _is_over(self, x: int, y: int, li: int) -> bool:
        tp = self.tmx.get_tile_properties(x, y, li)
        return bool(tp and tp.get("over"))

    def _anim_gid(self, gid: int) -> int:
        """Current frame gid for an animated tile (cycles on the wall clock),
        or the gid unchanged for a static tile."""
        fr = self.anim.get(gid)
        if not fr:
            return gid
        total = sum(d for _, d in fr) or 1
        t = pygame.time.get_ticks() % total
        acc = 0
        for fg, d in fr:
            acc += d
            if t < acc:
                return fg
        return fr[-1][0]

    def _cell_image(self, x: int, y: int, li: int):
        """Scaled image for one layer at a cell, or None. Resolves tile
        animation; a cuttable tile on a cut cell is hidden so the layers
        beneath it show through."""
        gid = self.tmx.get_tile_gid(x, y, li)
        if not gid:
            return None
        if (x, y) in self.cut:
            tp = self.tmx.get_tile_properties(x, y, li)
            if tp and tp.get("cuttable"):
                return None
        img = self.tmx.get_tile_image_by_gid(self._anim_gid(gid))
        return self._scaled(img) if img else None

    def draw_cell(self, surf, lx: int, ly: int, sx: int, sy: int,
                  over: bool = False) -> None:
        """Blit every tile layer at one cell that matches the draw phase.
        Below pass (over=False) also paints the border under a cut tile so
        a felled obstacle leaves ground, not a hole."""
        if not over and (lx, ly) in self.cut:
            b = self.border_image()
            if b:
                surf.blit(b, (sx, sy))
        for li in self.tile_layers:
            if self._is_over(lx, ly, li) != over:
                continue
            img = self._cell_image(lx, ly, li)
            if img:
                surf.blit(img, (sx, sy))

    # ── drawing ──────────────────────────────────────────────────────
    def _scaled(self, img):
        """Upscale an authored tile (16px or 32px) to the render TILE size
        with nearest-neighbour, cached so it happens once per tile."""
        key = id(img)
        out = self._tile_cache.get(key)
        if out is None or out.get_width() != TILE:
            out = pygame.transform.scale(img, (TILE, TILE))
            self._tile_cache[key] = out
        return out

    def draw(self, surf: pygame.Surface, cam_x: int, cam_y: int,
             over: bool = False) -> None:
        x0 = max(0, cam_x // TILE)
        y0 = max(0, cam_y // TILE)
        x1 = min(self.width, (cam_x + surf.get_width()) // TILE + 2)
        y1 = min(self.height, (cam_y + surf.get_height()) // TILE + 2)
        for y in range(y0, y1):
            for x in range(x0, x1):
                self.draw_cell(surf, x, y, x * TILE - cam_x,
                               y * TILE - cam_y, over)

    @property
    def px_size(self) -> tuple:
        return self.width * TILE, self.height * TILE


class World:
    """A region's maps plus the recursive lookup that stitches connected
    maps into one continuous overworld.

    Everything seamless falls out of one primitive, `resolve` -- exactly
    as Pokemon Gen 1's get_tile does: an in-bounds coordinate returns its
    own tile; an off-edge coordinate recurses into the neighbour declared
    on that edge (shifted by the connection offset and the crossed map's
    size); an edge with no neighbour returns None (a border tile / wall).
    Rendering, collision, and border fill all call through it, so the
    stitch is defined in exactly one place.
    """

    def __init__(self, root: str = ASSET_DIR):
        self.root = root
        self.maps: dict[str, TileMap] = {}

    def get(self, map_id: str) -> TileMap:
        tm = self.maps.get(map_id)
        if tm is None:
            tm = TileMap(map_id, self.root)        # raises if truly missing
            self.maps[map_id] = tm
        return tm

    def _try(self, map_id: str):
        try:
            return self.get(map_id)
        except Exception:
            return None                            # bad neighbour -> border

    def resolve(self, map_id: str, x: int, y: int, depth: int = 0):
        """(TileMap, local_x, local_y) for a tile, following connections
        across edges, or None when it falls beyond an unconnected edge."""
        tm = self._try(map_id)
        if tm is None or depth > 16:
            return None
        if tm.in_bounds(x, y):
            return tm, x, y
        for d, off_edge in (("north", y < 0), ("south", y >= tm.height),
                            ("west", x < 0), ("east", x >= tm.width)):
            if off_edge:
                conn = tm.connections.get(d)
                if not conn:
                    return None
                nb_id, offset = conn
                nb = self._try(nb_id)
                if nb is None:
                    return None
                nx, ny = rebase(d, x, y, tm.width, tm.height,
                                nb.width, nb.height, offset)
                return self.resolve(nb_id, nx, ny, depth + 1)
        return None

    # collision / encounter queries that respect connections
    def blocked(self, map_id: str, x: int, y: int) -> bool:
        r = self.resolve(map_id, x, y)
        return r is None or r[0].blocked(r[1], r[2])

    def is_grass(self, map_id: str, x: int, y: int) -> bool:
        r = self.resolve(map_id, x, y)
        return bool(r) and r[0].is_grass(r[1], r[2])

    def is_surf(self, map_id: str, x: int, y: int) -> bool:
        r = self.resolve(map_id, x, y)
        return bool(r) and r[0].is_surf(r[1], r[2])

    def passable(self, map_id: str, x: int, y: int, direction: str) -> bool:
        r = self.resolve(map_id, x, y)
        return bool(r) and r[0].passable(r[1], r[2], direction)

    def draw(self, surf: pygame.Surface, map_id: str,
             cam_x: int, cam_y: int, over: bool = False) -> None:
        """Draw the viewport across map boundaries via `resolve`; the
        camera is not clamped, so neighbours scroll seamlessly into view
        and open edges show the current map's border tile. Called twice
        per frame: below the player (over=False) then above (over=True)."""
        cur = self._try(map_id)
        x0, y0 = cam_x // TILE, cam_y // TILE        # floor (handles cam<0)
        x1 = (cam_x + surf.get_width()) // TILE
        y1 = (cam_y + surf.get_height()) // TILE
        for ty in range(y0, y1 + 1):
            for tx in range(x0, x1 + 1):
                sx, sy = tx * TILE - cam_x, ty * TILE - cam_y
                r = self.resolve(map_id, tx, ty)
                if r:
                    tm, lx, ly = r
                    tm.draw_cell(surf, lx, ly, sx, sy, over)
                elif not over and cur is not None:
                    b = cur.border_image()
                    if b:
                        surf.blit(b, (sx, sy))
