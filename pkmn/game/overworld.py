"""Overworld scene: tile-grid movement with full-tile commitment and
tap-to-turn, collision, NPCs, signs, warps, tall-grass encounters,
step-on/auto triggers, trainer line-of-sight battles, and the event
script runner that glues them together."""
from __future__ import annotations

import json
import os

import pygame

from ..core.pokemon import PokemonState
from .battle_scene import BattleScene
from .config import (A, ASSET_DIR, DIRS, DOWN, ENCOUNTER_CHANCE, LEFT,
                     LOGICAL_H, LOGICAL_W, RIGHT, START, TILE, TURN_FRAMES,
                     UP, WALK_SPEED, SCALE as S)
from .dialog import DialogScene
from .scene import Scene
from .script import DONE, ScriptRunner
from .tilemap import TileMap, World

OPPOSITE = {"up": "down", "down": "up", "left": "right", "right": "left"}
JUMP_H = int(TILE * 0.6)        # ledge-jump arc height in px


class Npc:
    def __init__(self, spawn):
        self.tile = spawn.tile
        self.name = spawn.name
        self.facing = spawn.facing
        self.dialog = getattr(spawn, "dialog", ["..."])
        self.heal = getattr(spawn, "heal", False)
        self.script = getattr(spawn, "script", "")
        self.hidden = False
        # walking animation (cutscenes)
        self.path: list = []
        self.move_px = 0
        self.walk_t = 0.0


class Trainer(Npc):
    def __init__(self, spawn):
        super().__init__(spawn)
        self.sight = spawn.sight
        self.party = spawn.party
        self.prize = spawn.prize
        self.flag = spawn.flag
        self.before = spawn.before
        self.after = spawn.after


class OverworldScene(Scene):
    def __init__(self, game):
        super().__init__(game)
        root = game.game_dir
        try:
            self._encounters = json.load(open(os.path.join(
                root, "encounters.json")))
        except FileNotFoundError:
            self._encounters = {}
        try:
            self.scripts = json.load(open(os.path.join(root, "scripts.json")))
        except FileNotFoundError:
            self.scripts = {}
        self.map: TileMap = None
        self.npcs: list[Npc] = []
        self.moving = False
        self.move_px = 0
        self.walk_t = 0.0
        self.turn_cool = 0
        self._running = False
        self.script: ScriptRunner | None = None
        self.cutscene: dict | None = None   # {'npc', 'pause', 'then'}
        self.world = World(game.game_dir)   # caches maps; stitches neighbours
        self.surfing = False                # riding water (Surf)
        self.jump = False                   # mid ledge-hop
        self._move_dist = TILE              # px for the current step (2x on a jump)
        self.load_map(game.state.map_id, game.state.tile)

    # ── world management ─────────────────────────────────────────────
    def load_map(self, map_id: str, tile=None) -> None:
        flags = self.game.state.flags
        self.map = self.world.get(map_id)
        self.game.state.map_id = map_id
        self.game.state.tile = tuple(tile if tile is not None else self.map.spawn)
        self.npcs = [Npc(s) for s in self.map.npcs
                     if not (s.visible_unless and s.visible_unless in flags)]
        self.npcs += [Trainer(s) for s in self.map.trainers]
        self.moving = False
        self.move_px = 0
        self.jump = False
        self.script = None
        self.cutscene = None
        self.surfing = self.map.is_surf(*self.game.state.tile)
        self.game.audio.play_music(self.map.props.get("music", "route"))
        for trig in self.map.triggers:        # 'auto' triggers on entry
            if trig.when == "enter" and not (
                    trig.unless_flag and trig.unless_flag in flags):
                self.start_script(self.scripts.get(trig.script, []))
                break

    def find_npc(self, name: str):
        for n in self.npcs:
            if n.name == name and not n.hidden:
                return n
        return None

    def hide_npc(self, name: str) -> None:
        npc = self.find_npc(name)
        if npc:
            npc.hidden = True

    def _occupied(self, x, y) -> bool:
        return any(n.tile == (x, y) and not n.hidden for n in self.npcs)

    def _blocked(self, x, y) -> bool:
        return (self.world.blocked(self.map.id, x, y) if self.map.is_seamless
                else self.map.blocked(x, y))

    def _is_surf(self, x, y) -> bool:
        return (self.world.is_surf(self.map.id, x, y) if self.map.is_seamless
                else self.map.is_surf(x, y))

    def _has_ledge(self, x, y, facing) -> bool:
        if self.map.is_seamless:
            r = self.world.resolve(self.map.id, x, y)
            return bool(r) and r[0].has_ledge(r[1], r[2], facing)
        return self.map.has_ledge(x, y, facing)

    def _try_cut(self, x, y) -> bool:
        if not self.game.state.can_cut:
            return False
        if self.map.is_seamless:
            r = self.world.resolve(self.map.id, x, y)
            return bool(r) and r[0].do_cut(r[1], r[2])
        return self.map.do_cut(x, y)

    def _walkable(self, x, y) -> bool:
        if self._occupied(x, y):
            return False
        if self._is_surf(x, y):                # water: only if able to surf
            return self.surfing or self.game.state.can_surf
        return not self._blocked(x, y)

    def _cross_to(self, tm: TileMap, tile: tuple) -> None:
        """Seamless boundary crossing: make a neighbour the current map and
        rebase the player onto it -- no fade, no 'enter' triggers (that is a
        door's job). Rendering already drew the neighbour, so it's invisible.
        Objects (NPCs/trainers) activate as you cross, like the source game."""
        st = self.game.state
        flags = st.flags
        self.map = tm
        st.map_id = tm.id
        st.tile = tuple(tile)
        self.npcs = [Npc(s) for s in tm.npcs
                     if not (s.visible_unless and s.visible_unless in flags)]
        self.npcs += [Trainer(s) for s in tm.trainers]
        self.surfing = tm.is_surf(*tile)

    # ── scripts & cutscenes ──────────────────────────────────────────
    def start_script(self, steps, npc=None) -> None:
        if not steps:
            return
        self.script = ScriptRunner(self.game, self, steps)
        if self.script.advance() == DONE:
            self.script = None

    def on_resume(self) -> None:
        st = self.game.state
        if self.map is not None and self.map.id != st.map_id:
            self.load_map(st.map_id, st.tile)   # whiteout teleported us
            return
        if self.script is not None:
            if self.script.resume() == DONE:
                self.script = None
        if self.map is not None:              # resume the field track after battle
            self.game.audio.play_music(self.map.props.get("music", "route"))

    def start_npc_walk(self, npc, dest: tuple) -> None:
        """Straight-line walk (scripts are responsible for clear paths)."""
        path = []
        x, y = npc.tile
        dx = (dest[0] > x) - (dest[0] < x)
        dy = (dest[1] > y) - (dest[1] < y)
        while x != dest[0]:
            x += dx
            path.append((x, y))
        while y != dest[1]:
            y += dy
            path.append((x, y))
        npc.path = path
        npc.move_px = 0

    def _trainer_spotted(self, trainer: Trainer) -> None:
        trainer_steps = []
        tx, ty = trainer.tile
        px, py = self.game.state.tile
        dx, dy = DIRS[trainer.facing]
        while (tx + dx, ty + dy) != (px, py):
            tx, ty = tx + dx, ty + dy
            trainer_steps.append((tx, ty))
        self.cutscene = {"npc": trainer, "pause": 30}
        trainer.path = trainer_steps
        self.game.state.facing = OPPOSITE[trainer.facing]

        def begin_battle():
            self.start_script([
                {"say": "|".join(trainer.before)},
                {"battle": {"trainer": trainer.name, "party": trainer.party,
                            "prize": trainer.prize, "flag": trainer.flag}},
            ])
        self.cutscene["then"] = begin_battle

    def _check_trainer_los(self) -> bool:
        ptile = self.game.state.tile
        for n in self.npcs:
            if not isinstance(n, Trainer) or n.hidden \
                    or n.flag in self.game.state.flags:
                continue
            x, y = n.tile
            dx, dy = DIRS[n.facing]
            for _ in range(n.sight):
                x, y = x + dx, y + dy
                if self.map.blocked(x, y):
                    break
                if (x, y) == ptile:
                    self._trainer_spotted(n)
                    return True
                if self._occupied(x, y):
                    break
        return False

    # ── input ────────────────────────────────────────────────────────
    def handle(self, inp) -> None:
        """Authentic grid movement: a step, once started, always
        completes the full tile; tapping a new direction turns in place
        first; holding walks tile by tile. Hold B to run."""
        from .config import B
        self._running = B in inp.held
        st = self.game.state
        if self.cutscene is not None or self.script is not None:
            return  # events own the player during cutscenes
        if self.moving:
            return  # committed to the current grid step
        if START in inp.pressed:
            from .menus import PauseScene
            self.game.push(PauseScene(self.game))
            return
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
        if self._has_ledge(nx, ny, d):           # one-way ledge: hop over it
            lx, ly = nx + dx, ny + dy
            if (not self._blocked(lx, ly) and not self._is_surf(lx, ly)
                    and not self._occupied(lx, ly)):
                self.moving, self.move_px = True, 0
                self._dest, self._move_dist, self.jump = (lx, ly), 2 * TILE, True
            return
        if self._walkable(nx, ny):
            self.moving, self.move_px = True, 0
            self._dest, self._move_dist, self.jump = (nx, ny), TILE, False

    def _interact(self) -> None:
        st = self.game.state
        dx, dy = DIRS[st.facing]
        front = (st.tile[0] + dx, st.tile[1] + dy)
        for npc in self.npcs:
            if npc.tile != front or npc.hidden:
                continue
            npc.facing = OPPOSITE[st.facing]
            if isinstance(npc, Trainer):
                if not self.game.feature("trainers"):
                    self.game.push(DialogScene(self.game, npc.before))
                    return
                if npc.flag in st.flags:
                    self.start_script([{"say": "|".join(npc.after)}])
                else:
                    self.start_script([
                        {"say": "|".join(npc.before)},
                        {"battle": {"trainer": npc.name, "party": npc.party,
                                    "prize": npc.prize, "flag": npc.flag}}])
                return
            if npc.script and npc.script in self.scripts:
                self.start_script(self.scripts[npc.script], npc)
            else:
                def close(npc=npc):
                    if npc.heal:
                        self.game.state.heal_party()
                self.game.push(DialogScene(self.game, npc.dialog, on_close=close))
            return
        if self._try_cut(*front):
            return
        sign = self.map.signs.get(front)
        if sign:
            if sign.script and sign.script in self.scripts:
                self.start_script(self.scripts[sign.script])
            else:
                self.game.push(DialogScene(self.game, sign.dialog))

    # ── simulation ───────────────────────────────────────────────────
    def update(self) -> None:
        if self.game.pending_warp:                  # Escape Rope / item warp
            mid, tile, facing = self.game.pending_warp
            self.game.pending_warp = None
            self.load_map(mid, tile)
            if facing:
                self.game.state.facing = facing
            self.moving = False
            return
        self._update_cutscene()
        self._update_npc_walks()
        if self.turn_cool > 0 and not self.moving:
            self.turn_cool -= 1
        if not self.moving:
            self.walk_t = 0.0
            return
        speed = WALK_SPEED
        if self._running and self.game.feature("running"):
            speed *= 2
        self.move_px += speed
        self.walk_t += speed
        if self.move_px >= self._move_dist:
            self.game.state.tile = self._dest
            self.moving = False
            self.move_px = 0
            self.jump = False
            self._on_arrive()
            self.surfing = self._is_surf(*self.game.state.tile)

    def _update_cutscene(self) -> None:
        cs = self.cutscene
        if cs is None:
            return
        if cs["pause"] > 0:
            cs["pause"] -= 1
            return
        if cs["npc"].path:
            return  # still walking over (animated in _update_npc_walks)
        then = cs.get("then")
        self.cutscene = None
        if then:
            then()

    def _update_npc_walks(self) -> None:
        for npc in self.npcs:
            if not npc.path:
                continue
            nxt = npc.path[0]
            npc.facing = ("left" if nxt[0] < npc.tile[0] else
                          "right" if nxt[0] > npc.tile[0] else
                          "up" if nxt[1] < npc.tile[1] else "down")
            npc.move_px += WALK_SPEED
            npc.walk_t += WALK_SPEED
            if npc.move_px >= TILE:
                npc.tile = npc.path.pop(0)
                npc.move_px = 0
                if not npc.path:
                    npc.walk_t = 0.0
                if not npc.path and self.cutscene is None \
                        and self.script is not None:
                    if self.script.resume() == DONE:  # move_npc finished
                        self.script = None

    def _on_arrive(self) -> None:
        st = self.game.state
        if self.map.is_seamless and not self.map.in_bounds(*st.tile):
            r = self.world.resolve(self.map.id, *st.tile)
            if r:
                self._cross_to(r[0], (r[1], r[2]))   # st.tile now in-bounds
        warp = self.map.warps.get(st.tile)
        if warp:
            st.facing = warp.facing
            self.load_map(warp.to_map, warp.to_tile)
            return
        for trig in self.map.triggers:
            if trig.when == "step" and trig.tile == st.tile and not (
                    trig.unless_flag and trig.unless_flag in st.flags):
                self.start_script(self.scripts.get(trig.script, []))
                return
        if self.game.feature("trainers") and self._check_trainer_los():
            return
        repel = st.repel_steps > 0                  # counts down every step
        if repel:
            st.repel_steps -= 1
        if self.game.feature("encounters") and self.map.is_grass(*st.tile) \
                and st.first_able():
            if repel:
                return                              # repel keeps wild mons away
            chance = int(self.map.props.get(
                "encounter_chance",
                self.game.setting("encounter_chance", ENCOUNTER_CHANCE)))
            if st.rng.randint(1, max(1, chance)) == 1:
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
        self.game.push(BattleScene(self.game, [wild], wild=True,
                                   weather=self.map.props.get("weather")))

    # ── render ───────────────────────────────────────────────────────
    @staticmethod
    def _frame_idx(walk_t, moving, n) -> int:
        if not moving or n <= 1:
            return 0
        return (int(walk_t) // (TILE // 2)) % n   # 0,1,2,3 walk cycle

    def _player_px(self) -> tuple:
        st = self.game.state
        x, y = st.tile[0] * TILE, st.tile[1] * TILE
        if self.moving:
            dx, dy = DIRS[st.facing]
            x += dx * self.move_px
            y += dy * self.move_px
            if self.jump:                        # parabolic hop
                prog = self.move_px / self._move_dist
                y -= int(4 * prog * (1 - prog) * JUMP_H)
        return x, y

    def _npc_px(self, npc) -> tuple:
        x, y = npc.tile[0] * TILE, npc.tile[1] * TILE
        if npc.path and npc.move_px:
            nxt = npc.path[0]
            x += (nxt[0] - npc.tile[0]) * npc.move_px
            y += (nxt[1] - npc.tile[1]) * npc.move_px
        return x, y

    def draw(self, surf) -> None:
        px, py = self._player_px()
        cx = px - LOGICAL_W // 2 + TILE // 2
        cy = py - LOGICAL_H // 2 + TILE // 2
        if self.map.is_seamless:
            # world scrolls under a centred player; neighbours fill the edges
            self.world.draw(surf, self.map.id, cx, cy)
            cam_x, cam_y = cx, cy
        else:
            mw, mh = self.map.px_size
            cam_x = max(0, min(cx, max(0, mw - LOGICAL_W)))
            cam_y = max(0, min(cy, max(0, mh - LOGICAL_H)))
            self.map.draw(surf, cam_x, cam_y)
        npc_img = self.game.assets.npc
        for npc in self.npcs:
            if npc.hidden:
                continue
            nx, ny = self._npc_px(npc)
            frames = npc_img[npc.facing]
            img = frames[self._frame_idx(npc.walk_t, bool(npc.path),
                                         len(frames))]
            yoff = self.game.assets.npc_h - TILE
            surf.blit(img, (nx - cam_x, ny - cam_y - yoff))
            if self.cutscene and self.cutscene["npc"] is npc \
                    and self.cutscene["pause"] > 0:
                mark = self.game.assets.font_big.render("!", True, (200, 40, 40))
                surf.blit(mark, (nx - cam_x + 6 * S, ny - cam_y - 12 * S))
        pframes = self.game.assets.player[self.game.state.facing]
        pimg = pframes[self._frame_idx(self.walk_t, self.moving, len(pframes))]
        pyoff = self.game.assets.player_h - TILE
        st = self.game.state
        if self.jump:                                  # shadow on the ground
            dx, dy = DIRS[st.facing]
            gx, gy = st.tile[0] * TILE + dx * self.move_px, \
                st.tile[1] * TILE + dy * self.move_px
            sh = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
            pygame.draw.ellipse(sh, (0, 0, 0, 90),
                                (TILE // 4, TILE * 2 // 3, TILE // 2, TILE // 4))
            surf.blit(sh, (gx - cam_x, gy - cam_y))
        if self.surfing:                               # water mount under feet
            mt = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
            pygame.draw.ellipse(mt, (64, 150, 220),
                                (2, TILE // 2, TILE - 4, TILE // 2 - 2))
            pygame.draw.ellipse(mt, (150, 212, 246),
                                (6, TILE // 2 + 3, TILE - 12, TILE // 4))
            surf.blit(mt, (px - cam_x, py - cam_y))
        surf.blit(pimg, (px - cam_x, py - cam_y - pyoff))
        tint = {"rain": (40, 70, 130, 60), "sandstorm": (180, 150, 70, 60),
                "hail": (200, 220, 240, 55), "sun": (255, 220, 120, 35)}.get(
                    self.map.props.get("weather"))
        if tint:
            overlay = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
            overlay.fill(tint)
            surf.blit(overlay, (0, 0))
