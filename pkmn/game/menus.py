"""Pause menu, party list, summary screen, overworld bag, and PC box."""
from __future__ import annotations

import pygame

from ..core.pokemon import PokemonState
from .config import A, B, DOWN, LEFT, LOGICAL_H, LOGICAL_W, RIGHT, SCALE as S, UP
from .dialog import (BOX_BORDER, PANEL_DARK, PANEL_MID, PANEL_SEL, TEXT,
                      TYPE_PALETTE, draw_box, draw_hp_bar, draw_panel,
                      draw_stat_bar, draw_status_badge, draw_type_badge,
                      wrap_text)
from . import keybinds
from .save import save_game
from .scene import Scene


# ── shared constants ─────────────────────────────────────────────────────

_PAUSE_ACCENTS = {
    "POKEMON":  ( 88, 200,  96),
    "BAG":      (248, 208,  48),
    "SAVE":     ( 72, 136, 220),
    "POKEDEX":  (216,  72,  64),
    "BADGES":   (224, 160,  64),
    "CONTROLS": (136, 136, 160),
    "FLY":      (168, 144, 240),
    "CLOSE":    ( 80,  88, 100),
}

_NATURE_MODS: dict[str, tuple] = {
    "hardy":   (None, None),     "lonely":   ("attack",          "defense"),
    "brave":   ("attack",        "speed"),    "adamant":  ("attack",          "special_attack"),
    "naughty": ("attack",        "special_defense"),
    "bold":    ("defense",       "attack"),   "docile":   (None, None),
    "relaxed": ("defense",       "speed"),    "impish":   ("defense",         "special_attack"),
    "lax":     ("defense",       "special_defense"),
    "timid":   ("speed",         "attack"),   "hasty":    ("speed",           "defense"),
    "serious": (None, None),                 "jolly":    ("speed",           "special_attack"),
    "naive":   ("speed",         "special_defense"),
    "modest":  ("special_attack","attack"),   "mild":     ("special_attack",  "defense"),
    "quiet":   ("special_attack","speed"),    "bashful":  (None, None),
    "rash":    ("special_attack","special_defense"),
    "calm":    ("special_defense","attack"),  "gentle":   ("special_defense", "defense"),
    "sassy":   ("special_defense","speed"),   "careful":  ("special_defense", "special_attack"),
    "quirky":  (None, None),
}

# Bag pocket tabs: (label, filter_fn(ItemData, item_id) → bool)
_POCKETS = [
    ("ALL",   lambda it, _: True),
    ("MED",   lambda it, _: it is not None and bool(it.heal or it.cures or it.revive)),
    ("BALLS", lambda it, _: it is not None and bool(it.is_ball)),
    ("TMs",   lambda it, _: it is not None and it.pocket == "machines"),
    ("HELD",  lambda it, _: (it is not None and bool(it.holdable)
                              and not bool(it.is_ball)
                              and it.pocket != "machines"
                              and not bool(it.heal or it.cures or it.revive))),
]


def nav_list(scene, inp, n) -> None:
    before = scene.cursor
    if DOWN in inp.pressed:
        scene.cursor = min(max(0, n - 1), scene.cursor + 1)
    if UP in inp.pressed:
        scene.cursor = max(0, scene.cursor - 1)
    if scene.cursor != before:
        scene.game.audio.play_sfx("menu_move")


class PauseScene(Scene):
    translucent = True

    def __init__(self, game):
        super().__init__(game)
        self.cursor = 0
        self.note = ""
        self.OPTIONS = tuple(
            o for o, feat, default in (
                ("POKEMON", "menu_party", True), ("BAG", "menu_bag", True),
                ("SAVE", "saving", True), ("POKEDEX", "pokedex", True),
                ("BADGES", "badges", False), ("CONTROLS", "controls", True))
            if game.feature(feat, default)) + (
            ("FLY",) if (game.feature("fly", False) and game.state.can_fly) else ()
        ) + ("CLOSE",)

    def handle(self, inp) -> None:
        nav_list(self, inp, len(self.OPTIONS))
        if B in inp.pressed:
            self.game.pop()
            return
        if A in inp.pressed:
            pick = self.OPTIONS[self.cursor]
            if pick == "POKEDEX":
                self.game.push(PokedexScene(self.game))
            elif pick == "BADGES":
                self.game.push(BadgesScene(self.game))
            elif pick == "FLY":
                self.game.push(FlyScene(self.game))
            elif pick == "CONTROLS":
                self.game.push(ControlsScene(self.game))
            elif pick == "POKEMON":
                self.game.push(PartyScene(self.game))
            elif pick == "BAG":
                self.game.push(BagScene(self.game))
            elif pick == "SAVE":
                save_game(self.game.state,
                          self.game.save_path or "save.json")
                self.game.audio.play_sfx("save")
                self.note = "Game saved!"
            else:
                self.game.pop()

    def draw(self, surf) -> None:
        font = self.game.assets.font
        ROW = 20 * S
        W = 100 * S
        H = ROW * len(self.OPTIONS) + 10 * S
        rect = pygame.Rect(LOGICAL_W - W - 6 * S, 8 * S, W, H)
        draw_panel(surf, rect, PANEL_DARK, BOX_BORDER, radius=6 * S)
        for i, label in enumerate(self.OPTIONS):
            y = rect.y + 5 * S + i * ROW
            accent = _PAUSE_ACCENTS.get(label, (80, 88, 100))
            if i == self.cursor:
                hl = pygame.Surface((rect.width - 4 * S, ROW), pygame.SRCALPHA)
                hl.fill((*accent[:3], 55))
                surf.blit(hl, (rect.x + 2 * S, y))
            ab = pygame.Rect(rect.x + 4 * S, y + 3 * S, 4 * S, ROW - 6 * S)
            pygame.draw.rect(surf, accent, ab, border_radius=S)
            col = (255, 255, 255) if i == self.cursor else (230, 242, 255)
            surf.blit(font.render(label, True, col),
                      (rect.x + 12 * S, y + (ROW - font.get_height()) // 2))
        if self.note:
            nrect = pygame.Rect(4 * S, LOGICAL_H - 26 * S, 140 * S, 22 * S)
            draw_panel(surf, nrect, PANEL_DARK, BOX_BORDER, radius=4 * S)
            surf.blit(font.render(self.note, True, (235, 248, 255)),
                      (nrect.x + 6 * S, nrect.y + (22 * S - font.get_height()) // 2))


class PartyScene(Scene):
    """Party list. A on a slot opens a small menu — SUMMARY, MOVE, CANCEL.
    Choosing MOVE picks the mon up; pick another slot to swap them into
    place. B backs out (cancelling a move-in-progress first)."""
    translucent = True
    ACTIONS = ("SUMMARY", "MOVE", "ITEM", "CANCEL")

    def __init__(self, game):
        super().__init__(game)
        self.cursor = 0
        self.held: int | None = None      # slot being moved
        self.menu: int | None = None      # action-menu cursor (None = closed)
        self.note = ""

    def handle(self, inp) -> None:
        party = self.game.state.party
        if self.menu is not None:                     # action menu is open
            before = self.menu
            if UP in inp.pressed:
                self.menu = max(0, self.menu - 1)
            if DOWN in inp.pressed:
                self.menu = min(len(self.ACTIONS) - 1, self.menu + 1)
            if self.menu != before:
                self.game.audio.play_sfx("menu_move")
            if B in inp.pressed:
                self.menu = None
            elif A in inp.pressed:
                act = self.ACTIONS[self.menu]
                self.menu = None
                if act == "SUMMARY":
                    self.game.push(SummaryScene(self.game, party[self.cursor]))
                elif act == "MOVE":
                    self.held = self.cursor
                elif act == "ITEM":
                    self._toggle_item(party[self.cursor])
            return
        nav_list(self, inp, len(party))
        if B in inp.pressed:
            if self.held is not None:
                self.held = None                      # cancel the move
            else:
                self.game.pop()
        elif A in inp.pressed:
            if self.held is not None:                 # drop -> swap into place
                if self.held != self.cursor:
                    party[self.held], party[self.cursor] = \
                        party[self.cursor], party[self.held]
                self.held = None
            else:
                self.menu = 0                         # open the action menu

    def _toggle_item(self, mon) -> None:
        st = self.game.state
        if mon.held_item:                              # take it back
            it = self.game.data.item(mon.held_item)
            st.bag[mon.held_item] = st.bag.get(mon.held_item, 0) + 1
            self.note = f"Took the {it.name if it else mon.held_item}."
            mon.held_item = None
            self.game.audio.play_sfx("confirm")
        else:
            self.game.push(HeldItemPicker(self.game, mon))

    def draw(self, surf) -> None:
        party = self.game.state.party
        font = self.game.assets.font
        FH = font.get_height()

        CARD_H = 26 * S
        GAP    =  3 * S
        MARGIN =  8 * S
        total_cards = len(party)
        outer_h = total_cards * (CARD_H + GAP) - GAP + MARGIN * 2
        outer = pygame.Rect(MARGIN, MARGIN, LOGICAL_W - MARGIN * 2, outer_h)
        draw_panel(surf, outer, PANEL_DARK, BOX_BORDER, radius=6 * S)

        for i, p in enumerate(party):
            cy = outer.y + MARGIN // 2 + i * (CARD_H + GAP)
            card = pygame.Rect(outer.x + 4 * S, cy, outer.width - 8 * S, CARD_H)
            is_sel  = (i == self.cursor)
            is_held = (i == self.held)

            # Card background
            card_bg = (52, 68, 108) if is_sel else (44, 56, 90) if is_held else PANEL_MID
            pygame.draw.rect(surf, card_bg, card, border_radius=4 * S)
            if is_sel:
                pygame.draw.rect(surf, (100, 160, 240), card,
                                 width=2 * S, border_radius=4 * S)
            elif is_held:
                pygame.draw.rect(surf, (216, 152, 60), card,
                                 width=2 * S, border_radius=4 * S)

            # Left type-colour accent bar
            sp = self.game.data.species(p.species_id)
            ptype = sp.types[0] if sp and sp.types else "normal"
            acc_col = TYPE_PALETTE.get(ptype, TYPE_PALETTE["normal"])[0]
            acc = pygame.Rect(card.x, card.y, 6 * S, card.height)
            pygame.draw.rect(surf, acc_col, acc,
                             border_top_left_radius=4 * S,
                             border_bottom_left_radius=4 * S)

            tx = card.x + 10 * S
            ty = card.y + (CARD_H - FH) // 2 - 5 * S

            # Name + level
            name = p.nickname or p.species_id.title()
            surf.blit(font.render(name, True, (255, 255, 255)), (tx, ty))
            lv_txt = f"Lv{p.level}"
            surf.blit(font.render(lv_txt, True, (220, 236, 255)),
                      (tx + 76 * S, ty))

            # Status badge (right side)
            if p.status:
                draw_status_badge(surf, font, p.status,
                                  card.right - 40 * S, ty)

            # HP bar
            bar_y = ty + FH + 2 * S
            if p.current_hp > 0:
                frac = max(0.0, min(1.0, p.current_hp / max(1, p.max_hp)))
                bar_rect = pygame.Rect(tx, bar_y, 130 * S, 5 * S)
                draw_hp_bar(surf, bar_rect, frac)
                hp_txt = f"{max(0, p.current_hp)}/{p.max_hp}"
                surf.blit(font.render(hp_txt, True, (225, 242, 255)),
                          (tx + 134 * S, bar_y - (FH - 5 * S) // 2))
            else:
                surf.blit(font.render("FAINTED", True, (216, 72, 64)), (tx, bar_y))

            # Held item (right of HP area, dimmed)
            if p.held_item:
                hit = self.game.data.item(p.held_item)
                iname = hit.name if hit else p.held_item.replace("-", " ").title()
                surf.blit(font.render(f" @ {iname}", True, (200, 222, 245)),
                          (tx + 170 * S, bar_y - (FH - 5 * S) // 2))

        # Hint bar below cards
        hint = (self.note or
                ("Pick a slot to swap into." if self.held is not None
                 else "A: options   B: back"))
        hy = outer.bottom + 4 * S
        draw_panel(surf, pygame.Rect(MARGIN, hy, LOGICAL_W - MARGIN * 2, 20 * S),
                   PANEL_DARK, radius=4 * S)
        surf.blit(font.render(hint, True, (210, 230, 255)),
                  (MARGIN + 6 * S, hy + (20 * S - FH) // 2))

        # Action-menu popup
        if self.menu is not None:
            mw = 80 * S
            mh = 16 * S * len(self.ACTIONS) + 8 * S
            mx = LOGICAL_W // 2 - mw // 2
            my = LOGICAL_H // 3
            mr = pygame.Rect(mx, my, mw, mh)
            draw_panel(surf, mr, PANEL_DARK, BOX_BORDER, radius=4 * S)
            for i, act in enumerate(self.ACTIONS):
                yy = mr.y + 4 * S + i * 16 * S
                if i == self.menu:
                    pygame.draw.rect(surf, PANEL_SEL,
                                     pygame.Rect(mr.x + 2 * S, yy,
                                                 mr.width - 4 * S, 16 * S),
                                     border_radius=3 * S)
                col = (255, 255, 255) if i == self.menu else (225, 240, 255)
                surf.blit(font.render(act, True, col),
                          (mr.x + 10 * S, yy + (16 * S - FH) // 2))



class SummaryScene(Scene):
    translucent = True
    _PAGES = ("INFO", "STATS", "MOVES")

    def __init__(self, game, mon):
        super().__init__(game)
        self.mon = mon
        self.page = 0

    def handle(self, inp) -> None:
        if LEFT in inp.pressed:
            self.page = (self.page - 1) % len(self._PAGES)
            self.game.audio.play_sfx("menu_move")
        elif RIGHT in inp.pressed:
            self.page = (self.page + 1) % len(self._PAGES)
            self.game.audio.play_sfx("menu_move")
        if A in inp.pressed or B in inp.pressed:
            self.game.pop()

    # ── shared header ──────────────────────────────────────────────────
    def _draw_header(self, surf, font, big, m, sp, rect) -> None:
        draw_panel(surf, rect, PANEL_DARK, BOX_BORDER, radius=6 * S)
        # page tabs
        tab_w = 38 * S
        for ti, tab in enumerate(self._PAGES):
            tx = rect.x + 6 * S + ti * (tab_w + 2 * S)
            ty = rect.y + 3 * S
            bg = (60, 90, 150) if ti == self.page else (30, 38, 58)
            pygame.draw.rect(surf, bg,
                             pygame.Rect(tx, ty, tab_w, 14 * S),
                             border_radius=3 * S)
            surf.blit(font.render(tab, True,
                                  (255, 255, 255) if ti == self.page
                                  else (120, 140, 170)),
                      (tx + (tab_w - font.size(tab)[0]) // 2,
                       ty + (14 * S - font.get_height()) // 2))
        # name + level
        name = m.nickname or sp.name
        surf.blit(big.render(f"{name}  Lv{m.level}", True, (255, 255, 255)),
                  (rect.x + 8 * S, rect.y + 20 * S))
        # type badges
        bx = rect.x + 8 * S
        for t in sp.types:
            r = draw_type_badge(surf, font, t, bx, rect.y + 36 * S)
            bx = r.right + 4 * S
        # shiny / gender / status
        extras = []
        if m.shiny:
            extras.append(("★ SHINY", (255, 220, 64)))
        gmap = {"male": ("♂", (100, 148, 240)), "female": ("♀", (240, 100, 160))}
        if m.gender in gmap:
            extras.append(gmap[m.gender])
        if m.status:
            from .dialog import STATUS_COLORS, STATUS_LABELS
            sl = STATUS_LABELS.get(m.status, "")
            sc = STATUS_COLORS.get(m.status, (128, 128, 128))
            if sl:
                extras.append((sl, sc))
        ex = rect.right - 6 * S
        for lbl, col in reversed(extras):
            w = font.size(lbl)[0] + 6 * S
            ex -= w
            surf.blit(font.render(lbl, True, col), (ex, rect.y + 22 * S))

    # ── page 0 : INFO ──────────────────────────────────────────────────
    def _draw_info(self, surf, font, big, m, sp, body) -> None:
        from ..core.experience import exp_total
        img = self.game.assets.battler(
            m.species_id, m.nickname or sp.name, dex=getattr(sp, "dex", None))
        iw = min(img.get_width(), 56 * S)
        img_s = pygame.transform.scale(img, (iw, iw))
        surf.blit(img_s, (body.right - iw - 8 * S, body.y + 6 * S))
        y = body.y + 8 * S
        x = body.x + 8 * S
        # metadata lines
        ab = m.ability.replace("-", " ").title() if m.ability else "—"
        lines = [
            ("Dex No.",    f"#{getattr(sp, 'dex', 0) or 0:03d}"),
            ("Species",    sp.name),
            ("Nature",     m.nature.title() if m.nature else "—"),
            ("Ability",    ab),
            ("Friendship", str(m.friendship)),
        ]
        if m.held_item:
            hit = self.game.data.item(m.held_item)
            lines.append(("Held Item", hit.name if hit else m.held_item))
        for lbl, val in lines:
            surf.blit(font.render(lbl, True, (210, 228, 252)), (x, y))
            surf.blit(font.render(val, True, (230, 240, 255)),
                      (x + 48 * S, y))
            y += 14 * S
        # EXP
        y += 4 * S
        nxt = exp_total(sp.growth_rate, m.level + 1) if m.level < 100 else m.exp
        surf.blit(font.render(f"EXP  {m.exp}   To next: {max(0, nxt - m.exp)}",
                              True, (210, 228, 252)), (x, y))
        y += 14 * S
        exp_frac = (max(0, m.exp - exp_total(sp.growth_rate, m.level))
                    / max(1, nxt - exp_total(sp.growth_rate, m.level))
                    if m.level < 100 else 1.0)
        from .dialog import draw_stat_bar
        draw_stat_bar(surf, pygame.Rect(x, y, 100 * S, 5 * S),
                      int(exp_frac * 255), color=(72, 136, 220))

    # ── page 1 : STATS ─────────────────────────────────────────────────
    def _draw_stats(self, surf, font, big, m, sp, body) -> None:
        boosted, lowered = _NATURE_MODS.get(
            (m.nature or "").lower(), (None, None))
        STAT_KEYS = ("hp", "attack", "defense", "special_attack",
                     "special_defense", "speed")
        STAT_LABELS = {
            "hp": "HP", "attack": "Atk", "defense": "Def",
            "special_attack": "SpAtk", "special_defense": "SpDef", "speed": "Spd",
        }
        # Max reference values for bar scaling (roughly base stat ceiling)
        MAX_VALS = {
            "hp": 714, "attack": 565, "defense": 545,
            "special_attack": 565, "special_defense": 545, "speed": 540,
        }
        x = body.x + 10 * S
        y = body.y + 6 * S
        bar_x = x + 34 * S
        bar_w = 120 * S
        for key in STAT_KEYS:
            val = m.current_hp if key == "hp" else m.stats.get(key, 0)
            max_hp = m.max_hp
            label = STAT_LABELS[key]
            if key == boosted:
                lcol = (240, 100, 100)
            elif key == lowered:
                lcol = (100, 130, 240)
            else:
                lcol = (160, 185, 220)
            surf.blit(font.render(label, True, lcol), (x, y))
            # value
            if key == "hp":
                vtxt = f"{max(0, m.current_hp)}/{max_hp}"
            else:
                vtxt = str(m.stats.get(key, 0))
            surf.blit(font.render(vtxt, True, (230, 245, 255)),
                      (x + 22 * S, y))
            # bar
            bar_rect = pygame.Rect(bar_x, y + (font.get_height() - 7 * S) // 2,
                                   bar_w, 7 * S)
            raw = m.stats.get(key, 1)
            draw_stat_bar(surf, bar_rect, raw, MAX_VALS.get(key, 400))
            y += 18 * S

    # ── page 2 : MOVES ─────────────────────────────────────────────────
    def _draw_moves(self, surf, font, big, m, sp, body) -> None:
        cols, rows = 2, 2
        cw = body.width // cols
        ch = (body.height - 4 * S) // rows
        for i, slot in enumerate(m.moves[:4]):
            col, row = i % cols, i // cols
            cx = body.x + col * cw + 4 * S
            cy = body.y + row * ch + 4 * S
            cell = pygame.Rect(cx, cy, cw - 8 * S, ch - 8 * S)
            mv = self.game.data.move(slot.move_id)
            mtype = mv.type if mv else "typeless"
            bg = TYPE_PALETTE.get(mtype, TYPE_PALETTE["typeless"])[0]
            # Dimmed bg for the cell
            bg_dim = tuple(max(0, int(c * 0.55 + 15)) for c in bg)
            draw_panel(surf, cell, bg_dim, None, radius=4 * S)
            pygame.draw.rect(surf, tuple(min(255, c + 40) for c in bg_dim),
                             cell, width=2 * S, border_radius=4 * S)
            # type badge top-left
            badge = draw_type_badge(surf, font, mtype,
                                    cell.x + 5 * S, cell.y + 5 * S)
            # move name
            mv_name = mv.name if mv else slot.move_id.replace("-", " ").title()
            surf.blit(font.render(mv_name, True, (255, 255, 255)),
                      (cell.x + 5 * S, badge.bottom + 4 * S))
            # PP
            pp_txt = f"PP {slot.pp}/{slot.pp_max}"
            surf.blit(font.render(pp_txt, True,
                                  (200, 220, 245) if slot.pp > 0
                                  else (216, 72, 64)),
                      (cell.x + 5 * S, cell.bottom - font.get_height() - 4 * S))

    def draw(self, surf) -> None:
        m, font, big = self.mon, self.game.assets.font, self.game.assets.font_big
        sp = m.species
        HDR_H = 52 * S
        rect = pygame.Rect(6 * S, 6 * S, LOGICAL_W - 12 * S, LOGICAL_H - 12 * S)
        header = pygame.Rect(rect.x, rect.y, rect.width, HDR_H)
        body   = pygame.Rect(rect.x, rect.y + HDR_H + 2 * S,
                             rect.width, rect.height - HDR_H - 2 * S)
        self._draw_header(surf, font, big, m, sp, header)
        draw_panel(surf, body, PANEL_MID, BOX_BORDER, radius=6 * S)
        if self.page == 0:
            self._draw_info(surf, font, big, m, sp, body)
        elif self.page == 1:
            self._draw_stats(surf, font, big, m, sp, body)
        else:
            self._draw_moves(surf, font, big, m, sp, body)
        # navigation hint
        hint = "< / > to switch pages   A/B: back"
        hw = font.size(hint)[0] + 12 * S
        hx = rect.x + (rect.width - hw) // 2
        hy = body.bottom - 18 * S
        surf.blit(font.render(hint, True, (205, 225, 252)), (hx, hy))


class PokedexScene(Scene):
    """Pokedex: the region roster in national-dex order with seen/caught
    status, plus running totals. Owned entries show OWN; merely seen show
    the name; unseen show dashes (as the games do)."""
    translucent = True

    def __init__(self, game):
        super().__init__(game)
        self.cursor = 0
        st = game.state
        ids = set(st.regiondex) | st.seen | st.caught
        self.entries = sorted(ids, key=self._dexno)

    def _dexno(self, sid):
        sp = self.game.data.species(sid)
        return getattr(sp, "dex", 0) or 0

    def handle(self, inp) -> None:
        nav_list(self, inp, len(self.entries))
        if A in inp.pressed:
            sid = self.entries[self.cursor] if self.entries else None
            if sid and sid in self.game.state.seen:
                self.game.push(SummaryScene(
                    self.game, PokemonState.generate(
                        self.game.data, sid, 5, rng=self.game.state.rng)))
        elif B in inp.pressed:
            self.game.pop()

    def draw(self, surf) -> None:
        st = self.game.state
        font, big = self.game.assets.font, self.game.assets.font_big
        FH = font.get_height()
        LIST_W = 118 * S
        DETAIL_X = 8 * S + LIST_W + 4 * S
        DETAIL_W = LOGICAL_W - DETAIL_X - 8 * S
        FULL_H = LOGICAL_H - 16 * S

        # ── left panel: list ──────────────────────────────────────────
        lrect = pygame.Rect(8 * S, 8 * S, LIST_W, FULL_H)
        draw_panel(surf, lrect, PANEL_DARK, BOX_BORDER, radius=6 * S)
        # header
        surf.blit(big.render("POKÉDEX", True, (210, 230, 255)),
                  (lrect.x + 6 * S, lrect.y + 5 * S))
        surf.blit(font.render(f"Seen {len(st.seen)}", True, (120, 190, 240)),
                  (lrect.x + 6 * S, lrect.y + 22 * S))
        surf.blit(font.render(f"Own  {len(st.caught)}", True, (120, 230, 140)),
                  (lrect.x + 6 * S, lrect.y + 34 * S))

        HDR = 46 * S
        ROW_H = 14 * S
        avail_rows = max(1, (lrect.height - HDR - 4 * S) // ROW_H)
        top = (0 if len(self.entries) <= avail_rows
               else max(0, min(self.cursor - avail_rows // 2,
                               len(self.entries) - avail_rows)))
        for ri, idx in enumerate(range(top, min(top + avail_rows,
                                                len(self.entries)))):
            sid = self.entries[idx]
            sp = self.game.data.species(sid)
            no = getattr(sp, "dex", 0) or 0
            ry = lrect.y + HDR + ri * ROW_H
            is_sel = (idx == self.cursor)
            if is_sel:
                hl = pygame.Rect(lrect.x + 2 * S, ry,
                                 lrect.width - 4 * S, ROW_H)
                pygame.draw.rect(surf, PANEL_SEL, hl, border_radius=3 * S)
            if sid in st.caught:
                col, txt = (120, 230, 140), f"#{no:03d} {sp.name}"
            elif sid in st.seen:
                col, txt = (238, 248, 255), f"#{no:03d} {sp.name}"
            else:
                col, txt = (188, 205, 228), f"#{no:03d} ----------"
            surf.blit(font.render(txt, True, col),
                      (lrect.x + 5 * S, ry + (ROW_H - FH) // 2))

        # ── right panel: detail ───────────────────────────────────────
        drect = pygame.Rect(DETAIL_X, 8 * S, DETAIL_W, FULL_H)
        draw_panel(surf, drect, PANEL_MID, BOX_BORDER, radius=6 * S)

        if not self.entries:
            return
        sid = self.entries[self.cursor]
        sp = self.game.data.species(sid)
        seen = sid in st.seen
        caught = sid in st.caught
        no = getattr(sp, "dex", 0) or 0

        if seen:
            # Sprite (scaled to fit)
            img = self.game.assets.battler(sid, sp.name, dex=getattr(sp, "dex", None))
            sprite_size = min(52 * S, DETAIL_W - 12 * S)
            img_s = pygame.transform.scale(img, (sprite_size, sprite_size))
            sx = drect.x + (drect.width - sprite_size) // 2
            surf.blit(img_s, (sx, drect.y + 6 * S))
            dy = drect.y + sprite_size + 10 * S
            # Dex # + name
            surf.blit(big.render(f"#{no:03d}  {sp.name}", True, (255, 255, 255)),
                      (drect.x + 8 * S, dy))
            dy += 20 * S
            # Type badges
            bx = drect.x + 8 * S
            for t in sp.types:
                r = draw_type_badge(surf, font, t, bx, dy)
                bx = r.right + 4 * S
            dy += 20 * S
            # Caught / Seen badge
            if caught:
                status_txt, status_col = "CAUGHT", (120, 230, 140)
            else:
                status_txt, status_col = "SEEN", (120, 190, 240)
            surf.blit(font.render(status_txt, True, status_col),
                      (drect.x + 8 * S, dy))
        else:
            # Silhouette placeholder
            cy = drect.y + drect.height // 2
            surf.blit(big.render("?", True, (182, 198, 222)),
                      (drect.x + drect.width // 2 - 10 * S, cy - 12 * S))
            surf.blit(font.render("Not yet encountered", True, (188, 205, 228)),
                      (drect.x + 8 * S, cy + 14 * S))


_VITAMIN_STAT = {
    "hp-up":   "hp",
    "protein":  "attack",
    "iron":     "defense",
    "calcium":  "special_attack",
    "zinc":     "special_defense",
    "carbos":   "speed",
}

_PP_RESTORE_ONE = {"ether": 10, "max-ether": None}   # None = full restore
_PP_RESTORE_ALL = {"elixir": 10, "max-elixir": None}  # None = full restore


def _tm_move_id(item) -> str | None:
    """Parse move ID from a TM/HM short_effect text."""
    eff = getattr(item, "short_effect", "") or ""
    if not eff.startswith("Teaches "):
        return None
    try:
        name = eff[8:].split(" to ")[0]
        return name.lower().replace(" ", "-")
    except Exception:
        return None


class BagScene(Scene):
    """Overworld bag: medicine, vitamins, PP items, evolution stones, TMs."""
    translucent = True

    def __init__(self, game):
        super().__init__(game)
        self.cursor = 0
        self.pocket = 0                    # active pocket tab index
        self.picking: str | None = None    # item id awaiting a party target
        self.pick_cursor = 0
        self.note = ""

    def items(self) -> list:
        all_items = [(k, v) for k, v in sorted(self.game.state.bag.items()) if v > 0]
        _, filt = _POCKETS[self.pocket]
        return [(k, v) for k, v in all_items
                if filt(self.game.data.item(k), k)]

    def _item_needs_target(self, item_id, it) -> bool:
        """True if the item needs a party-member target before use."""
        if it is None:
            return False
        if it.heal or it.cures or it.revive:
            return True
        if item_id in _VITAMIN_STAT:
            return True
        if item_id in _PP_RESTORE_ONE or item_id in _PP_RESTORE_ALL:
            return True
        if it.category == "pp-max-effect" or "pp-up" in item_id:
            return True
        if it.category == "evolution":
            return True
        if it.pocket == "machines":
            return True
        return False

    def handle(self, inp) -> None:
        st = self.game.state
        if self.picking is None:
            # Pocket switching
            if LEFT in inp.pressed:
                self.pocket = (self.pocket - 1) % len(_POCKETS)
                self.cursor = 0
                self.game.audio.play_sfx("menu_move")
            if RIGHT in inp.pressed:
                self.pocket = (self.pocket + 1) % len(_POCKETS)
                self.cursor = 0
                self.game.audio.play_sfx("menu_move")
            nav_list(self, inp, len(self.items()))
            if B in inp.pressed:
                self.game.pop()
            elif A in inp.pressed and self.items():
                item_id = self.items()[min(self.cursor,
                                           len(self.items()) - 1)][0]
                it = self.game.data.item(item_id)
                if self._item_needs_target(item_id, it):
                    self.picking = item_id
                    self.pick_cursor = 0
                elif not self._field_use(item_id, it):
                    self.note = "Can't use that here."
            return
        # choosing a target party member
        before = self.pick_cursor
        if DOWN in inp.pressed:
            self.pick_cursor = min(len(st.party) - 1, self.pick_cursor + 1)
        if UP in inp.pressed:
            self.pick_cursor = max(0, self.pick_cursor - 1)
        if self.pick_cursor != before:
            self.game.audio.play_sfx("menu_move")
        if B in inp.pressed:
            self.picking = None
            return
        if A in inp.pressed:
            mon = st.party[self.pick_cursor]
            item_id = self.picking
            self.picking = None
            self._dispatch(item_id, mon)

    def _dispatch(self, item_id, mon) -> None:
        """Route the item→mon combination to the right handler."""
        it = self.game.data.item(item_id)
        if it is None:
            self.note = "Unknown item."
            return
        # Vitamins
        if item_id in _VITAMIN_STAT:
            self._apply_vitamin(item_id, it, mon)
            return
        # PP restore all moves (Elixir / Max Elixir)
        if item_id in _PP_RESTORE_ALL:
            self._apply_elixir(item_id, it, mon)
            return
        # PP restore one move or PP Up/Max → push move picker
        if item_id in _PP_RESTORE_ONE or it.category == "pp-max-effect" \
                or "pp-up" in item_id:
            if mon.current_hp <= 0:
                self.note = "That Pokémon has fainted."
                return
            self.game.push(_MovePickerScene(self.game, item_id, mon))
            return
        # Evolution stones
        if it.category == "evolution":
            self._apply_stone(item_id, it, mon)
            return
        # TMs / HMs
        if it.pocket == "machines":
            self.game.push(_MovePickerScene(self.game, item_id, mon))
            return
        # Default: heal/cure/revive
        self._apply(item_id, mon)

    def _field_use(self, item_id, it) -> bool:
        """Field items used straight from the bag (no party target)."""
        st = self.game.state
        name = it.name if it else item_id.replace("-", " ").title()
        if "repel" in item_id:
            steps = {"repel": 100, "super-repel": 200,
                     "max-repel": 250}.get(item_id, 100)
            st.repel_steps = steps
            st.bag[item_id] = st.bag.get(item_id, 0) - 1
            self.note = f"Used {name}! Wild Pokemon will stay away ({steps})."
            return True
        if item_id == "escape-rope":
            mid, tile, facing = self.game.whiteout_location()
            if mid:
                st.bag[item_id] = st.bag.get(item_id, 0) - 1
                self.game.pending_warp = (mid, tile, facing)
                while len(self.game.scenes) > 1:
                    self.game.pop()
            return True
        return False

    def _apply(self, item_id, mon) -> None:
        st = self.game.state
        it = self.game.data.item(item_id)
        did = False
        if it.revive and mon.current_hp <= 0:
            mon.current_hp = max(1, int(mon.max_hp * it.revive))
            mon.status = None
            did = True
        elif mon.current_hp > 0:
            if it.heal and mon.current_hp < mon.max_hp:
                amount = mon.max_hp if it.heal == -1 else it.heal
                mon.current_hp = min(mon.max_hp, mon.current_hp + amount)
                did = True
            if it.cures and mon.status and ("all" in it.cures
                                            or mon.status in it.cures):
                mon.status = None
                did = True
        if did:
            st.bag[item_id] -= 1
            self.note = f"Used the {it.name}!"
        else:
            self.note = "It won't have any effect."

    def _apply_vitamin(self, item_id, it, mon) -> None:
        """Add 10 EVs to the stat corresponding to this vitamin."""
        from ..core.pokemon import PokemonState
        stat = _VITAMIN_STAT[item_id]
        evs = mon.evs
        total_evs = sum(evs.get(s, 0) for s in evs)
        current = evs.get(stat, 0)
        if current >= 100 or total_evs >= 510:
            self.note = "It won't have any effect."
            return
        add = min(10, 100 - current, 510 - total_evs)
        mon.evs[stat] = current + add
        mon.bind(self.game.data)  # recalculate stats
        self.game.state.bag[item_id] -= 1
        self.note = f"Used the {it.name}! ({stat.replace('_',' ').title()} EVs: {mon.evs[stat]})"
        self.game.audio.play_sfx("confirm")

    def _apply_elixir(self, item_id, it, mon) -> None:
        """Elixir / Max Elixir: restore PP for all moves."""
        if mon.current_hp <= 0:
            self.note = "That Pokémon has fainted."
            return
        max_restore = _PP_RESTORE_ALL[item_id]  # None = full
        restored = False
        for slot in mon.moves:
            if slot.pp < slot.pp_max:
                if max_restore is None:
                    slot.pp = slot.pp_max
                else:
                    slot.pp = min(slot.pp_max, slot.pp + max_restore)
                restored = True
        if restored:
            self.game.state.bag[item_id] -= 1
            self.note = f"Used the {it.name}!"
            self.game.audio.play_sfx("confirm")
        else:
            self.note = "PP is already full."

    def _apply_stone(self, item_id, it, mon) -> None:
        """Evolution stone: trigger EvolutionScene if applicable."""
        if mon.current_hp <= 0:
            self.note = "That Pokémon has fainted."
            return
        sp = self.game.data.species(mon.species_id)
        if sp is None:
            self.note = "It won't have any effect."
            return
        target_species = None
        for evo in sp.evolves_to:
            if isinstance(evo, dict):
                trigger = evo.get("trigger")
                evo_item = evo.get("item")
            else:
                trigger = getattr(evo, "trigger", None)
                evo_item = getattr(evo, "item", None)
            if trigger == "use-item" and evo_item == item_id:
                target_species = evo.get("species") if isinstance(evo, dict) \
                    else getattr(evo, "species", None)
                break
        if target_species is None:
            self.note = f"It won't have any effect on {mon.nickname or mon.species_id.title()}."
            return
        from .evolution import EvolutionScene
        self.game.state.bag[item_id] -= 1
        self.game.push(EvolutionScene(self.game, mon, target_species))

    def draw(self, surf) -> None:
        font = self.game.assets.font
        FH = font.get_height()
        items = self.items()
        MARGIN = 8 * S

        # ── pocket tabs ───────────────────────────────────────────────
        TAB_W = 34 * S
        TAB_H = 14 * S
        tabs_y = MARGIN
        for ti, (tlbl, _) in enumerate(_POCKETS):
            tx = MARGIN + ti * (TAB_W + 2 * S)
            is_active = (ti == self.pocket)
            bg = (60, 100, 170) if is_active else (30, 38, 58)
            pygame.draw.rect(surf, bg,
                             pygame.Rect(tx, tabs_y, TAB_W, TAB_H),
                             border_radius=3 * S)
            col = (255, 255, 255) if is_active else (205, 225, 252)
            surf.blit(font.render(tlbl, True, col),
                      (tx + (TAB_W - font.size(tlbl)[0]) // 2,
                       tabs_y + (TAB_H - FH) // 2))

        # ── item list panel ───────────────────────────────────────────
        LIST_W = 120 * S
        list_y = tabs_y + TAB_H + 3 * S
        list_h = LOGICAL_H - list_y - MARGIN - 24 * S
        lrect = pygame.Rect(MARGIN, list_y, LIST_W, list_h)
        draw_panel(surf, lrect, PANEL_DARK, BOX_BORDER, radius=4 * S)
        ROW_H = 14 * S
        avail = max(1, (list_h - 4 * S) // ROW_H)
        top = (0 if len(items) <= avail
               else max(0, min(self.cursor - avail // 2,
                               len(items) - avail)))
        if not items:
            surf.blit(font.render("(empty)", True, (188, 205, 228)),
                      (lrect.x + 8 * S, lrect.y + 8 * S))
        for ri, idx in enumerate(range(top, min(top + avail, len(items)))):
            k, v = items[idx]
            ry = lrect.y + 2 * S + ri * ROW_H
            is_sel = (idx == self.cursor and self.picking is None)
            if is_sel:
                pygame.draw.rect(surf, PANEL_SEL,
                                 pygame.Rect(lrect.x + 2 * S, ry,
                                             lrect.width - 4 * S, ROW_H),
                                 border_radius=3 * S)
            name = k.replace("-", " ").title()
            surf.blit(font.render(name, True,
                                  (255, 255, 255) if is_sel else (230, 242, 255)),
                      (lrect.x + 6 * S, ry + (ROW_H - FH) // 2))
            qty = str(v)
            qw = font.size(qty)[0]
            surf.blit(font.render(qty, True, (210, 230, 255)),
                      (lrect.right - qw - 6 * S, ry + (ROW_H - FH) // 2))

        # ── detail panel (right of list) ──────────────────────────────
        DETAIL_X = MARGIN + LIST_W + 4 * S
        DETAIL_W = LOGICAL_W - DETAIL_X - MARGIN
        drect = pygame.Rect(DETAIL_X, list_y, DETAIL_W, list_h)
        draw_panel(surf, drect, PANEL_MID, BOX_BORDER, radius=4 * S)
        if items and self.picking is None:
            k, _ = items[min(self.cursor, len(items) - 1)]
            it = self.game.data.item(k)
            if it:
                dy = drect.y + 8 * S
                surf.blit(font.render(it.name, True, (230, 245, 255)),
                          (drect.x + 8 * S, dy))
                dy += 16 * S
                if hasattr(it, "short_effect") and it.short_effect:
                    from .dialog import wrap_text as _wt
                    for line in _wt(font, it.short_effect, drect.width - 16 * S)[:4]:
                        surf.blit(font.render(line, True, (212, 230, 252)),
                                  (drect.x + 8 * S, dy))
                        dy += 14 * S

        # ── party picker overlay ──────────────────────────────────────
        if self.picking is not None:
            party = self.game.state.party
            pw = 120 * S
            ph = len(party) * 20 * S + 8 * S
            px = LOGICAL_W // 2 - pw // 2
            py = LOGICAL_H // 2 - ph // 2
            prect = pygame.Rect(px, py, pw, ph)
            draw_panel(surf, prect, PANEL_DARK, BOX_BORDER, radius=6 * S)
            surf.blit(font.render("Use on:", True, (238, 248, 255)),
                      (prect.x + 8 * S, prect.y + 4 * S))
            for i, p in enumerate(party):
                ry = prect.y + 20 * S + i * 20 * S
                is_sel = (i == self.pick_cursor)
                if is_sel:
                    pygame.draw.rect(surf, PANEL_SEL,
                                     pygame.Rect(prect.x + 2 * S, ry,
                                                 prect.width - 4 * S, 20 * S),
                                     border_radius=3 * S)
                name = p.nickname or p.species_id.title()
                hp = f"{max(0,p.current_hp)}/{p.max_hp}"
                surf.blit(font.render(f"{name}  {hp}", True,
                                      (255, 255, 255) if is_sel else (170, 200, 230)),
                          (prect.x + 8 * S, ry + (20 * S - FH) // 2))

        # ── note bar ──────────────────────────────────────────────────
        note_y = LOGICAL_H - MARGIN - 22 * S
        draw_panel(surf, pygame.Rect(MARGIN, note_y, LOGICAL_W - MARGIN * 2, 22 * S),
                   PANEL_DARK, radius=4 * S)
        note = self.note or "< / > switch pocket   A: use   B: back"
        surf.blit(font.render(note, True, (210, 230, 255)),
                  (MARGIN + 6 * S, note_y + (22 * S - FH) // 2))


class _MovePickerScene(Scene):
    """Sub-scene for picking a move slot when using PP items or TMs."""
    translucent = True

    def __init__(self, game, item_id: str, mon):
        super().__init__(game)
        self.item_id = item_id
        self.mon = mon
        self.cursor = 0
        self.note = ""
        it = game.data.item(item_id)
        self._it = it
        self._is_tm = (it is not None and it.pocket == "machines")
        self._tm_move = _tm_move_id(it) if self._is_tm else None
        self._is_pp_up = (it is not None and (
            it.category == "pp-max-effect" or "pp-up" in item_id))
        self._is_ether = item_id in _PP_RESTORE_ONE

    def _moves(self):
        return self.mon.moves

    def handle(self, inp) -> None:
        moves = self._moves()
        nav_list(self, inp, len(moves))
        if B in inp.pressed:
            self.game.pop()
            return
        if A in inp.pressed and moves:
            slot = moves[min(self.cursor, len(moves) - 1)]
            if self._is_tm:
                self._teach_tm(slot)
            elif self._is_pp_up:
                self._apply_pp_up(slot)
            elif self._is_ether:
                self._apply_ether(slot)

    def _teach_tm(self, slot_to_replace) -> None:
        """Teach the TM's move, replacing the selected move slot."""
        it = self._it
        move_id = self._tm_move
        if move_id is None:
            self.note = "Unknown TM move."
            return
        sp = self.game.data.species(self.mon.species_id)
        if sp is None or move_id not in sp.learnset.get("machine", []):
            self.note = f"{self.mon.nickname or self.mon.species_id.title()} can't learn that move!"
            return
        mv = self.game.data.move(move_id)
        if mv is None:
            self.note = "Move data not found."
            return
        # Replace the selected slot with the new move
        slot_to_replace.move_id = move_id
        slot_to_replace.pp = mv.pp
        slot_to_replace.pp_max = mv.pp
        # TMs in Gen 5 are reusable — do NOT decrement count
        self.note = f"{self.mon.nickname or self.mon.species_id.title()} learned {mv.name}!"
        self.game.audio.play_sfx("confirm")
        self.game.pop()

    def _apply_pp_up(self, slot) -> None:
        it = self._it
        mv = self.game.data.move(slot.move_id)
        if mv is None:
            self.note = "Move data not found."
            return
        base_pp = mv.pp
        max_possible = int(base_pp * 1.6)
        if slot.pp_max >= max_possible:
            self.note = "PP is already at maximum."
            return
        is_pp_max = ("pp-max" in self.item_id or
                     getattr(it, "category", "") == "pp-max-effect")
        if is_pp_max:
            slot.pp_max = max_possible
        else:
            slot.pp_max = min(max_possible, slot.pp_max + max(1, base_pp // 5))
        slot.pp = min(slot.pp, slot.pp_max)
        self.game.state.bag[self.item_id] -= 1
        mv_name = mv.name if mv else slot.move_id
        self.note = f"{mv_name}'s PP raised! (Max: {slot.pp_max})"
        self.game.audio.play_sfx("confirm")
        self.game.pop()

    def _apply_ether(self, slot) -> None:
        it = self._it
        restore = _PP_RESTORE_ONE.get(self.item_id, 10)
        if slot.pp >= slot.pp_max:
            self.note = "PP is already full."
            return
        if restore is None:
            slot.pp = slot.pp_max
        else:
            slot.pp = min(slot.pp_max, slot.pp + restore)
        self.game.state.bag[self.item_id] -= 1
        mv = self.game.data.move(slot.move_id)
        mv_name = mv.name if mv else slot.move_id
        self.note = f"{mv_name}'s PP restored!"
        self.game.audio.play_sfx("confirm")
        self.game.pop()

    def draw(self, surf) -> None:
        font = self.game.assets.font
        mon_name = self.mon.nickname or self.mon.species_id.title()
        it_name = self._it.name if self._it else self.item_id.title()
        rect = pygame.Rect(8 * S, 8 * S, LOGICAL_W - 16 * S, LOGICAL_H - 16 * S)
        draw_box(surf, rect)
        surf.blit(font.render(f"{it_name} → {mon_name}", True, TEXT),
                  (rect.x + 8 * S, rect.y + 8 * S))
        if self._is_tm and self._tm_move:
            mv = self.game.data.move(self._tm_move)
            mv_name = mv.name if mv else self._tm_move
            surf.blit(font.render(f"Teaches: {mv_name}", True, BOX_BORDER),
                      (rect.x + 8 * S, rect.y + 20 * S))
        header = "Replace move:" if self._is_tm else "Which move?"
        surf.blit(font.render(header, True, TEXT),
                  (rect.x + 8 * S, rect.y + 32 * S))
        for i, slot in enumerate(self.mon.moves):
            y = rect.y + 46 * S + i * 14 * S
            mv = self.game.data.move(slot.move_id)
            mv_name = mv.name if mv else slot.move_id
            if i == self.cursor:
                surf.blit(font.render(">", True, TEXT), (rect.x + 6 * S, y))
            pp_txt = f"  {slot.pp}/{slot.pp_max}" if not self._is_tm else ""
            surf.blit(font.render(f" {mv_name}{pp_txt}", True, TEXT),
                      (rect.x + 16 * S, y))
        if self.note:
            nrect = pygame.Rect(4 * S, LOGICAL_H - 24 * S,
                                LOGICAL_W - 8 * S, 20 * S)
            draw_box(surf, nrect)
            surf.blit(font.render(self.note, True, TEXT),
                      (nrect.x + 6 * S, nrect.y + 5 * S))


class PCScene(Scene):
    """Two-column storage: A moves the selected mon between party/box."""
    translucent = True

    def __init__(self, game):
        super().__init__(game)
        self.col = 0       # 0=party, 1=box
        self.cursor = 0

    def _lists(self):
        return self.game.state.party, self.game.state.pc

    def handle(self, inp) -> None:
        party, box = self._lists()
        cols = (party, box)
        before_col = self.col
        if LEFT in inp.pressed:
            self.col = 0
        if RIGHT in inp.pressed:
            self.col = 1
        if self.col != before_col:
            self.game.audio.play_sfx("menu_move")
        cur = cols[self.col]
        nav_list(self, inp, len(cur))
        self.cursor = min(self.cursor, max(0, len(cur) - 1))
        if B in inp.pressed:
            self.game.pop()
            return
        if A in inp.pressed and cur:
            mon = cur[self.cursor]
            if self.col == 0:
                able = [p for p in party if p.current_hp > 0 and p is not mon]
                if len(party) > 1 and able:        # never strand the player
                    party.remove(mon)
                    box.append(mon)
            else:
                if len(party) < 6:
                    box.remove(mon)
                    party.append(mon)

    def draw(self, surf) -> None:
        font, big = self.game.assets.font, self.game.assets.font_big
        rect = pygame.Rect(8 * S, 8 * S, LOGICAL_W - 16 * S, LOGICAL_H - 40 * S)
        draw_box(surf, rect)
        party, box = self._lists()
        for c, (label, rows) in enumerate((("PARTY", party), ("BOX", box))):
            x = rect.x + 8 * S + c * (rect.width // 2)
            surf.blit(big.render(label, True, TEXT), (x, rect.y + 6 * S))
            for i, p in enumerate(rows[:9]):
                y = rect.y + 24 * S + i * 14 * S
                if c == self.col and i == self.cursor:
                    surf.blit(font.render(">", True, TEXT), (x - 8 * S, y))
                surf.blit(font.render(
                    f"{(p.nickname or p.species_id.title())} Lv{p.level}",
                    True, TEXT), (x, y))
        tip = "A: move   LEFT/RIGHT: column   B: close"
        surf.blit(font.render(tip, True, BOX_BORDER),
                  (rect.x + 8 * S, rect.bottom + 6 * S))


class ChoiceScene(Scene):
    """Script `choice`: prompt + options; the pick lands on
    game.last_choice and the runner splices that branch."""
    translucent = True

    def __init__(self, game, prompt, labels):
        super().__init__(game)
        self.prompt = prompt
        self.labels = labels or ["OK"]
        self.cursor = 0

    def handle(self, inp) -> None:
        nav_list(self, inp, len(self.labels))
        if B in inp.pressed:
            self.cursor = len(self.labels) - 1   # B = last option (decline)
        if A in inp.pressed or B in inp.pressed:
            self.game.last_choice = self.cursor
            self.game.pop()

    def draw(self, surf) -> None:
        font = self.game.assets.font
        rect = pygame.Rect(4 * S, LOGICAL_H - 52 * S, LOGICAL_W - 8 * S, 48 * S)
        draw_box(surf, rect)
        for i, line in enumerate(wrap_text(font, self.prompt,
                                           rect.width - 16 * S)[:2]):
            surf.blit(font.render(line, True, TEXT),
                      (rect.x + 8 * S, rect.y + 6 * S + i * 12 * S))
        orect = pygame.Rect(LOGICAL_W - 86 * S,
                            rect.y - 14 * S * len(self.labels) - 14 * S,
                            80 * S, 14 * S * len(self.labels) + 10 * S)
        draw_box(surf, orect)
        for i, label in enumerate(self.labels):
            y = orect.y + 5 * S + i * 14 * S
            if i == self.cursor:
                surf.blit(font.render(">", True, TEXT), (orect.x + 4 * S, y))
            surf.blit(font.render(label, True, TEXT), (orect.x + 13 * S, y))


class ShopScene(Scene):
    """Script `shop`: a Poke Mart with BUY and SELL. Buy prices come from
    the script override, then the item catalog's cost, then 100; items
    sell for half their catalog cost."""
    translucent = True

    def __init__(self, game, item_ids, prices=None):
        super().__init__(game)
        self.buy_rows = []
        for iid in item_ids:
            it = game.data.item(iid)
            if it is None:
                continue
            price = int((prices or {}).get(iid, it.cost or 100))
            self.buy_rows.append((iid, it.name, price))
        self.mode = "menu"            # menu | buy | sell
        self.cursor = 0
        self.note = "Welcome! What'll it be?"

    def _sell_rows(self):
        rows = []
        for iid, qty in sorted(self.game.state.bag.items()):
            it = self.game.data.item(iid)
            price = (it.cost or 0) // 2 if it else 0
            if qty > 0 and price > 0:
                rows.append((iid, it.name, price, qty))
        return rows

    def handle(self, inp) -> None:
        st = self.game.state
        if self.mode == "menu":
            opts = ("BUY", "SELL", "EXIT")
            nav_list(self, inp, len(opts))
            if B in inp.pressed:
                self.game.pop()
            elif A in inp.pressed:
                pick = opts[self.cursor]
                if pick == "EXIT":
                    self.game.pop()
                else:
                    self.mode, self.cursor = pick.lower(), 0
            return
        if B in inp.pressed:
            self.mode, self.cursor = "menu", 0
            return
        if self.mode == "buy":
            n = len(self.buy_rows)
            nav_list(self, inp, n)
            if A in inp.pressed and self.buy_rows:
                iid, name, price = self.buy_rows[min(self.cursor, n - 1)]
                if st.money >= price:
                    st.money -= price
                    st.bag[iid] = st.bag.get(iid, 0) + 1
                    self.note = f"Bought a {name}!"
                else:
                    self.note = "You can't afford that."
        else:                                       # sell
            rows = self._sell_rows()
            n = len(rows)
            nav_list(self, inp, n)
            if A in inp.pressed and rows:
                iid, name, price, _ = rows[min(self.cursor, n - 1)]
                st.bag[iid] -= 1
                if st.bag[iid] <= 0:
                    del st.bag[iid]
                st.money += price
                self.note = f"Sold a {name} for ${price}."

    def draw(self, surf) -> None:
        font = self.game.assets.font
        if self.mode == "menu":
            rows = ["BUY", "SELL", "EXIT"]
        elif self.mode == "buy":
            rows = [f"{n:<14} ${p}  (x{self.game.state.bag.get(i, 0)})"
                    for i, n, p in self.buy_rows] or ["(nothing)"]
        else:
            rows = [f"{n:<14} ${p}  (x{q})"
                    for _, n, p, q in self._sell_rows()] or ["(nothing to sell)"]
        rect = pygame.Rect(8 * S, 8 * S, 180 * S,
                           14 * S * max(1, len(rows)) + 12 * S)
        draw_box(surf, rect)
        for i, label in enumerate(rows):
            y = rect.y + 7 * S + i * 14 * S
            if i == self.cursor and not label.startswith("("):
                surf.blit(font.render(">", True, TEXT), (rect.x + 5 * S, y))
            surf.blit(font.render(label, True, TEXT), (rect.x + 14 * S, y))
        foot = pygame.Rect(8 * S, rect.bottom + 4 * S, 180 * S, 32 * S)
        draw_box(surf, foot)
        surf.blit(font.render(f"Money: ${self.game.state.money}", True, TEXT),
                  (foot.x + 6 * S, foot.y + 4 * S))
        surf.blit(font.render(self.note, True, BOX_BORDER),
                  (foot.x + 6 * S, foot.y + 17 * S))


class ControlsScene(Scene):
    """Remap keys to the game's actions. Up/Down choose an action, Confirm
    starts a rebind (then press any key; Esc aborts), Cancel goes back, and
    a Reset row restores the defaults. Changes save immediately."""
    translucent = True

    def __init__(self, game):
        super().__init__(game)
        self.cursor = 0
        self.binding = False
        self.rows = list(keybinds.ACTION_IDS) + ["__reset__"]
        self.note = "Confirm: rebind    Cancel: back"

    def handle(self, inp) -> None:
        if self.binding:
            for code in sorted(inp.raw):
                name = keybinds.key_name(code)
                if name == "escape":
                    self.binding = False
                    self.note = "Rebind cancelled."
                    return
                if name == "?" or name in keybinds.RESERVED:
                    continue
                action = self.rows[self.cursor]
                self.game.apply_bindings(
                    keybinds.rebind(self.game.bindings, action, name))
                self.binding = False
                self.game.audio.play_sfx("confirm")
                self.note = f"{keybinds.label(action)} -> '{name}'"
                return
            return
        nav_list(self, inp, len(self.rows))
        if B in inp.pressed:
            self.game.audio.play_sfx("menu_back")
            self.game.pop()
            return
        if A in inp.pressed:
            row = self.rows[self.cursor]
            if row == "__reset__":
                self.game.apply_bindings(keybinds.default_bindings())
                self.game.audio.play_sfx("confirm")
                self.note = "Restored default controls."
            else:
                self.binding = True
                self.note = f"Press a key for {keybinds.label(row)}  (Esc: cancel)"

    def draw(self, surf) -> None:
        font, big = self.game.assets.font, self.game.assets.font_big
        rect = pygame.Rect(8 * S, 8 * S, LOGICAL_W - 16 * S, LOGICAL_H - 16 * S)
        draw_box(surf, rect)
        surf.blit(big.render("CONTROLS", True, TEXT), (rect.x + 8 * S, rect.y + 8 * S))
        y = rect.y + 32 * S
        for i, row in enumerate(self.rows):
            sel = (i == self.cursor)
            if sel:
                surf.blit(font.render(">", True, TEXT), (rect.x + 6 * S, y))
            if row == "__reset__":
                surf.blit(font.render("Reset to defaults", True, TEXT),
                          (rect.x + 16 * S, y))
            else:
                keys = ("< press a key >" if sel and self.binding
                        else keybinds.keys_label(self.game.bindings, row))
                surf.blit(font.render(f"{keybinds.label(row):<9} {keys}",
                                      True, TEXT), (rect.x + 16 * S, y))
            y += 13 * S
        surf.blit(font.render(self.note, True, BOX_BORDER),
                  (rect.x + 8 * S, rect.bottom - 20 * S))


class BadgesScene(Scene):
    """Display earned badges."""
    translucent = True

    def __init__(self, game):
        super().__init__(game)

    def handle(self, inp) -> None:
        if A in inp.pressed or B in inp.pressed:
            self.game.pop()

    def draw(self, surf) -> None:
        font, big = self.game.assets.font, self.game.assets.font_big
        rect = pygame.Rect(8 * S, 8 * S, LOGICAL_W - 16 * S, LOGICAL_H - 16 * S)
        draw_box(surf, rect)
        surf.blit(big.render("BADGES", True, TEXT), (rect.x + 8 * S, rect.y + 8 * S))
        badges = sorted(self.game.state.badges)
        if not badges:
            surf.blit(font.render("No badges yet.", True, TEXT),
                      (rect.x + 8 * S, rect.y + 32 * S))
        else:
            for i, badge in enumerate(badges):
                y = rect.y + 32 * S + i * 14 * S
                surf.blit(font.render(f"  {badge.replace('-', ' ').title()} Badge",
                                      True, TEXT), (rect.x + 8 * S, y))
        surf.blit(font.render(f"Total: {len(badges)}", True, BOX_BORDER),
                  (rect.x + 8 * S, rect.bottom - 20 * S))


class FlyScene(Scene):
    """Town Map / Fly destination chooser. Only maps with `fly_name` in their
    props and present in `visited_maps` are shown."""
    translucent = True

    def __init__(self, game):
        super().__init__(game)
        self.cursor = 0
        self._spots = self._build_spots()

    def _build_spots(self):
        """Return list of (display_name, map_id, spawn_tile) for all visited
        maps that declare a fly_name."""
        st = self.game.state
        ow = self.game.scenes[0] if self.game.scenes else None
        world = getattr(ow, "world", None)
        spots = []
        for mid in sorted(st.visited_maps):
            if world is not None:
                try:
                    tm = world.get(mid)
                    name = tm.props.get("fly_name")
                    if name:
                        spots.append((name, mid, tm.spawn))
                except Exception:
                    pass
        return spots

    def handle(self, inp) -> None:
        nav_list(self, inp, len(self._spots))
        if B in inp.pressed:
            self.game.pop()
            return
        if A in inp.pressed and self._spots:
            name, mid, spawn = self._spots[min(self.cursor, len(self._spots) - 1)]
            self.game.state.facing = "down"
            self.game.pending_warp = (mid, spawn, "down")
            while len(self.game.scenes) > 1:
                self.game.pop()

    def draw(self, surf) -> None:
        font, big = self.game.assets.font, self.game.assets.font_big
        rect = pygame.Rect(8 * S, 8 * S, LOGICAL_W - 16 * S, LOGICAL_H - 16 * S)
        draw_box(surf, rect)
        surf.blit(big.render("FLY TO WHERE?", True, TEXT),
                  (rect.x + 8 * S, rect.y + 8 * S))
        if not self._spots:
            surf.blit(font.render("No destinations visited yet.", True, TEXT),
                      (rect.x + 8 * S, rect.y + 32 * S))
        else:
            for i, (name, mid, _) in enumerate(self._spots):
                y = rect.y + 32 * S + i * 14 * S
                if i == self.cursor:
                    surf.blit(font.render(">", True, TEXT), (rect.x + 6 * S, y))
                surf.blit(font.render(name, True, TEXT), (rect.x + 16 * S, y))
        surf.blit(font.render("A: fly there   B: cancel", True, BOX_BORDER),
                  (rect.x + 8 * S, rect.bottom - 20 * S))


class HeldItemPicker(Scene):
    """Choose a holdable bag item for `mon` to hold; swaps any current item."""
    translucent = True

    def __init__(self, game, mon):
        super().__init__(game)
        self.mon = mon
        self.cursor = 0

    def items(self):
        out = []
        for iid, qty in sorted(self.game.state.bag.items()):
            it = self.game.data.item(iid)
            if qty > 0 and it and it.holdable and not it.is_ball:
                out.append((iid, it.name, qty))
        return out

    def handle(self, inp) -> None:
        items = self.items()
        nav_list(self, inp, len(items))
        if B in inp.pressed:
            self.game.audio.play_sfx("menu_back")
            self.game.pop()
            return
        if A in inp.pressed and items:
            iid, name, _ = items[min(self.cursor, len(items) - 1)]
            st = self.game.state
            if self.mon.held_item:                     # return the old one
                st.bag[self.mon.held_item] = \
                    st.bag.get(self.mon.held_item, 0) + 1
            st.bag[iid] = st.bag.get(iid, 0) - 1
            if st.bag[iid] <= 0:
                del st.bag[iid]
            self.mon.held_item = iid
            self.game.audio.play_sfx("confirm")
            self.game.pop()

    def draw(self, surf) -> None:
        font = self.game.assets.font
        items = self.items()
        rect = pygame.Rect(8 * S, 8 * S, 200 * S,
                           14 * S * max(1, len(items)) + 46 * S)
        draw_box(surf, rect)
        who = self.mon.nickname or self.mon.species_id.title()
        surf.blit(font.render(f"Give to {who}:", True, TEXT),
                  (rect.x + 8 * S, rect.y + 6 * S))
        if not items:
            surf.blit(font.render("(no holdable items)", True, TEXT),
                      (rect.x + 14 * S, rect.y + 24 * S))
        for i, (iid, name, qty) in enumerate(items):
            y = rect.y + 24 * S + i * 14 * S
            if i == self.cursor:
                surf.blit(font.render(">", True, TEXT), (rect.x + 5 * S, y))
            surf.blit(font.render(f"{name}  x{qty}", True, TEXT),
                      (rect.x + 14 * S, y))
        surf.blit(font.render("A: give   B: cancel", True, BOX_BORDER),
                  (rect.x + 8 * S, rect.bottom - 18 * S))
