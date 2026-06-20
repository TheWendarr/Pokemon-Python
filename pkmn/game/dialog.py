"""Text box UI: the dialog overlay scene plus drawing helpers shared
with the battle scene."""
from __future__ import annotations

import pygame

from .config import A, B, LOGICAL_H, LOGICAL_W, SCALE as S
from .scene import Scene

BOX_BG = (248, 248, 240)
BOX_BORDER = (60, 70, 90)
TEXT = (40, 44, 52)


def draw_box(surf, rect) -> None:
    pygame.draw.rect(surf, BOX_BG, rect, border_radius=4 * S)
    pygame.draw.rect(surf, BOX_BORDER, rect, width=2 * S, border_radius=4 * S)


def wrap_text(font, text, width) -> list:
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if font.size(trial)[0] <= width:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines or [""]


class DialogScene(Scene):
    """Modal message box. A advances; closes after the last page."""
    translucent = True

    def __init__(self, game, lines, on_close=None):
        super().__init__(game)
        self.pages: list = []
        font = game.assets.font
        for line in lines:
            self.pages.extend(wrap_chunks(font, line, LOGICAL_W - 28 * S))
        self.idx = 0
        self.on_close = on_close

    def handle(self, inp) -> None:
        if A in inp.pressed or B in inp.pressed:
            self.idx += 1
            if self.idx >= len(self.pages):
                self.game.pop()
                if self.on_close:
                    self.on_close()

    def draw(self, surf) -> None:
        rect = pygame.Rect(4 * S, LOGICAL_H - 52 * S, LOGICAL_W - 8 * S, 48 * S)
        draw_box(surf, rect)
        font = self.game.assets.font
        for i, line in enumerate(self.pages[self.idx]):
            surf.blit(font.render(line, True, TEXT),
                      (rect.x + 8 * S, rect.y + 7 * S + i * 14 * S))
        surf.blit(font.render("v", True, BOX_BORDER),
                  (rect.right - 14 * S, rect.bottom - 14 * S))


def wrap_chunks(font, text, width, per_page: int = 2) -> list:
    lines = wrap_text(font, text, width)
    return [lines[i:i + per_page] for i in range(0, len(lines), per_page)]
