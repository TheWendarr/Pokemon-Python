"""Pause menu, party list, summary screen, overworld bag, and PC box."""
from __future__ import annotations

import pygame

from ..core.pokemon import PokemonState
from .config import A, B, DOWN, LEFT, LOGICAL_H, LOGICAL_W, RIGHT, SCALE as S, UP
from .dialog import BOX_BORDER, TEXT, draw_box, wrap_text
from .save import save_game
from .scene import Scene


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
            o for o, feat in (("POKEMON", "menu_party"), ("BAG", "menu_bag"),
                              ("SAVE", "saving"), ("POKEDEX", "pokedex"))
            if game.feature(feat)) + ("CLOSE",)

    def handle(self, inp) -> None:
        nav_list(self, inp, len(self.OPTIONS))
        if B in inp.pressed:
            self.game.pop()
            return
        if A in inp.pressed:
            pick = self.OPTIONS[self.cursor]
            if pick == "POKEDEX":
                self.game.push(PokedexScene(self.game))
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
        rect = pygame.Rect(LOGICAL_W - 92 * S, 6 * S, 86 * S,
                           14 * S * len(self.OPTIONS) + 12 * S)
        draw_box(surf, rect)
        font = self.game.assets.font
        for i, label in enumerate(self.OPTIONS):
            y = rect.y + 7 * S + i * 14 * S
            if i == self.cursor:
                surf.blit(font.render(">", True, TEXT), (rect.x + 5 * S, y))
            surf.blit(font.render(label, True, TEXT), (rect.x + 14 * S, y))
        if self.note:
            nrect = pygame.Rect(4 * S, LOGICAL_H - 24 * S, 110 * S, 20 * S)
            draw_box(surf, nrect)
            surf.blit(font.render(self.note, True, TEXT),
                      (nrect.x + 6 * S, nrect.y + 5 * S))


class PartyScene(Scene):
    """Party list. A on a slot opens a small menu — SUMMARY, MOVE, CANCEL.
    Choosing MOVE picks the mon up; pick another slot to swap them into
    place. B backs out (cancelling a move-in-progress first)."""
    translucent = True
    ACTIONS = ("SUMMARY", "MOVE", "CANCEL")

    def __init__(self, game):
        super().__init__(game)
        self.cursor = 0
        self.held: int | None = None      # slot being moved
        self.menu: int | None = None      # action-menu cursor (None = closed)

    def handle(self, inp) -> None:
        party = self.game.state.party
        if self.menu is not None:                     # action menu is open
            if UP in inp.pressed:
                self.menu = max(0, self.menu - 1)
            if DOWN in inp.pressed:
                self.menu = min(len(self.ACTIONS) - 1, self.menu + 1)
            if B in inp.pressed:
                self.menu = None
            elif A in inp.pressed:
                act = self.ACTIONS[self.menu]
                self.menu = None
                if act == "SUMMARY":
                    self.game.push(SummaryScene(self.game, party[self.cursor]))
                elif act == "MOVE":
                    self.held = self.cursor
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

    def draw(self, surf) -> None:
        party = self.game.state.party
        rect = pygame.Rect(8 * S, 8 * S, LOGICAL_W - 16 * S,
                           18 * S * len(party) + 12 * S)
        draw_box(surf, rect)
        font = self.game.assets.font
        for i, p in enumerate(party):
            y = rect.y + 7 * S + i * 18 * S
            mark = ">" if i == self.cursor else ("^" if i == self.held else " ")
            label = (f"{mark} {(p.nickname or p.species_id.title())} "
                     f"Lv{p.level}  {max(0, p.current_hp)}/{p.max_hp}"
                     f"{'  ' + p.status.upper()[:3] if p.status else ''}")
            color = (216, 152, 60) if i == self.held else TEXT
            surf.blit(font.render(label, True, color), (rect.x + 6 * S, y))
        hint = ("Pick a slot to swap into." if self.held is not None
                else "A: options   B: back")
        surf.blit(font.render(hint, True, BOX_BORDER),
                  (rect.x + 6 * S, rect.bottom + 4 * S))
        if self.menu is not None:                     # action-menu popup
            mw, mh = 76 * S, 14 * S * len(self.ACTIONS) + 10 * S
            mr = pygame.Rect(rect.right - mw, rect.bottom + 2 * S, mw, mh)
            draw_box(surf, mr)
            for i, act in enumerate(self.ACTIONS):
                yy = mr.y + 6 * S + i * 14 * S
                if i == self.menu:
                    surf.blit(font.render(">", True, TEXT), (mr.x + 4 * S, yy))
                surf.blit(font.render(act, True, TEXT), (mr.x + 14 * S, yy))



class SummaryScene(Scene):
    translucent = True

    def __init__(self, game, mon):
        super().__init__(game)
        self.mon = mon

    def handle(self, inp) -> None:
        if A in inp.pressed or B in inp.pressed:
            self.game.pop()

    def draw(self, surf) -> None:
        from ..core.experience import exp_total
        m = self.mon
        rect = pygame.Rect(8 * S, 8 * S, LOGICAL_W - 16 * S, LOGICAL_H - 16 * S)
        draw_box(surf, rect)
        font, big = self.game.assets.font, self.game.assets.font_big
        sp = m.species
        img = self.game.assets.battler(
            m.species_id, m.nickname or sp.name,
            dex=getattr(sp, "dex", None))
        surf.blit(img, (rect.right - img.get_width() - 8 * S, rect.y + 8 * S))
        surf.blit(big.render(f"{m.nickname or sp.name}  Lv{m.level}",
                             True, TEXT), (rect.x + 8 * S, rect.y + 8 * S))
        surf.blit(font.render("/".join(sp.types).upper(), True, TEXT),
                  (rect.x + 8 * S, rect.y + 24 * S))
        y = rect.y + 40 * S
        for key in ("hp", "attack", "defense", "special_attack",
                    "special_defense", "speed"):
            label = key.replace("special_", "sp. ").replace("_", " ")
            val = (f"{max(0, m.current_hp)}/{m.max_hp}" if key == "hp"
                   else m.stats[key])
            surf.blit(font.render(f"{label}: {val}", True, TEXT),
                      (rect.x + 8 * S, y))
            y += 12 * S
        nxt = exp_total(sp.growth_rate, m.level + 1) if m.level < 100 else m.exp
        surf.blit(font.render(f"exp: {m.exp}  (next: {max(0, nxt - m.exp)})",
                              True, TEXT), (rect.x + 8 * S, y))
        y += 16 * S
        for slot in m.moves:
            mv = self.game.data.move(slot.move_id)
            surf.blit(font.render(f"{mv.name}  {slot.pp}/{slot.pp_max}",
                                  True, TEXT), (rect.x + 8 * S, y))
            y += 12 * S
        # right column (under the sprite): nature / gender+shiny / ability / friendship
        cx, cy = rect.x + 130 * S, rect.y + 70 * S
        g = {"male": "Male", "female": "Female"}.get(m.gender, "")
        meta = [f"{m.nature.title()} nature"]
        gs = "   ".join(t for t in (g, "SHINY" if m.shiny else "") if t)
        if gs:
            meta.append(gs)
        ab = m.ability.replace("-", " ").title() if m.ability else "-"
        meta.append(f"Ability: {ab}")
        meta.append(f"Friendship: {m.friendship}")
        for ln in meta:
            surf.blit(font.render(ln, True, TEXT), (cx, cy))
            cy += 12 * S


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
        rect = pygame.Rect(8 * S, 8 * S, LOGICAL_W - 16 * S, LOGICAL_H - 16 * S)
        draw_box(surf, rect)
        surf.blit(big.render(
            f"POKEDEX    Seen {len(st.seen)}   Caught {len(st.caught)}",
            True, TEXT), (rect.x + 8 * S, rect.y + 8 * S))
        rows = max(1, (rect.height - 42 * S) // (12 * S))
        top = 0 if len(self.entries) <= rows else \
            max(0, min(self.cursor - rows // 2, len(self.entries) - rows))
        for r, idx in enumerate(range(top, min(top + rows, len(self.entries)))):
            sid = self.entries[idx]
            sp = self.game.data.species(sid)
            no = getattr(sp, "dex", 0) or 0
            y = rect.y + 32 * S + r * 12 * S
            if idx == self.cursor:
                surf.blit(font.render(">", True, TEXT), (rect.x + 6 * S, y))
            if sid in st.caught:
                txt = f"#{no:03d}  {sp.name}  OWN"
            elif sid in st.seen:
                txt = f"#{no:03d}  {sp.name}"
            else:
                txt = f"#{no:03d}  ----------"
            surf.blit(font.render(txt, True, TEXT), (rect.x + 16 * S, y))


class BagScene(Scene):
    """Overworld bag: medicine applies to a chosen party member."""
    translucent = True

    def __init__(self, game):
        super().__init__(game)
        self.cursor = 0
        self.picking: str | None = None   # item id awaiting a target
        self.pick_cursor = 0
        self.note = ""

    def items(self) -> list:
        return [(k, v) for k, v in sorted(self.game.state.bag.items()) if v > 0]

    def handle(self, inp) -> None:
        st = self.game.state
        if self.picking is None:
            nav_list(self, inp, len(self.items()))
            if B in inp.pressed:
                self.game.pop()
            elif A in inp.pressed and self.items():
                item_id = self.items()[min(self.cursor,
                                           len(self.items()) - 1)][0]
                it = self.game.data.item(item_id)
                if it and (it.heal or it.cures or it.revive):
                    self.picking = item_id
                    self.pick_cursor = 0
                elif not self._field_use(item_id, it):
                    self.note = "Can't use that here."
            return
        # choosing a target party member
        if DOWN in inp.pressed:
            self.pick_cursor = min(len(st.party) - 1, self.pick_cursor + 1)
        if UP in inp.pressed:
            self.pick_cursor = max(0, self.pick_cursor - 1)
        if B in inp.pressed:
            self.picking = None
            return
        if A in inp.pressed:
            self._apply(self.picking, st.party[self.pick_cursor])
            self.picking = None

    def _field_use(self, item_id, it) -> bool:
        """Field items used straight from the bag (no party target):
        Repel keeps weak wild Pokemon away; Escape Rope warps to the last
        heal point."""
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

    def draw(self, surf) -> None:
        font = self.game.assets.font
        items = self.items() or [("(empty)", "")]
        rect = pygame.Rect(8 * S, 8 * S, 140 * S, 14 * S * len(items) + 12 * S)
        draw_box(surf, rect)
        for i, (k, v) in enumerate(items):
            y = rect.y + 7 * S + i * 14 * S
            if i == self.cursor and self.picking is None:
                surf.blit(font.render(">", True, TEXT), (rect.x + 5 * S, y))
            label = f"{k.replace('-', ' ').title()}" + (f" x{v}" if v else "")
            surf.blit(font.render(label, True, TEXT), (rect.x + 14 * S, y))
        if self.picking is not None:
            party = self.game.state.party
            prect = pygame.Rect(60 * S, 40 * S, 150 * S,
                                14 * S * len(party) + 12 * S)
            draw_box(surf, prect)
            for i, p in enumerate(party):
                y = prect.y + 7 * S + i * 14 * S
                if i == self.pick_cursor:
                    surf.blit(font.render(">", True, TEXT), (prect.x + 5 * S, y))
                surf.blit(font.render(
                    f"{(p.nickname or p.species_id.title())} "
                    f"{max(0, p.current_hp)}/{p.max_hp}", True, TEXT),
                    (prect.x + 14 * S, y))
        if self.note:
            nrect = pygame.Rect(4 * S, LOGICAL_H - 24 * S, 160 * S, 20 * S)
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
        if LEFT in inp.pressed:
            self.col = 0
        if RIGHT in inp.pressed:
            self.col = 1
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
