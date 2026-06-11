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
from .config import (A, B, DATA_DIR, DOWN, FPS, LEFT, LOGICAL_H, LOGICAL_W,
                     RIGHT, SCALE, UP)
from .state import GameState

KEYMAP = {
    pygame.K_UP: UP, pygame.K_w: UP,
    pygame.K_DOWN: DOWN, pygame.K_s: DOWN,
    pygame.K_LEFT: LEFT, pygame.K_a: LEFT,
    pygame.K_RIGHT: RIGHT, pygame.K_d: RIGHT,
    pygame.K_z: A, pygame.K_RETURN: A, pygame.K_SPACE: A,
    pygame.K_x: B, pygame.K_BACKSPACE: B, pygame.K_ESCAPE: B,
}


class Input:
    """`pressed` is edge-triggered (this frame), `held` is level."""

    def __init__(self):
        self.pressed: set = set()
        self.held: set = set()

    def press(self, name: str) -> None:
        self.pressed.add(name)
        self.held.add(name)

    def release(self, name: str) -> None:
        self.held.discard(name)

    def clear_frame(self) -> None:
        self.pressed.clear()


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
                 data_dir: str = DATA_DIR):
        if headless:
            os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
            os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
        pygame.init()
        flags = 0 if headless else pygame.SCALED
        size = ((LOGICAL_W, LOGICAL_H) if headless
                else (LOGICAL_W * SCALE, LOGICAL_H * SCALE))
        self.window = pygame.display.set_mode(size, flags)
        pygame.display.set_caption("pkmn")
        self.canvas = pygame.Surface((LOGICAL_W, LOGICAL_H))
        self.data = GameData(data_dir)
        self.assets = Assets()
        self.state = GameState.new_game(self.data, seed=seed)
        self.scenes: list[Scene] = []
        self.input = Input()
        self.running = True

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

    def draw(self) -> None:
        self.canvas.fill((16, 16, 24))
        start = len(self.scenes) - 1
        while start > 0 and self.scenes[start].translucent:
            start -= 1
        for sc in self.scenes[start:]:
            sc.draw(self.canvas)
        self.window.blit(pygame.transform.scale(
            self.canvas, self.window.get_size()), (0, 0))
        pygame.display.flip()

    # ── interactive loop ─────────────────────────────────────────────
    def run(self) -> None:
        clock = pygame.time.Clock()
        while self.running:
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    self.running = False
                elif ev.type == pygame.KEYDOWN and ev.key in KEYMAP:
                    self.input.press(KEYMAP[ev.key])
                elif ev.type == pygame.KEYUP and ev.key in KEYMAP:
                    self.input.release(KEYMAP[ev.key])
            self.tick()
            self.draw()
            clock.tick(FPS)
        pygame.quit()
