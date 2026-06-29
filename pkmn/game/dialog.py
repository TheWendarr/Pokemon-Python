"""Text box UI: the dialog overlay scene plus drawing helpers shared
with the battle scene."""
from __future__ import annotations

import pygame

from .config import A, B, LOGICAL_H, LOGICAL_W, SCALE as S
from .scene import Scene

BOX_BG = (248, 248, 240)
BOX_BORDER = (60, 70, 90)
TEXT = (40, 44, 52)

# UI theme colours
GREEN      = (88,  200,  96)
YELLOW     = (232, 200,  64)
RED        = (216,  72,  64)
PANEL_DARK = (22,  27,  40)   # main dark panel background
PANEL_MID  = (34,  42,  60)   # slightly lighter panel
PANEL_SEL  = (48,  70, 110)   # selected-row highlight

# Gen-5 type palette: (background, text)
TYPE_PALETTE: dict[str, tuple] = {
    "normal":   ((168, 168, 120), (255, 255, 255)),
    "fire":     ((240, 128,  48), (255, 255, 255)),
    "water":    (( 96, 144, 240), (255, 255, 255)),
    "electric": ((248, 208,  48), ( 40,  40,  40)),
    "grass":    ((120, 200,  80), (255, 255, 255)),
    "ice":      ((152, 216, 216), ( 40,  40,  40)),
    "fighting": ((192,  48,  40), (255, 255, 255)),
    "poison":   ((160,  64, 160), (255, 255, 255)),
    "ground":   ((224, 192, 104), ( 40,  40,  40)),
    "flying":   ((168, 144, 240), (255, 255, 255)),
    "psychic":  ((248,  88, 136), (255, 255, 255)),
    "bug":      ((168, 184,  32), (255, 255, 255)),
    "rock":     ((184, 160,  56), (255, 255, 255)),
    "ghost":    ((112,  88, 152), (255, 255, 255)),
    "dragon":   ((112,  56, 248), (255, 255, 255)),
    "dark":     ((112,  88,  72), (255, 255, 255)),
    "steel":    ((184, 184, 208), ( 40,  40,  40)),
    "fairy":    ((238, 153, 172), ( 40,  40,  40)),
    "typeless": ((104, 104, 104), (255, 255, 255)),
}

STATUS_COLORS = {
    "poison":     (160,  64, 160),
    "bad-poison": (112,   0, 128),
    "burn":       (240,  80,  48),
    "paralysis":  (200, 168,   0),
    "sleep":      (120, 120, 130),
    "freeze":     ( 80, 200, 220),
}
STATUS_LABELS = {
    "poison": "PSN", "bad-poison": "TOX", "burn": "BRN",
    "paralysis": "PAR", "sleep": "SLP", "freeze": "FRZ",
}


def draw_box(surf, rect) -> None:
    pygame.draw.rect(surf, BOX_BG, rect, border_radius=4 * S)
    pygame.draw.rect(surf, BOX_BORDER, rect, width=2 * S, border_radius=4 * S)


def draw_panel(surf, rect, bg, border=None, *, radius=None) -> None:
    """Filled dark panel; border defaults to BOX_BORDER when provided."""
    r = radius if radius is not None else 4 * S
    pygame.draw.rect(surf, bg, rect, border_radius=r)
    if border is not None:
        pygame.draw.rect(surf, border, rect, width=2 * S, border_radius=r)


def draw_type_badge(surf, font, type_id: str, x: int, y: int) -> pygame.Rect:
    """Coloured type pill; returns its bounding rect."""
    key = (type_id or "").lower()
    bg, fg = TYPE_PALETTE.get(key, TYPE_PALETTE["typeless"])
    label = (type_id or "???").upper()
    tw, th = font.size(label)
    pw, ph = 6 * S, 2 * S
    r = pygame.Rect(x, y, tw + pw * 2, th + ph * 2)
    pygame.draw.rect(surf, bg, r, border_radius=3 * S)
    surf.blit(font.render(label, True, fg), (x + pw, y + ph))
    return r


def draw_hp_bar(surf, rect: pygame.Rect, frac: float) -> None:
    """HP bar coloured green/yellow/red by fraction."""
    pygame.draw.rect(surf, (50, 56, 76), rect, border_radius=S)
    if frac > 0:
        color = GREEN if frac > 0.5 else YELLOW if frac > 0.2 else RED
        fill = rect.copy()
        fill.width = max(1, int(rect.width * frac))
        pygame.draw.rect(surf, color, fill, border_radius=S)


def draw_stat_bar(surf, rect: pygame.Rect, value: int,
                  max_val: int = 255, color=(72, 136, 220)) -> None:
    """Stat fill bar (blue by default)."""
    pygame.draw.rect(surf, (50, 56, 76), rect, border_radius=S)
    frac = max(0.0, min(1.0, value / max(1, max_val)))
    if frac > 0:
        fill = rect.copy()
        fill.width = max(1, int(rect.width * frac))
        pygame.draw.rect(surf, color, fill, border_radius=S)


def draw_status_badge(surf, font, status: str, x: int, y: int) -> None:
    """Coloured status condition tag (PSN / BRN / etc.)."""
    color = STATUS_COLORS.get(status)
    label = STATUS_LABELS.get(status)
    if not (color and label):
        return
    tw, th = font.size(label)
    pw, ph = 4 * S, 2 * S
    r = pygame.Rect(x, y, tw + pw * 2, th + ph * 2)
    pygame.draw.rect(surf, color, r, border_radius=2 * S)
    surf.blit(font.render(label, True, (255, 255, 255)), (x + pw, y + ph))


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
            self.game.audio.play_sfx("menu_move")   # advance through text
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
