"""Evolution cutscene pushed on top of the scene stack after a battle win.

Phases:
  text1    — "What? {name} is evolving!"  (auto-advances or press A)
  flash    — sprite alternates colour / white silhouette (~3 s); B to cancel
  whiteout — screen floods to white  (~0.5 s)
  emerge   — evolved sprite materialises from white  (~0.67 s)
  text2    — "Congratulations! … evolved into …!"  (press A to dismiss)
  done     — pops self off the scene stack
"""
from __future__ import annotations

import pygame

from ..core.pokemon import evolve
from .config import A, B, LOGICAL_H, LOGICAL_W, SCALE as S, SPRITE_PX
from .dialog import BOX_BORDER, TEXT, draw_box, wrap_chunks
from .scene import Scene

_TEXT1_HOLD  = 160   # frames before auto-advancing from "What? …" text
_FLASH_DUR   = 180   # frames of colour/white flicker  (≈ 3 s at 60 fps)
_FLASH_RATE  = 6     # frames per colour↔white toggle
_WHITE_DUR   = 30    # frames for the screen-to-white flood
_EMERGE_DUR  = 40    # frames for the new sprite to materialise from white

_BG = (8, 12, 24)   # same dark-navy used by the battle backdrop


def _white_surface(surf: pygame.Surface) -> pygame.Surface:
    """Return a white-filled copy, preserving per-pixel alpha."""
    white = surf.copy()
    white.fill((255, 255, 255), special_flags=pygame.BLEND_RGB_MAX)
    return white


class EvolutionScene(Scene):
    def __init__(self, game, state, target_species: str):
        super().__init__(game)
        self._state  = state
        self._target = target_species
        self._old_name = state.nickname or state.species_id.replace("-", " ").title()

        # Pre-load both sprites now so there's no hitch mid-animation.
        old_sp  = game.data.species(state.species_id)
        new_sp  = game.data.species(target_species)
        old_dex = getattr(old_sp, "dex", None)
        new_dex = getattr(new_sp, "dex", None)
        self._new_dex = new_dex or 0
        self._old_sprite = game.assets.battler(
            state.species_id, self._old_name, dex=old_dex, back=True)
        self._new_sprite = game.assets.battler(
            target_species,
            target_species.replace("-", " ").title(),
            dex=new_dex, back=True)
        self._white_old = _white_surface(self._old_sprite)

        self._phase     = "text1"
        self._timer     = 0
        self._cancelled = False
        self._evolved   = False
        self._new_name  = ""

        game.audio.play_music("evolution", loop=False)

    # ── input ────────────────────────────────────────────────────────

    def handle(self, inp) -> None:
        if self._phase == "text1" and A in inp.pressed:
            self._go("flash")
        elif self._phase == "flash" and B in inp.pressed:
            self._cancelled = True
            self._go("text2")
        elif self._phase == "text2" and A in inp.pressed:
            self._go("done")

    # ── update ───────────────────────────────────────────────────────

    def update(self) -> None:
        self._timer += 1
        if self._phase == "text1":
            if self._timer >= _TEXT1_HOLD:
                self._go("flash")
        elif self._phase == "flash":
            if self._timer >= _FLASH_DUR:
                self._go("whiteout")
        elif self._phase == "whiteout":
            if self._timer >= _WHITE_DUR:
                self._commit_evolve()
                self._go("emerge")
        elif self._phase == "emerge":
            if self._timer >= _EMERGE_DUR:
                self._go("text2")
        elif self._phase == "done":
            self.game.pop()

    def _commit_evolve(self) -> None:
        if self._evolved or self._cancelled:
            return
        evolve(self._state, self.game.data, self._target)
        self._evolved  = True
        self._new_name = (self._state.nickname
                          or self._state.species_id.replace("-", " ").title())
        self.game.audio.play_cry(self._new_dex)
        self.game.audio.play_sfx("evo_done")

    def _go(self, phase: str) -> None:
        self._phase = phase
        self._timer = 0

    # ── draw ─────────────────────────────────────────────────────────

    def draw(self, surf) -> None:
        cx = LOGICAL_W // 2
        sy = LOGICAL_H // 2 - SPRITE_PX // 2 - 12 * S

        if self._phase == "text1":
            surf.fill(_BG)
            surf.blit(self._old_sprite, (cx - SPRITE_PX // 2, sy))
            self._draw_dialog(surf, f"What? {self._old_name} is evolving!")

        elif self._phase == "flash":
            surf.fill(_BG)
            show_white = (self._timer // _FLASH_RATE) % 2 == 1
            sp = self._white_old if show_white else self._old_sprite
            surf.blit(sp, (cx - SPRITE_PX // 2, sy))
            hint = self.game.assets.font.render("(B) Cancel", True, (140, 140, 140))
            surf.blit(hint, (LOGICAL_W - hint.get_width() - 8 * S, 8 * S))

        elif self._phase == "whiteout":
            k = min(1.0, self._timer / _WHITE_DUR)
            bg = tuple(int(c + (255 - c) * k) for c in _BG)
            surf.fill(bg)
            alpha = int(255 * max(0.0, 1.0 - k * 2.5))
            if alpha > 0:
                sp = self._white_old.copy()
                sp.set_alpha(alpha)
                surf.blit(sp, (cx - SPRITE_PX // 2, sy))

        elif self._phase == "emerge":
            k = min(1.0, self._timer / _EMERGE_DUR)
            surf.fill((255, 255, 255))
            sp = self._new_sprite.copy()
            sp.set_alpha(int(255 * k))
            surf.blit(sp, (cx - SPRITE_PX // 2, sy))

        elif self._phase == "text2":
            surf.fill(_BG)
            if self._cancelled:
                self._draw_dialog(surf, f"{self._old_name} did not evolve.")
            else:
                surf.blit(self._new_sprite, (cx - SPRITE_PX // 2, sy))
                self._draw_dialog(
                    surf,
                    f"Congratulations! {self._old_name} evolved "
                    f"into {self._new_name}!")

    def _draw_dialog(self, surf, text: str) -> None:
        font = self.game.assets.font
        rect = pygame.Rect(4 * S, LOGICAL_H - 52 * S, LOGICAL_W - 8 * S, 48 * S)
        draw_box(surf, rect)
        pages = wrap_chunks(font, text, rect.width - 16 * S)
        lines = pages[0] if pages else [text]
        for i, ln in enumerate(lines[:3]):
            surf.blit(font.render(ln, True, TEXT),
                      (rect.x + 8 * S, rect.y + 7 * S + i * 14 * S))
        surf.blit(font.render("v", True, BOX_BORDER),
                  (rect.right - 14 * S, rect.bottom - 14 * S))
