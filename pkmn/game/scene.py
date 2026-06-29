"""Scene stack + input abstraction + the Game shell.

Scenes implement handle(inp) / update() / draw(surf). The stack draws
from the lowest opaque scene upward so dialogs can overlay the world.
Input is a plain object tests can poke directly — the pygame event pump
only feeds it, which keeps the whole client headless-testable.
"""
from __future__ import annotations

import os

import pygame

from ..data.repository import GameData
from .assets import Assets
from .audio import AudioManager
from . import keybinds
from . import daytime
from . import contract
import math

from .config import (A, B, DATA_DIR, DOWN, FPS, LEFT, LOGICAL_H, LOGICAL_W,
                     RIGHT, START, UP, WINDOW_H, WINDOW_W)
from .save import load_game
from .state import GameState

# Physical key bindings are configurable per Game (see pkmn.game.keybinds);
# Game builds self.keymap = {keycode: action} from the loaded bindings.


class Input:
    """`pressed` is edge-triggered (this frame), `held` is level."""

    def __init__(self):
        self.pressed: set = set()
        self.held: set = set()
        self.raw: set = set()          # raw keycodes this frame (rebind menu)
        self.key_downs: list = []      # (keycode, unicode) pairs this frame

    def press(self, name: str) -> None:
        self.pressed.add(name)
        self.held.add(name)

    def press_raw(self, code: int) -> None:
        self.raw.add(code)

    def release(self, name: str) -> None:
        self.held.discard(name)

    def clear_frame(self) -> None:
        self.pressed.clear()
        self.raw.clear()
        self.key_downs.clear()


class Scene:
    translucent = False   # if True, the scene below is drawn beneath

    def __init__(self, game: "Game"):
        self.game = game

    def handle(self, inp: Input) -> None: ...
    def update(self) -> None: ...
    def draw(self, surf) -> None: ...
    def on_resume(self) -> None: ...


class Game:
    """Owns the scene stack, game data, assets, and session state."""

    def __init__(self, *, headless: bool = False, seed: int | None = None,
                 data_dir: str | None = None, save_path: str | None = None,
                 game_dir: str = "game/assets", fullscreen: bool = False,
                 fill: bool = False, mute: bool = False,
                 controls_path: str | None = None, daynight=None,
                 cheat: bool = False):
        self.headless = headless
        if headless:
            os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
            os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
        pygame.init()
        self.fullscreen = False
        self.fill = fill                       # fill screen vs pixel-perfect
        if headless:
            self.window = pygame.display.set_mode((LOGICAL_W, LOGICAL_H))
        else:
            self._open_window(fullscreen)
        self.game_dir = game_dir
        self.manifest = self._load_manifest(game_dir)
        ev = self.manifest.get("engine_version", contract.ENGINE_VERSION)
        if not contract.compatible(ev):
            raise ValueError(
                f"region {self.manifest.get('name', game_dir)!r} targets "
                f"engine v{ev}, but this engine is v{contract.ENGINE_VERSION}. "
                f"This game requires a newer engine — update pokemon-python "
                f"or lower 'engine_version' in game.json.")
        pygame.display.set_caption(self.manifest.get("name", "pkmn"))
        self.canvas = pygame.Surface((LOGICAL_W, LOGICAL_H))
        self.data = GameData(data_dir or self.manifest.get("data_dir")
                             or DATA_DIR)
        self.assets = Assets(game_dir)
        self.save_path = save_path
        self._seed = seed
        loaded = load_game(self.data, save_path) if save_path else None
        self.state = loaded or GameState.new_game(
            self.data, manifest=self.manifest, seed=seed)
        self.scenes: list[Scene] = []
        self.pending_warp = None        # (map, tile, facing) -> overworld warps
        self.input = Input()
        self.last_battle = None    # winner of the most recent battle
        self.running = True
        self.audio = AudioManager(game_dir, manifest=self.manifest, mute=mute)
        self.controls_path = controls_path
        self.bindings = keybinds.load(controls_path)
        self.keymap = keybinds.resolve(self.bindings)
        dn = daynight if daynight is not None else self.setting("daynight", "auto")
        self.clock_hour = None
        if isinstance(dn, str) and dn.isdigit():
            self.clock_hour, dn = int(dn) % 24, "auto"
        self.daynight = dn
        self.cheat = cheat                 # cheat console enabled
        self.battle_bg = "field"          # set per map; battles read it

    def feature(self, name: str, default: bool = True) -> bool:
        """Designer toggle: manifest["features"][name]; default ON."""
        return bool(self.manifest.get("features", {}).get(name, default))

    def setting(self, name: str, default):
        return self.manifest.get("settings", {}).get(name, default)

    def apply_bindings(self, bindings: dict) -> None:
        """Adopt a new key->action mapping and persist it to controls_path."""
        self.bindings = keybinds.normalize(bindings)
        self.keymap = keybinds.resolve(self.bindings)
        keybinds.save(self.bindings, self.controls_path)

    def time_phase(self) -> str:
        """Current day/night phase: 'morning' | 'day' | 'evening' | 'night'."""
        dn = self.daynight
        if dn in (False, "off", "none", None):
            return "day"
        if dn in daytime.PHASES:                 # pinned to one phase
            return dn
        return daytime.current_phase(self.clock_hour)

    def whiteout_location(self):
        """Where the player reappears after whiting out: the manifest's
        'whiteout' location, else the start location. Tile None -> spawn."""
        w = self.manifest.get("whiteout") or self.manifest.get("start", {})
        tile = tuple(w["tile"]) if w.get("tile") else None
        return w.get("map") or self.state.map_id, tile, w.get("facing", "down")

    @staticmethod
    def _load_manifest(game_dir: str) -> dict:
        import json
        path = os.path.join(game_dir, "game.json")
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        return {}

    # ── scene stack ──────────────────────────────────────────────────
    def push(self, scene: Scene) -> None:
        self.scenes.append(scene)

    def pop(self) -> None:
        self.scenes.pop()
        if self.scenes:
            self.scenes[-1].on_resume()
        else:
            self.running = False

    @property
    def top(self) -> Scene:
        return self.scenes[-1]

    # ── one frame (also the unit tests drive this directly) ─────────
    def tick(self) -> None:
        if not self.scenes:
            self.running = False
            return
        self.top.handle(self.input)
        if self.scenes:
            self.top.update()
        self.input.clear_frame()

    def _open_window(self, fullscreen: bool) -> None:
        """(Re)create the output window. Default (pixel-perfect) opens at
        the largest integer multiple of the 256x192 canvas that fits the
        desktop, so every pixel is uniform and crisp. Fill mode opens a
        1080p window (clamped to the desktop). Fullscreen uses the native
        resolution. Presentation adapts to the live window size (_fit)."""
        self.fullscreen = fullscreen
        if fullscreen:
            self.window = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
            return
        info = pygame.display.Info()
        dw, dh = info.current_w or WINDOW_W, info.current_h or WINDOW_H
        if self.fill:
            size = (min(WINDOW_W, dw), min(WINDOW_H, dh))
        else:
            scale = max(1, min(dw // LOGICAL_W, (dh - 80) // LOGICAL_H))
            size = (LOGICAL_W * scale, LOGICAL_H * scale)
        self.window = pygame.display.set_mode(size, pygame.RESIZABLE)

    @staticmethod
    def _fit(win_w: int, win_h: int) -> tuple:
        """Largest *integer* aspect-correct (4:3) placement of the logical
        canvas in the window: (dst_w, dst_h, offset_x, offset_y). Integer
        scaling keeps pixels uniform and crisp; the remainder letterboxes."""
        scale = max(1, min(win_w // LOGICAL_W, win_h // LOGICAL_H))
        dst_w, dst_h = LOGICAL_W * scale, LOGICAL_H * scale
        return dst_w, dst_h, (win_w - dst_w) // 2, (win_h - dst_h) // 2

    def _present(self, win_w, win_h):
        """Scale the canvas to the window. Pixel-perfect by default
        (integer nearest); fill mode uses sharp-bilinear (integer
        pre-scale then a gentle high-quality fit) to fill the screen
        cleanly without the uneven pixels of raw non-integer nearest."""
        if not self.fill:
            dw, dh, ox, oy = self._fit(win_w, win_h)
            return pygame.transform.scale(self.canvas, (dw, dh)), ox, oy
        scale = min(win_w / LOGICAL_W, win_h / LOGICAL_H)
        dw, dh = round(LOGICAL_W * scale), round(LOGICAL_H * scale)
        factor = max(1, math.ceil(scale))
        pre = pygame.transform.scale(
            self.canvas, (LOGICAL_W * factor, LOGICAL_H * factor))
        return (pygame.transform.smoothscale(pre, (dw, dh)),
                (win_w - dw) // 2, (win_h - dh) // 2)

    def draw(self) -> None:
        self.canvas.fill((16, 16, 24))
        start = len(self.scenes) - 1
        while start > 0 and self.scenes[start].translucent:
            start -= 1
        for sc in self.scenes[start:]:
            sc.draw(self.canvas)
        win_w, win_h = self.window.get_size()
        scaled, ox, oy = self._present(win_w, win_h)
        self.window.fill((0, 0, 0))                  # letterbox bars
        self.window.blit(scaled, (ox, oy))
        pygame.display.flip()

    # ── interactive loop ─────────────────────────────────────────────
    def run(self) -> None:
        from .cheat import CheatConsoleScene
        clock = pygame.time.Clock()
        while self.running:
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    self.running = False
                elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_F11:
                    self._open_window(not self.fullscreen)
                elif (ev.type == pygame.KEYDOWN
                      and ev.key == pygame.K_BACKQUOTE
                      and self.cheat):
                    # Toggle cheat console with ~ (backquote)
                    if self.scenes and isinstance(self.scenes[-1], CheatConsoleScene):
                        self.pop()
                    else:
                        self.push(CheatConsoleScene(self))
                elif ev.type == pygame.KEYDOWN:
                    self.input.key_downs.append((ev.key, ev.unicode))
                    self.input.press_raw(ev.key)        # for the rebind menu
                    if ev.key in self.keymap:
                        self.input.press(self.keymap[ev.key])
                elif ev.type == pygame.KEYUP and ev.key in self.keymap:
                    self.input.release(self.keymap[ev.key])
                elif ev.type == pygame.VIDEORESIZE and not self.fullscreen:
                    self.window = pygame.display.set_mode(
                        (ev.w, ev.h), pygame.RESIZABLE)
            self.tick()
            self.draw()
            clock.tick(FPS)
        pygame.quit()
