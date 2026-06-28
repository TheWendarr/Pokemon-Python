"""Title screen: logo / "Press Start" / New Game or Continue menu."""
from __future__ import annotations

import os

import pygame

from .config import A, B, DOWN, LOGICAL_H, LOGICAL_W, SCALE as S, START, UP
from .dialog import BOX_BORDER, BOX_BG, TEXT, draw_box
from .scene import Scene
from .state import GameState


class TitleScene(Scene):
    def __init__(self, game):
        super().__init__(game)
        ti = game.manifest.get("title") or {}
        self._title_text = ti.get("text") or game.manifest.get("name", "pkmn")
        music = ti.get("music", "title")
        game.audio.play_music(music)
        self._art = self._load_art(game, ti.get("art"))
        self._phase = "start"   # "start" | "menu"
        self._cursor = 0
        self._blink = 0
        self._has_save = bool(game.save_path and os.path.exists(game.save_path))
        self._options = ["NEW GAME", "CONTINUE"] if self._has_save else ["NEW GAME"]

    @staticmethod
    def _load_art(game, filename) -> "pygame.Surface | None":
        if not filename:
            return None
        path = os.path.join(game.game_dir, filename)
        if not os.path.exists(path):
            return None
        try:
            img = pygame.image.load(path).convert_alpha()
            max_w, max_h = LOGICAL_W * 2 // 3, LOGICAL_H // 3
            scale = min(max_w / img.get_width(), max_h / img.get_height(), 1.0)
            if scale < 1.0:
                img = pygame.transform.scale(
                    img,
                    (int(img.get_width() * scale), int(img.get_height() * scale)))
            return img
        except Exception:
            return None

    def handle(self, inp) -> None:
        if self._phase == "start":
            if START in inp.pressed or A in inp.pressed:
                self.game.audio.play_sfx("confirm")
                self._phase = "menu"
            return
        # menu phase
        if UP in inp.pressed:
            self._cursor = max(0, self._cursor - 1)
            self.game.audio.play_sfx("menu_move")
        if DOWN in inp.pressed:
            self._cursor = min(len(self._options) - 1, self._cursor + 1)
            self.game.audio.play_sfx("menu_move")
        if B in inp.pressed:
            self._phase = "start"
            self.game.audio.play_sfx("cancel")
            return
        if A in inp.pressed or START in inp.pressed:
            self._select()

    def _select(self) -> None:
        choice = self._options[self._cursor]
        self.game.audio.play_sfx("confirm")
        if choice == "CONTINUE":
            self._launch()
        else:  # NEW GAME
            self.game.state = GameState.new_game(
                self.game.data,
                manifest=self.game.manifest,
                seed=self.game._seed)
            self._launch()

    def _launch(self) -> None:
        from .overworld import OverworldScene
        ow = OverworldScene(self.game)
        # Replace TitleScene in-place so the stack is never empty
        # (an empty stack during pop() sets running=False and exits the loop).
        idx = self.game.scenes.index(self)
        self.game.scenes[idx] = ow

    def update(self) -> None:
        self._blink = (self._blink + 1) % 60

    def draw(self, surf) -> None:
        surf.fill((8, 12, 24))
        font = self.game.assets.font
        big = self.game.assets.font_big

        # title text
        title_surf = big.render(self._title_text, True, (240, 240, 220))
        tw = title_surf.get_width()
        ty = LOGICAL_H // 4
        surf.blit(title_surf, (LOGICAL_W // 2 - tw // 2, ty))

        # optional art
        art_y = ty + title_surf.get_height() + 16 * S
        if self._art:
            ax = LOGICAL_W // 2 - self._art.get_width() // 2
            surf.blit(self._art, (ax, art_y))
            art_y += self._art.get_height() + 8 * S

        if self._phase == "start":
            if self._blink < 40:
                ps = font.render("Press START", True, (220, 220, 200))
                surf.blit(ps, (LOGICAL_W // 2 - ps.get_width() // 2,
                               LOGICAL_H * 5 // 8))
        else:
            # draw menu box
            box_w, box_h = 120 * S, (len(self._options) * 16 + 12) * S
            bx = LOGICAL_W // 2 - box_w // 2
            by = LOGICAL_H * 5 // 8
            rect = pygame.Rect(bx, by, box_w, box_h)
            draw_box(surf, rect)
            for i, label in enumerate(self._options):
                iy = by + 6 * S + i * 16 * S
                if i == self._cursor:
                    surf.blit(font.render(">", True, TEXT),
                              (bx + 6 * S, iy))
                surf.blit(font.render(label, True, TEXT),
                          (bx + 16 * S, iy))
