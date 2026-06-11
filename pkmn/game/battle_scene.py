"""Battle UI: a scene that drives the pure BattleEngine and renders its
Event stream. Text comes from the same format_event used by the CLI
demo, so engine output reads identically everywhere."""
from __future__ import annotations

import pygame

from ..battle.ai import GreedyAI, RandomAI
from ..battle.engine import BattleEngine, Phase
from ..battle.state import (CatchAction, ItemAction, MoveAction, P1, P2,
                            RunAction, SwitchAction)
from ..cli.battle_demo import format_event
from .config import A, B, DOWN, LEFT, LOGICAL_H, LOGICAL_W, RIGHT, UP
from .dialog import BOX_BORDER, TEXT, draw_box, wrap_chunks
from .scene import Scene

GREEN = (88, 200, 96)
YELLOW = (232, 200, 64)
RED = (216, 72, 64)


class BattleScene(Scene):
    def __init__(self, game, foe_party, *, wild: bool = True,
                 trainer_name: str | None = None):
        super().__init__(game)
        st = game.state
        self.wild = wild
        self.eng = BattleEngine(game.data, st.party, foe_party,
                                wild=wild, rng=st.rng)
        self.ai = (RandomAI(P2, st.rng) if wild else GreedyAI(P2, st.rng))
        self.pages: list = []          # message pages (lists of lines)
        self.mode = "msg"
        self.cursor = 0
        self.disp_hp = {P1: float(self.eng.active(P1).current_hp),
                        P2: float(self.eng.active(P2).current_hp)}
        self._push(self.eng._start_events)
        if trainer_name:
            self.pages.insert(0, [f"{trainer_name} wants to battle!"])

    # ── event plumbing ───────────────────────────────────────────────
    def _push(self, events) -> None:
        font = self.game.assets.font
        for ev in events:
            line = format_event(ev)
            if line:
                self.pages.extend(wrap_chunks(font, line.strip(),
                                              LOGICAL_W - 28))

    def _submit(self, action) -> None:
        ev = self.eng.submit_turn(action, self.ai.choose_action(self.eng))
        self._push(ev)
        self._auto_replace_foe()
        self.mode = "msg"
        self.cursor = 0

    def _auto_replace_foe(self) -> None:
        while (self.eng.phase == Phase.WAITING_REPLACEMENT
               and P2 in self.eng.pending_replacements):
            idx = self.ai.choose_replacement(self.eng)
            self._push(self.eng.submit_replacement(P2, idx))

    def _decide(self) -> None:
        """Queue is drained: choose the next interactive mode."""
        if self.eng.over:
            self._queue_post_battle()
            self.mode = "msg" if self.pages else "done"
            return
        if self.eng.phase == Phase.WAITING_REPLACEMENT:
            self.mode = "party"
            self.cursor = 0
            return
        self.mode = "menu"
        self.cursor = 0

    _posted = False

    def _queue_post_battle(self) -> None:
        if self._posted:
            return
        self._posted = True
        st = self.game.state
        if self.eng.winner == "caught" and self.eng.caught_pokemon is not None:
            mon = self.eng.caught_pokemon
            if len(st.party) < 6:
                st.party.append(mon)
            else:
                self.pages.append([f"{mon.nickname or mon.species_id.title()}"
                                   " was sent to storage."])
        elif self.eng.winner == P2:
            st.heal_party()
            st.map_id, st.tile, st.facing = "town", None, "down"
            self.pages.append(["You whited out!",
                               "You rushed back home to recover."])

    # ── input ────────────────────────────────────────────────────────
    def handle(self, inp) -> None:
        m = self.mode
        if m == "msg":
            if A in inp.pressed or B in inp.pressed:
                if self.pages:
                    self.pages.pop(0)
                if not self.pages:
                    self._decide()
        elif m == "done":
            if A in inp.pressed or B in inp.pressed:
                self.game.pop()
        elif m == "menu":
            self._nav(inp, self._menu_items(), columns=2)
            if A in inp.pressed:
                self._pick_menu(self._menu_items()[self.cursor])
        elif m == "moves":
            acts = self._move_actions()
            self._nav(inp, acts, columns=2)
            if A in inp.pressed:
                self._submit(acts[self.cursor])
            elif B in inp.pressed:
                self.mode = "menu"
                self.cursor = 0
        elif m == "bag":
            items = self._bag_items()
            self._nav(inp, items, columns=1)
            if A in inp.pressed and items:
                self._use_item(items[self.cursor][0])
            elif B in inp.pressed:
                self.mode = "menu"
                self.cursor = 0
        elif m == "party":
            self._nav(inp, self.game.state.party, columns=1)
            if A in inp.pressed:
                self._pick_party(self.cursor)
            elif B in inp.pressed and self.eng.phase != Phase.WAITING_REPLACEMENT:
                self.mode = "menu"
                self.cursor = 0

    def _nav(self, inp, items, *, columns: int) -> None:
        n = max(1, len(items))
        if RIGHT in inp.pressed and columns > 1:
            self.cursor = min(n - 1, self.cursor + 1)
        if LEFT in inp.pressed and columns > 1:
            self.cursor = max(0, self.cursor - 1)
        if DOWN in inp.pressed:
            self.cursor = min(n - 1, self.cursor + columns)
        if UP in inp.pressed:
            self.cursor = max(0, self.cursor - columns)

    def _menu_items(self) -> list:
        return ["FIGHT", "BAG", "PKMN", "RUN"]

    def _pick_menu(self, item: str) -> None:
        if item == "FIGHT":
            self.mode = "moves"
            self.cursor = 0
        elif item == "BAG":
            self.mode = "bag"
            self.cursor = 0
        elif item == "PKMN":
            self.mode = "party"
            self.cursor = 0
        elif item == "RUN":
            self._submit(RunAction())

    def _move_actions(self) -> list:
        return [a for a in self.eng.legal_actions(P1)
                if isinstance(a, MoveAction)]

    def _bag_items(self) -> list:
        return [(k, v) for k, v in sorted(self.game.state.bag.items()) if v > 0]

    def _use_item(self, item_id: str) -> None:
        item = self.game.data.item(item_id)
        self.game.state.bag[item_id] -= 1
        if item is not None and item.category == "ball":
            self._submit(CatchAction(item_id))
        else:
            self._submit(ItemAction(item_id))

    def _pick_party(self, idx: int) -> None:
        st, eng = self.game.state, self.eng
        if eng.phase == Phase.WAITING_REPLACEMENT:
            if idx in eng.bench(P1):
                self._push(eng.submit_replacement(P1, idx))
                self._auto_replace_foe()
                self.mode = "msg"
        else:
            if any(isinstance(a, SwitchAction) and a.party_index == idx
                   for a in eng.legal_actions(P1)):
                self._submit(SwitchAction(idx))

    # ── frame update ─────────────────────────────────────────────────
    def update(self) -> None:
        for side in (P1, P2):
            target = float(self.eng.active(side).current_hp)
            cur = self.disp_hp[side]
            if abs(cur - target) < 0.6:
                self.disp_hp[side] = target
            else:
                self.disp_hp[side] = cur + (target - cur) * 0.18

    # ── render ───────────────────────────────────────────────────────
    def draw(self, surf) -> None:
        surf.fill((232, 240, 232))
        pygame.draw.rect(surf, (200, 224, 200),
                         (0, LOGICAL_H - 76, LOGICAL_W, 76))
        self._draw_battler(surf, P2, (LOGICAL_W - 72, 28))
        self._draw_battler(surf, P1, (28, 66))
        self._draw_info(surf, P2, pygame.Rect(6, 6, 110, 30))
        self._draw_info(surf, P1, pygame.Rect(LOGICAL_W - 122, 78, 116, 38),
                        numbers=True)
        rect = pygame.Rect(4, LOGICAL_H - 52, LOGICAL_W - 8, 48)
        draw_box(surf, rect)
        if self.mode in ("msg", "done"):
            self._draw_msg(surf, rect)
        elif self.mode == "menu":
            self._draw_grid(surf, rect, self._menu_items(), columns=2)
        elif self.mode == "moves":
            labels = []
            for a in self._move_actions():
                if a.move_id in ("struggle", "recharge"):
                    labels.append(a.move_id.title())
                else:
                    mv = self.game.data.move(a.move_id)
                    slot = self.eng.active(P1).state.move_slot(a.move_id)
                    pp = f" {slot.pp}/{slot.pp_max}" if slot else ""
                    labels.append(f"{mv.name}{pp}")
            self._draw_grid(surf, rect, labels, columns=2)
        elif self.mode == "bag":
            labels = [f"{k.replace('-', ' ').title()} x{v}"
                      for k, v in self._bag_items()] or ["(empty)"]
            self._draw_grid(surf, rect, labels, columns=1)
        elif self.mode == "party":
            labels = [f"{(p.nickname or p.species_id.title())} "
                      f"Lv{p.level} {max(0, p.current_hp)}/{p.max_hp}"
                      for p in self.game.state.party]
            self._draw_grid(surf, rect, labels, columns=1)

    def _draw_msg(self, surf, rect) -> None:
        font = self.game.assets.font
        page = self.pages[0] if self.pages else ["..."]
        for i, line in enumerate(page):
            surf.blit(font.render(line, True, TEXT),
                      (rect.x + 8, rect.y + 7 + i * 14))
        surf.blit(font.render("v", True, BOX_BORDER),
                  (rect.right - 14, rect.bottom - 14))

    def _draw_grid(self, surf, rect, labels, *, columns: int) -> None:
        font = self.game.assets.font
        rows = max(1, -(-len(labels) // columns))
        for i, label in enumerate(labels):
            col, row = i % columns, i // columns
            x = rect.x + 14 + col * (rect.width // columns)
            y = rect.y + 6 + row * max(12, (rect.height - 10) // rows)
            if i == self.cursor:
                surf.blit(font.render(">", True, TEXT), (x - 9, y))
            surf.blit(font.render(label, True, TEXT), (x, y))

    def _draw_battler(self, surf, side, pos) -> None:
        bp = self.eng.active(side)
        if bp.fainted:
            return
        img = self.game.assets.battler(bp.state.species_id, bp.name)
        surf.blit(img, pos)

    def _draw_info(self, surf, side, rect, *, numbers: bool = False) -> None:
        bp = self.eng.active(side)
        draw_box(surf, rect)
        font = self.game.assets.font
        surf.blit(font.render(f"{bp.name}  Lv{bp.level}", True, TEXT),
                  (rect.x + 6, rect.y + 4))
        frac = max(0.0, min(1.0, self.disp_hp[side] / bp.max_hp))
        bar = pygame.Rect(rect.x + 6, rect.y + 17, rect.width - 12, 5)
        pygame.draw.rect(surf, (90, 96, 110), bar, border_radius=2)
        if frac > 0:
            color = GREEN if frac > 0.5 else YELLOW if frac > 0.2 else RED
            fill = bar.copy()
            fill.width = max(1, int(bar.width * frac))
            pygame.draw.rect(surf, color, fill, border_radius=2)
        if numbers:
            surf.blit(font.render(
                f"{max(0, int(round(self.disp_hp[side])))}/{bp.max_hp}",
                True, TEXT), (rect.x + 6, rect.y + 24))
