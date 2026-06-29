"""Battle UI: drives the pure BattleEngine and renders its Event stream
as a *sequenced* animation timeline.

The engine resolves a whole turn at once and hands back an ordered list
of Events. Rather than dump them, the scene translates each event into
timed steps and plays them one at a time: the attacker lunges while its
move text shows, then the target's HP bar drains (with a hit flash),
then any "super effective!" line, then the next mover repeats, then
faints sink away. Sending a mon out throws a pokeball that bursts into
the creature ("Go X!"); a wild capture throws a ball, sucks the foe in,
and the ball *wobbles on screen* (no "*shake*" text) before it clicks
shut or breaks open. Text stays aligned with the action and lingers a
readable beat (~2s); pressing A/B skips a line and holding A/B
fast-forwards. The FIGHT/BAG/PKMN cursors and your last move slot are
remembered between turns (the move slot resets when you switch). Battle
text still comes from the same format_event used by the CLI demo.
"""
from __future__ import annotations

import math

import pygame

from . import daytime

# Battle backdrop palettes by location: (sky, ground). Weather recolours the
# sky on top of this, and the day/night tint is blended over everything.
_BACKDROPS = {
    "field":    ((200, 226, 240), (176, 210, 150)),
    "forest":   ((176, 208, 222), (120, 168, 104)),
    "cave":     ((58, 54, 70),    (96, 86, 80)),
    "water":    ((158, 206, 236), (110, 174, 208)),
    "sand":     ((238, 222, 172), (216, 196, 150)),
    "snow":     ((220, 234, 246), (232, 240, 248)),
    "mountain": ((196, 210, 226), (158, 150, 140)),
    "indoor":   ((150, 140, 158), (182, 166, 150)),
}
_WEATHER_SKY = {
    "rain": (150, 164, 186), "sun": (250, 226, 168),
    "sandstorm": (222, 198, 150), "hail": (214, 230, 240),
}

from ..battle.ai import GreedyAI, RandomAI
from ..battle.engine import BattleEngine, Phase
from ..battle.events import E
from ..battle.state import (CatchAction, ItemAction, MoveAction, P1, P2,
                            RunAction, SwitchAction)
from ..cli.battle_demo import format_event
from ..core.experience import battle_exp, exp_total
from ..core.pokemon import gain_exp
from .config import (A, B, DOWN, LEFT, LOGICAL_H, LOGICAL_W, RIGHT, SCALE as S,
                     SPRITE_PX, UP)
from .dialog import (BOX_BORDER, PANEL_DARK, PANEL_MID, PANEL_SEL, TEXT,
                      TYPE_PALETTE, draw_box, draw_panel, draw_status_badge,
                      draw_type_badge, wrap_chunks)
from .scene import Scene

GREEN = (88, 200, 96)
YELLOW = (232, 200, 64)
RED = (216, 72, 64)

LUNGE_DUR = 14          # frames for an attack lunge (out + back)
LUNGE_AMP = 9 * S       # pixels of lunge travel
FAINT_DUR = 26          # frames for a fainting sprite to sink + fade
FLASH_DUR = 15          # frames a struck sprite blinks
HP_LERP = 0.2           # HP bar easing factor per frame
HP_SNAP = 0.6           # close enough to call the drain finished
EXP_FILL_DUR = 60       # frames for a full EXP bar sweep (scales by distance)
LEVELUP_DUR  = 48       # frames for the blue level-up glow (sine pulse)
THROW_ARC = 14          # frames a thrown ball is in flight (send-out)
THROW_DUR = 26          # send-out: ball flight + materialise
CATCH_FLY = 14          # catch: ball flying at the foe
CATCH_ABSORB = 10       # catch: foe sucked into the ball
CATCH_DROP = 8          # catch: ball drops to the ground
CATCH_THROW_DUR = CATCH_FLY + CATCH_ABSORB + CATCH_DROP
CATCH_SHAKE_DUR = 26    # one visual wobble (no text)
CATCH_CLICK_DUR = 18    # the "click" on a successful catch
CATCH_BREAK_DUR = 18    # the ball bursting open on a failed catch
BALL_D = 12 * S         # pokeball diameter


class BattleScene(Scene):
    def __init__(self, game, foe_party, *, wild: bool = True,
                 trainer_name: str | None = None, weather: str | None = None,
                 backdrop: str | None = None, format: str = "single"):
        super().__init__(game)
        st = game.state
        self.wild = wild
        self.format = format
        self.doubles = format == "double"
        self.backdrop = backdrop or getattr(game, "battle_bg", "field")
        self.eng = BattleEngine(game.data, st.party, foe_party,
                                wild=wild, rng=st.rng,
                                dex_caught=len(st.caught), format=format)
        # Doubles UI: collected per-slot move choices, and which slot we are
        # currently picking a move for.
        self.pending_actions: list = []
        self.pick_slot = 0
        self.target_choice = 0
        for fp in foe_party:                 # Pokedex: these have been seen
            st.register_seen(fp.species_id)
        self.ai = (RandomAI(P2, st.rng) if wild else GreedyAI(P2, st.rng))
        game.audio.play_music("battle_wild" if wild else "battle_trainer")
        self.mode = "anim"
        self.cursor = 0
        self.cursors = {"menu": 0, "moves": 0, "bag": 0}   # remembered per mode
        self._pending_evos: list = []
        self.pending_learns: list = []   # (PokemonState, move_id)

        # ── animation timeline state ─────────────────────────────────
        self.steps: list = []            # queue of step dicts
        self.cur: dict | None = None     # step currently playing
        self.message: list = []          # text lines shown in the box
        self.text_hold = 0               # frames a text step lingers
        self.anim: dict | None = None    # active lunge / faint animation
        self.flash = {P1: 0, P2: 0}      # hit-blink frames remaining
        self.faint = {P1: 0.0, P2: 0.0}  # sink progress 0..1
        self.disp_hp = {P1: float(self.eng.active(P1).current_hp),
                        P2: float(self.eng.active(P2).current_hp)}
        self.hp_target = dict(self.disp_hp)
        # display_mon tracks which BattlePokemon is *visually* on field for
        # each side — it lags the engine's active pointer so that the faint
        # animation always shows the fainted mon's sprite, not the replacement.
        self.display_mon = {P1: self.eng.active(P1), P2: self.eng.active(P2)}
        # revealed[side] gates drawing: info boxes and sprites are hidden until
        # the send-in animation (throw/send step) starts for that side.
        self.revealed = {P1: False, P2: False}
        # EXP bar: animated display position (0.0–1.0 within the current level).
        self.disp_exp_frac = self._exp_frac(self.eng.active(P1).state)
        if self.doubles:
            self.mode = "menu"     # skip the singles send-in animation timeline
            self.revealed = {P1: True, P2: True}
        self.foe_absorbed = False         # foe is currently inside a ball
        self.ball_pos = None              # resting ball position when absorbed
        self._ball_img = None             # cached pokeball surface

        if weather in ("rain", "sun", "sandstorm", "hail"):
            ev: list = []
            self.eng.set_weather(weather, -1, ev)
            self.eng.log.extend(ev)
            self.eng._start_events = list(self.eng._start_events) + ev
        if self.doubles:
            # Minimal doubles flow drives the engine synchronously; show a
            # simple intro line in the message box and go straight to FIGHT.
            self.message = ["A double battle began!"]
        else:
            self._enqueue_intro(trainer_name)

    # ── building the timeline ────────────────────────────────────────
    def _say(self, text: str, anim=None) -> None:
        """Wrap a string into one or more text steps (the lunge anim, if
        any, rides only the first page)."""
        if not text:
            return
        for i, lines in enumerate(wrap_chunks(self.game.assets.font,
                                              text.strip(), LOGICAL_W - 28 * S)):
            self.steps.append({"kind": "text", "lines": lines,
                               "anim": anim if i == 0 else None})

    def _say_page(self, lines, anim=None) -> None:
        self.steps.append({"kind": "text", "lines": list(lines), "anim": anim})

    def _enqueue(self, events) -> None:
        for ev in events:
            t, d, side = ev.type, ev.data, ev.side
            if t in (E.TURN_START, E.BATTLE_END):
                continue
            if t == E.MOVE_USED:
                self._say(format_event(ev), anim=("lunge", side))
            elif t == E.DAMAGE:
                self.steps.append({"kind": "hp", "side": side,
                                   "to": d["remaining_hp"]})
                extra = []
                if d.get("crit"):
                    extra.append("A critical hit!")
                eff = d.get("effectiveness", 1.0)
                if eff > 1:
                    extra.append("It's super effective!")
                elif 0 < eff < 1:
                    extra.append("It's not very effective...")
                if extra:
                    self._say_page([" ".join(extra)])
            elif t == E.FAINT:
                self.steps.append({"kind": "faint", "side": side, "sfx": "faint"})
                self._say(format_event(ev))
            elif t == E.SEND_IN:
                name = d.get("pokemon", "")
                if side == P1:                       # player throws a ball
                    self._say(f"Go {name}!")
                    self.steps.append({"kind": "throw", "side": P1,
                                       "cry": self._cry_for(P1)})
                elif self.wild:                      # wild foe just appears
                    self.steps.append({"kind": "send", "side": P2,
                                       "cry": self._cry_for(P2)})
                    self._say(f"A wild {name} appeared!")
                else:                                # trainer sends a ball
                    self._say(f"{name} was sent out!")
                    self.steps.append({"kind": "throw", "side": P2,
                                       "cry": self._cry_for(P2)})
            elif t == E.CATCH_ATTEMPT:
                self._say(format_event(ev))          # "Threw a Ball at X!"
                self.steps.append({"kind": "catch_throw", "sfx": "ball_throw"})
            elif t == E.CATCH_SHAKE:
                self.steps.append({"kind": "catch_shake", "sfx": "ball_shake"})
            elif t == E.CATCH_SUCCESS:
                self.steps.append({"kind": "catch_click", "sfx": "ball_click"})
                self._say(format_event(ev))          # "Gotcha! X was caught!"
            elif t == E.CATCH_FAIL:
                self.steps.append({"kind": "catch_break", "sfx": "ball_break"})
                self._say(format_event(ev))          # "It broke free!"
            elif "remaining_hp" in d and side in (P1, P2):
                self._say(format_event(ev))
                self.steps.append({"kind": "hp", "side": side,
                                   "to": d["remaining_hp"]})
            else:
                self._say(format_event(ev))

    @staticmethod
    def _hold(lines) -> int:
        # linger ~2s (longer for longer text); always A/B-skippable
        return max(110, min(190, 40 + sum(len(s) for s in lines) * 2))

    @staticmethod
    def _exp_frac(st) -> float:
        """EXP bar fill fraction (0–1) for the given PokemonState."""
        if st.level >= 100:
            return 1.0
        exp_at  = exp_total(st.species.growth_rate, st.level)
        exp_nxt = exp_total(st.species.growth_rate, st.level + 1)
        return max(0.0, min(1.0, (st.exp - exp_at) / max(1, exp_nxt - exp_at)))

    def _enqueue_intro(self, trainer_name: str | None = None) -> None:
        """Build the battle intro in the correct visual order:
        trainer text → foe sends out → player sends out → entry effects."""
        events = self.eng._start_events
        p2_sendins = [e for e in events if e.type == E.SEND_IN and e.side == P2]
        p1_sendins = [e for e in events if e.type == E.SEND_IN and e.side == P1]
        others = [e for e in events
                  if e.type not in (E.BATTLE_START, E.SEND_IN)]
        if trainer_name:
            self._say(f"{trainer_name} wants to battle!")
        self._enqueue(p2_sendins)   # foe comes out first (trainer throws / wild appears)
        self._enqueue(p1_sendins)   # player sends out second
        self._enqueue(others)       # entry ability/weather effects after both are on field

    # ── turn submission ──────────────────────────────────────────────
    def _submit(self, action) -> None:
        ev = self.eng.submit_turn(action, self.ai.choose_action(self.eng))
        self._enqueue(ev)
        self._award_exp(ev)
        self._auto_replace_foe()
        self.mode = "anim"
        self.cur = None
        self.cursor = 0

    def _award_exp(self, events) -> None:
        if not self.game.feature("experience"):
            return
        for ev in events:
            if ev.type != E.FAINT or ev.side != P2:
                continue
            foe = self.eng.active(P2)
            winner = self.eng.active(P1)
            if winner.fainted:
                continue
            amount = battle_exp(foe.state.species.base_experience,
                                foe.level, trainer=not self.wild,
                                winner_level=winner.level)
            self._award_evs(winner.state, foe.state.species.ev_yield)
            st = winner.state
            pre_frac = self._exp_frac(st)           # bar position before gain
            res = gain_exp(st, self.game.data, amount)
            self._say_page([f"{winner.name} gained {amount} EXP!"])
            if not res["levels"]:
                # No level-up: bar drifts from old position to new position.
                self.steps.append({"kind": "exp", "from": pre_frac,
                                   "to": self._exp_frac(st)})
            else:
                # One or more level-ups: bar fills to 100%, then a blue glow
                # plays (with the SFX), then the level-up text, then the bar
                # refills from 0 for the next level (or to the final position).
                self.steps.append({"kind": "exp", "from": pre_frac, "to": 1.0})
                for i, lvl in enumerate(res["levels"]):
                    self.steps.append({"kind": "levelup"})   # glow + SFX
                    self._say_page([f"{winner.name} grew to Lv{lvl}!"])
                    last = i == len(res["levels"]) - 1
                    self.steps.append({"kind": "exp", "from": 0.0,
                                       "to": self._exp_frac(st) if last else 1.0})
            for mid in res["moves"]:
                self._say_page([f"{winner.name} learned "
                                f"{self.game.data.move(mid).name}!"])
            for mid in res.get("full_moves", []):
                if self.game.feature("move_replacement"):
                    self.pending_learns.append((winner.state, mid))
                    self._say_page([f"{winner.name} wants to learn "
                                    f"{self.game.data.move(mid).name}!"])
                else:
                    self._say_page([f"{winner.name} couldn't learn "
                                    f"{self.game.data.move(mid).name}..."])
            if res["evolution"] and self.game.feature("evolution"):
                self._pending_evos.append((winner.state, res["evolution"]))

    @staticmethod
    def _award_evs(ps, ev_yield: dict) -> None:
        """Award effort values from ev_yield, capping 252/stat and 510 total."""
        if not ev_yield:
            return
        total = sum(ps.evs.values())
        for stat, amount in ev_yield.items():
            if total >= 510:
                break
            stat = stat.replace("-", "_")
            current = ps.evs.get(stat, 0)
            gain = min(amount, 252 - current, 510 - total)
            if gain > 0:
                ps.evs[stat] = current + gain
                total += gain

    def _auto_replace_foe(self) -> None:
        while (self.eng.phase == Phase.WAITING_REPLACEMENT
               and P2 in self.eng.pending_replacements):
            idx = self.ai.choose_replacement(self.eng)
            self._enqueue(self.eng.submit_replacement(P2, idx))

    # ── when the timeline drains ─────────────────────────────────────
    def _decide(self) -> None:
        if self.eng.over and not self._posted:
            self._queue_post_battle()
            if self.steps:
                return                       # play them, then decide again
        if self.pending_learns:
            self.mode = "learn"
            self.cursor = 0
            return
        if self.eng.over:
            if self._pending_evos:
                from .evolution import EvolutionScene
                for state, target in reversed(self._pending_evos):
                    self.game.push(EvolutionScene(self.game, state, target))
                self._pending_evos = []
                return    # suspended under EvolutionScene(s); resumes after pop
            self.mode = "done"
            return
        if self.eng.phase == Phase.WAITING_REPLACEMENT:
            self._enter("party")
            return
        self._enter("menu")

    _posted = False

    def _queue_post_battle(self) -> None:
        if self._posted:
            return
        self._posted = True
        st = self.game.state
        if self.eng.winner == P1:
            self.game.audio.play_music("victory", loop=False)
        if self.eng.winner == "caught" and self.eng.caught_pokemon is not None:
            mon = self.eng.caught_pokemon
            st.register_caught(mon.species_id)
            if len(st.party) < 6:
                st.party.append(mon)
            else:
                st.pc.append(mon)
                self._say_page([f"{mon.nickname or mon.species_id.title()}"
                                " was sent to the PC box."])
        # Filter to valid evos (P1 won, mon still conscious).
        # The cutscene (EvolutionScene) handles the evolve() call and text.
        self._pending_evos = [
            (m, t) for m, t in self._pending_evos
            if self.eng.winner == P1 and m.current_hp > 0
        ]
        if self.eng.winner == P2:
            st.heal_party()
            st.map_id, st.tile, st.facing = self.game.whiteout_location()
            self._say_page(["You whited out!",
                            "You rushed back home to recover."])

    # ── input ────────────────────────────────────────────────────────
    def handle(self, inp) -> None:
        held = getattr(inp, "held", ())
        self._ff = (A in held) or (B in held)    # hold A/B: fast-forward text
        m = self.mode
        if self.doubles and m in ("menu", "moves", "d_move", "d_target",
                                  "d_done"):
            self._handle_doubles(inp)
            return
        if m == "anim":
            if (A in inp.pressed or B in inp.pressed) and self.cur:
                self._skip_step()
        elif m == "done":
            if A in inp.pressed or B in inp.pressed:
                self.game.last_battle = self.eng.winner
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
                self._enter("menu")
        elif m == "bag":
            items = self._bag_items()
            self._nav(inp, items, columns=1)
            if A in inp.pressed and items:
                self._use_item(items[self.cursor][0])
            elif B in inp.pressed:
                self._enter("menu")
        elif m == "learn":
            mon, new_move = self.pending_learns[0]
            options = len(mon.moves) + 1          # 4 moves + give up
            self._nav(inp, range(options), columns=1)
            if A in inp.pressed:
                name = self.game.data.move(new_move).name
                if self.cursor < len(mon.moves):
                    old = self.game.data.move(mon.moves[self.cursor].move_id)
                    md = self.game.data.move(new_move)
                    from ..core.pokemon import MoveSlot
                    mon.moves[self.cursor] = MoveSlot(md.id, md.pp, md.pp)
                    self._say_page(["1, 2, and... poof!",
                                    f"Forgot {old.name} and learned {name}!"])
                else:
                    self._say_page([f"Gave up on learning {name}."])
                self.pending_learns.pop(0)
                self.mode = "anim"
                self.cur = None
                self.cursor = 0
            elif B in inp.pressed:
                self._say_page(["Gave up on learning "
                                f"{self.game.data.move(new_move).name}."])
                self.pending_learns.pop(0)
                self.mode = "anim"
                self.cur = None
                self.cursor = 0
        elif m == "party":
            self._nav(inp, self.game.state.party, columns=1)
            if A in inp.pressed:
                self._pick_party(self.cursor)
            elif B in inp.pressed and self.eng.phase != Phase.WAITING_REPLACEMENT:
                self._enter("menu")

    # ── doubles UI (minimal but playable) ────────────────────────────
    def _doubles_move_actions(self, slot: int) -> list:
        return [a for a in self.eng.legal_actions(P1, slot)
                if isinstance(a, MoveAction)]

    def _handle_doubles(self, inp) -> None:
        eng = self.eng
        # Replacement first: fill any of our fainted slots in turn.
        if eng.phase == Phase.WAITING_REPLACEMENT:
            self._enter_doubles_replacement()
            return
        if eng.over:
            self.mode = "d_done"
            if A in inp.pressed or B in inp.pressed:
                self.game.last_battle = eng.winner
                self.game.pop()
            return
        if self.mode in ("menu",):
            # Begin choosing moves for slot 0.
            self.pending_actions = []
            self.pick_slot = 0
            self.mode = "d_move"
            self.cursor = 0
        if self.mode == "d_move":
            acts = self._doubles_move_actions(self.pick_slot)
            self._nav(inp, acts or [0], columns=2)
            if A in inp.pressed and acts:
                self._chosen_move = acts[self.cursor]
                mv = (None if self._chosen_move.move_id
                      in ("struggle", "recharge")
                      else self.game.data.move(self._chosen_move.move_id))
                spread = mv is not None and mv.target == "all-other-pokemon"
                self_t = mv is not None and (mv.targets_user
                                             or mv.target == "user")
                if spread or self_t:
                    self._commit_doubles_move(self._chosen_move.move_id,
                                              target_slot=0)
                else:
                    self.target_choice = 0
                    self.cursor = 0
                    self.mode = "d_target"
        elif self.mode == "d_target":
            foes = [b for b in self.eng.actives(P2)]
            self._nav(inp, foes, columns=2)
            if A in inp.pressed:
                self._commit_doubles_move(self._chosen_move.move_id,
                                          target_slot=self.cursor)
            elif B in inp.pressed:
                self.mode = "d_move"
                self.cursor = 0

    def _commit_doubles_move(self, move_id: str, target_slot: int) -> None:
        self.pending_actions.append(MoveAction(move_id, target_slot=target_slot))
        n_slots = len(self.eng.active_slots[P1])
        if self.pick_slot + 1 < n_slots:
            self.pick_slot += 1
            self.mode = "d_move"
            self.cursor = 0
        else:
            self._submit_doubles()

    def _submit_doubles(self) -> None:
        eng = self.eng
        foe_actions = self.ai.choose_actions(eng, n=len(eng.active_slots[P2]))
        ev = eng.submit_turn(self.pending_actions, foe_actions)
        self._award_exp(ev)
        self.message = [format_event(e) for e in ev
                        if "remaining_hp" in e.data or e.type == E.MOVE_USED][-4:] \
            or ["..."]
        for s in (P1, P2):
            self.disp_hp[s] = float(self.eng.active(s).current_hp)
            self.hp_target[s] = self.disp_hp[s]
        self.pending_actions = []
        self.pick_slot = 0
        if eng.over:
            self.mode = "d_done"
        elif eng.phase == Phase.WAITING_REPLACEMENT:
            self._enter_doubles_replacement()
        else:
            self.mode = "menu"
        self.cursor = 0

    def _enter_doubles_replacement(self) -> None:
        eng = self.eng
        # Auto-handle the foe; let the player pick for their own slots.
        for item in list(eng.pending_replacements):
            s, slot = item if isinstance(item, tuple) else (item, 0)
            if s == P2 and eng.bench(P2):
                eng.submit_replacement(P2, self.ai.choose_replacement(eng, slot),
                                       slot=slot)
        # Player replacements: pick the first benched mon for each slot.
        for item in list(eng.pending_replacements):
            s, slot = item if isinstance(item, tuple) else (item, 0)
            if s == P1 and eng.bench(P1):
                eng.submit_replacement(P1, eng.bench(P1)[0], slot=slot)
        for s in (P1, P2):
            self.disp_hp[s] = float(self.eng.active(s).current_hp)
            self.hp_target[s] = self.disp_hp[s]
        self.mode = "d_done" if eng.over else "menu"

    def _doubles_pos(self, side, slot):
        """Top-left of a doubles battler sprite (slot 1 sits slightly in)."""
        if side == P1:
            base_x, base_y = 8 * S, 84 * S
            return (base_x + slot * 56 * S, base_y - slot * 6 * S)
        base_x, base_y = LOGICAL_W - 66 * S, 24 * S
        return (base_x - slot * 52 * S, base_y + slot * 6 * S)

    def _draw_doubles(self, surf) -> None:
        self._draw_backdrop(surf)
        font = self.game.assets.font
        for side in (P2, P1):
            for slot, bp in enumerate(self.eng.actives(side)):
                if bp.fainted:
                    continue
                pos = self._doubles_pos(side, slot)
                dex = getattr(self.game.data.species(bp.state.species_id),
                              "dex", None)
                img = self.game.assets.battler(bp.state.species_id, bp.name,
                                               dex=dex, back=(side == P1))
                w = int(SPRITE_PX * 0.78)
                surf.blit(pygame.transform.scale(img, (w, w)), pos)
        # Compact info boxes, one per active slot.
        boxes = {
            (P2, 0): pygame.Rect(6 * S, 6 * S, 80 * S, 22 * S),
            (P2, 1): pygame.Rect(92 * S, 18 * S, 80 * S, 22 * S),
            (P1, 0): pygame.Rect(LOGICAL_W - 86 * S, 70 * S, 80 * S, 22 * S),
            (P1, 1): pygame.Rect(LOGICAL_W - 166 * S, 86 * S, 80 * S, 22 * S),
        }
        for side in (P1, P2):
            for slot, bp in enumerate(self.eng.actives(side)):
                rect = boxes[(side, slot)]
                draw_panel(surf, rect, PANEL_DARK, BOX_BORDER, radius=4 * S)
                surf.blit(font.render(f"{bp.name} Lv{bp.level}", True, (255, 255, 255)),
                          (rect.x + 4 * S, rect.y + 2 * S))
                frac = max(0.0, min(1.0, bp.current_hp / bp.max_hp))
                bar = pygame.Rect(rect.x + 4 * S, rect.y + 14 * S,
                                  rect.width - 8 * S, 4 * S)
                pygame.draw.rect(surf, (90, 96, 110), bar, border_radius=S)
                if frac > 0:
                    color = GREEN if frac > 0.5 else YELLOW if frac > 0.2 else RED
                    fill = bar.copy()
                    fill.width = max(1, int(bar.width * frac))
                    pygame.draw.rect(surf, color, fill, border_radius=S)
        rect = pygame.Rect(4 * S, LOGICAL_H - 52 * S, LOGICAL_W - 8 * S, 48 * S)
        draw_panel(surf, rect, PANEL_DARK, BOX_BORDER, radius=5 * S)
        if self.mode in ("menu", "d_done"):
            self._draw_msg(surf, rect)
        elif self.mode == "d_move":
            head = font.render(f"[slot {self.pick_slot}] choose a move",
                               True, (255, 255, 255))
            surf.blit(head, (rect.x + 8 * S, rect.y + 4 * S))
            labels = []
            for a in self._doubles_move_actions(self.pick_slot):
                if a.move_id in ("struggle", "recharge"):
                    labels.append(a.move_id.title())
                else:
                    labels.append(self.game.data.move(a.move_id).name)
            self._draw_grid(surf, pygame.Rect(rect.x, rect.y + 14 * S,
                                              rect.width, rect.height - 14 * S),
                            labels, columns=2)
        elif self.mode == "d_target":
            surf.blit(font.render("Target:", True, (255, 255, 255)),
                      (rect.x + 8 * S, rect.y + 4 * S))
            labels = [f"foe{slot} ({bp.name})"
                      for slot, bp in enumerate(self.eng.actives(P2))]
            self._draw_grid(surf, pygame.Rect(rect.x, rect.y + 14 * S,
                                              rect.width, rect.height - 14 * S),
                            labels, columns=2)

    def _skip_step(self) -> None:
        k = self.cur["kind"]
        if k == "text":
            self.text_hold = 0
            if self.anim and self.anim["type"] == "lunge":
                self.anim = None
        elif k == "hp":
            s = self.cur["side"]
            self.disp_hp[s] = self.hp_target[s]
            self.flash[s] = 0
        elif k == "faint":
            if self.anim:
                self.anim["t"] = self.anim["dur"]

    def _nav(self, inp, items, *, columns: int) -> None:
        n = max(1, len(items))
        c = self.cursor
        if RIGHT in inp.pressed and columns > 1:
            c += 1
        if LEFT in inp.pressed and columns > 1:
            c -= 1
        if DOWN in inp.pressed:
            c += columns
        if UP in inp.pressed:
            c -= columns
        new = c % n                               # wrap around
        if new != self.cursor:
            self.game.audio.play_sfx("menu_move")
        self.cursor = new
        if self.mode in self._MEMO:
            self.cursors[self.mode] = self.cursor

    _MEMO = ("menu", "moves", "bag")

    def _enter(self, mode: str) -> None:
        """Switch UI mode, restoring the remembered cursor for menus that
        keep it, so re-opening FIGHT lands on your last move (BAG and the
        main menu likewise). Move memory resets when a mon is switched."""
        self.mode = mode
        if mode in self._MEMO:
            n = len(self._list_for(mode))
            self.cursor = min(self.cursors.get(mode, 0), n - 1) if n else 0
        else:
            self.cursor = 0

    def _list_for(self, mode: str) -> list:
        if mode == "moves":
            return self._move_actions()
        if mode == "bag":
            return self._bag_items()
        return self._menu_items()

    def _menu_items(self) -> list:
        return ["FIGHT", "BAG", "PKMN", "RUN"]

    def _pick_menu(self, item: str) -> None:
        if item == "FIGHT":
            self._enter("moves")
        elif item == "BAG":
            self._enter("bag")
        elif item == "PKMN":
            self._enter("party")
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
        if item is not None and item.is_ball:
            self._submit(CatchAction(item_id))
        else:
            self._submit(ItemAction(item_id))

    def _pick_party(self, idx: int) -> None:
        st, eng = self.game.state, self.eng
        if eng.phase == Phase.WAITING_REPLACEMENT:
            if idx in eng.bench(P1):
                self.cursors["moves"] = 0
                self._enqueue(eng.submit_replacement(P1, idx))
                self._auto_replace_foe()
                self.mode = "anim"
                self.cur = None
        else:
            if any(isinstance(a, SwitchAction) and a.party_index == idx
                   for a in eng.legal_actions(P1)):
                self.cursors["moves"] = 0
                self._submit(SwitchAction(idx))

    # ── frame update: drive the timeline ─────────────────────────────
    def update(self) -> None:
        if self.doubles:
            return   # the doubles flow drives the engine synchronously
        for s in (P1, P2):
            if self.flash[s] > 0:
                self.flash[s] -= 1
            cur, tgt = self.disp_hp[s], self.hp_target[s]
            self.disp_hp[s] = tgt if abs(cur - tgt) < HP_SNAP \
                else cur + (tgt - cur) * HP_LERP
        if self.anim:
            self.anim["t"] += 1
            if self.anim["type"] == "exp_fill":
                a = self.anim
                progress = min(1.0, a["t"] / a["dur"])
                self.disp_exp_frac = a["from"] + (a["to"] - a["from"]) * progress
            if self.anim["t"] >= self.anim["dur"]:
                kind = self.anim["type"]
                if kind == "faint":
                    self.faint[self.anim["side"]] = 1.0
                elif kind == "catch_throw":
                    self.foe_absorbed = True          # foe now inside the ball
                    self.ball_pos = self._ball_rest()
                elif kind == "catch_break":
                    self.foe_absorbed = False          # foe pops back out
                elif kind == "exp_fill":
                    self.disp_exp_frac = self.anim["to"]  # snap to final
                self.anim = None
        if self.mode != "anim":
            return
        if self.cur is None:
            self._advance_steps()
            return
        if self._step_done():
            self.cur = None
            self._advance_steps()

    def _step_done(self) -> bool:
        k = self.cur["kind"]
        if k == "text":
            if self.text_hold > 0:
                self.text_hold -= 4 if getattr(self, "_ff", False) else 1
            return self.text_hold <= 0 and self.anim is None
        if k == "hp":
            s = self.cur["side"]
            return (abs(self.disp_hp[s] - self.hp_target[s]) < HP_SNAP
                    and self.flash[s] == 0)
        if k in ("faint", "throw", "exp", "levelup", "catch_throw",
                 "catch_shake", "catch_click", "catch_break"):
            return self.anim is None
        return True

    def _cry_for(self, side):
        sp = self.eng.active(side).state.species
        return getattr(sp, "dex", 0) or 0

    def _advance_steps(self) -> None:
        while self.cur is None:
            if not self.steps:
                self._decide()
                return
            step = self.steps.pop(0)
            self.cur = step
            if step.get("sfx"):
                self.game.audio.play_sfx(step["sfx"])
            if step.get("cry"):
                self.game.audio.play_cry(step["cry"])
            kind = step["kind"]
            if kind == "text":
                self.message = step["lines"]
                self.text_hold = self._hold(step["lines"])
                if step.get("anim"):
                    atype, aside = step["anim"]
                    self.anim = {"type": atype, "side": aside,
                                 "t": 0, "dur": LUNGE_DUR}
            elif kind == "hp":
                s = step["side"]
                if step["to"] < self.disp_hp[s] - 0.5:
                    self.flash[s] = FLASH_DUR
                    self.game.audio.play_sfx("hit")
                self.hp_target[s] = float(step["to"])
            elif kind == "faint":
                self.anim = {"type": "faint", "side": step["side"],
                             "t": 0, "dur": FAINT_DUR}
            elif kind == "send":
                s = step["side"]
                self.revealed[s] = True
                self.display_mon[s] = self.eng.active(s)
                self.faint[s] = 0.0
                v = float(self.eng.active(s).current_hp)
                self.disp_hp[s] = self.hp_target[s] = v
                self.cur = None                  # instantaneous; load next
                continue
            elif kind == "throw":
                s = step["side"]
                self.revealed[s] = True
                self.display_mon[s] = self.eng.active(s)
                self.faint[s] = 0.0
                v = float(self.eng.active(s).current_hp)
                self.disp_hp[s] = self.hp_target[s] = v
                self.anim = {"type": "throw", "side": s,
                             "t": 0, "dur": THROW_DUR}
            elif kind == "exp":
                span = abs(step["to"] - step["from"])
                dur = max(20, int(span * EXP_FILL_DUR))
                self.disp_exp_frac = step["from"]
                self.anim = {"type": "exp_fill", "t": 0, "dur": dur,
                             "from": step["from"], "to": step["to"]}
            elif kind == "levelup":
                self.game.audio.play_sfx("level_up")
                self.anim = {"type": "levelup", "t": 0, "dur": LEVELUP_DUR}
            elif kind == "catch_throw":
                self.anim = {"type": "catch_throw", "t": 0,
                             "dur": CATCH_THROW_DUR}
            elif kind == "catch_shake":
                self.anim = {"type": "catch_shake", "t": 0,
                             "dur": CATCH_SHAKE_DUR}
            elif kind == "catch_click":
                self.anim = {"type": "catch_click", "t": 0,
                             "dur": CATCH_CLICK_DUR}
            elif kind == "catch_break":
                self.anim = {"type": "catch_break", "t": 0,
                             "dur": CATCH_BREAK_DUR}
            return

    # ── render ───────────────────────────────────────────────────────
    def _draw_backdrop(self, surf) -> None:
        """A simple sky-over-ground backdrop, tinted by the weather, in
        place of a flat fill (the platform band sits on the ground)."""
        sky, ground = _BACKDROPS.get(self.backdrop, _BACKDROPS["field"])
        sky = _WEATHER_SKY.get(self.eng.weather, sky)   # weather recolours sky
        surf.fill(sky)
        pygame.draw.rect(surf, ground, (0, LOGICAL_H - 84 * S, LOGICAL_W, 84 * S))
        pygame.draw.rect(surf, tuple(max(0, c - 16) for c in ground),
                         (0, LOGICAL_H - 76 * S, LOGICAL_W, 6 * S))
        day = daytime.tint(self.game.time_phase())     # dusk/night wash
        if day[3]:
            dov = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
            dov.fill(day)
            surf.blit(dov, (0, 0))

    def draw(self, surf) -> None:
        if self.doubles:
            self._draw_doubles(surf)
            return
        self._draw_backdrop(surf)
        self._draw_battler(surf, P2, self._pos(P2))
        self._draw_battler(surf, P1, self._pos(P1))      # just above the box
        self._draw_ball_overlay(surf)
        self._draw_info(surf, P2, pygame.Rect(6 * S, 6 * S, 110 * S, 30 * S))
        self._draw_info(surf, P1,
                        pygame.Rect(LOGICAL_W - 122 * S, 98 * S, 116 * S, 41 * S),
                        numbers=True)
        rect = pygame.Rect(4 * S, LOGICAL_H - 52 * S, LOGICAL_W - 8 * S, 48 * S)
        draw_panel(surf, rect, PANEL_DARK, BOX_BORDER, radius=5 * S)
        if self.mode in ("anim", "done"):
            self._draw_msg(surf, rect)
        elif self.mode == "menu":
            self._draw_menu_buttons(surf, rect)
        elif self.mode == "moves":
            self._draw_move_slots(surf, rect)
        elif self.mode == "bag":
            labels = [f"{k.replace('-', ' ').title()} x{v}"
                      for k, v in self._bag_items()] or ["(empty)"]
            self._draw_grid(surf, rect, labels, columns=1)
        elif self.mode == "party":
            labels = [f"{(p.nickname or p.species_id.title())} "
                      f"Lv{p.level} {max(0, p.current_hp)}/{p.max_hp}"
                      for p in self.game.state.party]
            self._draw_grid(surf, rect, labels, columns=1)
        elif self.mode == "learn":
            mon, _new = self.pending_learns[0]
            labels = ["Forget " + self.game.data.move(s.move_id).name
                      for s in mon.moves] + ["Give up"]
            self._draw_grid(surf, rect, labels, columns=1)

    def _draw_msg(self, surf, rect) -> None:
        font = self.game.assets.font
        lines = self.message or ["..."]
        for i, line in enumerate(lines):
            surf.blit(font.render(line, True, (255, 255, 255)),
                      (rect.x + 8 * S, rect.y + 7 * S + i * 14 * S))
        waiting = self.mode == "done" or (self.cur is not None
                                          and self.cur["kind"] == "text")
        if waiting:
            surf.blit(font.render("v", True, (180, 210, 255)),
                      (rect.right - 14 * S, rect.bottom - 14 * S))

    def _draw_grid(self, surf, rect, labels, *, columns: int) -> None:
        """Generic text grid (used for party and bag mode)."""
        font = self.game.assets.font
        FH = font.get_height()
        rows = max(1, -(-len(labels) // columns))
        for i, label in enumerate(labels):
            col, row = i % columns, i // columns
            cw = rect.width // columns
            ch = max(12 * S, (rect.height - 10 * S) // rows)
            x = rect.x + 14 * S + col * cw
            y = rect.y + 6 * S + row * ch
            if i == self.cursor:
                hl = pygame.Rect(rect.x + 2 * S + col * cw, rect.y + 2 * S + row * ch,
                                 cw - 4 * S, ch - 2 * S)
                pygame.draw.rect(surf, PANEL_SEL, hl, border_radius=3 * S)
            surf.blit(font.render(label, True,
                                  (255, 255, 255) if i == self.cursor else TEXT),
                      (x, y + (ch - FH) // 2))

    # ── battle-specific styled grids ─────────────────────────────────
    _MENU_COLORS = {
        "FIGHT":  (185,  38,  38),
        "BAG":    (185, 148,  32),
        "PKMN":   ( 32, 156, 138),
        "RUN":    ( 90, 100, 118),
    }

    def _draw_menu_buttons(self, surf, rect) -> None:
        """Styled 2×2 FIGHT/BAG/PKMN/RUN action buttons."""
        font = self.game.assets.font
        FH = font.get_height()
        items = self._menu_items()
        cols, rows_n = 2, 2
        cw = rect.width // cols
        ch = rect.height // rows_n
        pad = 5 * S
        for i, label in enumerate(items):
            col, row = i % cols, i // cols
            bx = rect.x + col * cw + pad
            by = rect.y + row * ch + pad
            bw, bh = cw - pad * 2, ch - pad * 2
            brect = pygame.Rect(bx, by, bw, bh)
            base_col = self._MENU_COLORS.get(label, (80, 90, 110))
            is_sel = (i == self.cursor)
            btn_col = tuple(min(255, c + 35) for c in base_col) if is_sel else base_col
            pygame.draw.rect(surf, btn_col, brect, border_radius=5 * S)
            if is_sel:
                pygame.draw.rect(surf, (255, 255, 255), brect,
                                 width=2 * S, border_radius=5 * S)
            tw, th = font.size(label)
            surf.blit(font.render(label, True, (255, 255, 255)),
                      (bx + (bw - tw) // 2, by + (bh - FH) // 2))

    def _draw_move_slots(self, surf, rect) -> None:
        """Type-coloured move slots with detail panel on the left."""
        font = self.game.assets.font
        FH = font.get_height()
        acts = self._move_actions()
        bp = self.eng.active(P1)

        # Left: selected-move detail panel
        DETAIL_W = 76 * S
        drect = pygame.Rect(rect.x + 4 * S, rect.y + 4 * S,
                            DETAIL_W, rect.height - 8 * S)
        draw_panel(surf, drect, PANEL_DARK, None, radius=4 * S)
        if acts:
            sel = acts[min(self.cursor, len(acts) - 1)]
            mv = self.game.data.move(sel.move_id) if sel.move_id not in (
                "struggle", "recharge") else None
            if mv:
                dy = drect.y + 5 * S
                surf.blit(font.render(mv.name, True, (250, 252, 255)), (drect.x + 5 * S, dy))
                dy += FH + 2 * S
                draw_type_badge(surf, font, mv.type, drect.x + 5 * S, dy)
                dy += FH + 12 * S
                slot = bp.state.move_slot(sel.move_id)
                if slot:
                    pp_col = ((240, 80, 64) if slot.pp == 0
                              else (240, 200, 64) if slot.pp <= slot.pp_max // 4
                              else (180, 220, 255))
                    surf.blit(font.render(f"PP  {slot.pp}/{slot.pp_max}", True, pp_col),
                              (drect.x + 5 * S, dy))

        # Right: 2×2 move slot grid
        GRID_X = rect.x + DETAIL_W + 8 * S
        GRID_W = rect.right - GRID_X - 4 * S
        GRID_H = rect.height
        cols = 2
        n = len(acts)
        rows_n = max(1, -(-n // cols))
        cw = GRID_W // cols
        ch = GRID_H // max(2, rows_n)
        pad = 4 * S
        for i, a in enumerate(acts):
            col, row = i % cols, i // cols
            bx = GRID_X + col * cw + pad
            by = rect.y + row * ch + pad
            bw, bh = cw - pad * 2, ch - pad * 2
            brect = pygame.Rect(bx, by, bw, bh)
            mv = (None if a.move_id in ("struggle", "recharge")
                  else self.game.data.move(a.move_id))
            mtype = mv.type if mv else "typeless"
            bg = TYPE_PALETTE.get(mtype, TYPE_PALETTE["typeless"])[0]
            slot = bp.state.move_slot(a.move_id)
            # Grey out if PP empty
            if slot and slot.pp == 0:
                bg = tuple(int(c * 0.35 + 18) for c in bg)
            else:
                bg = tuple(int(c * 0.55 + 20) for c in bg)
            is_sel = (i == self.cursor)
            pygame.draw.rect(surf, bg, brect, border_radius=4 * S)
            border_col = (255, 255, 255) if is_sel else tuple(min(255, c + 50) for c in bg)
            pygame.draw.rect(surf, border_col, brect,
                             width=2 * S, border_radius=4 * S)
            mv_name = (a.move_id.title() if a.move_id in ("struggle", "recharge")
                       else (mv.name if mv else a.move_id))
            surf.blit(font.render(mv_name, True, (255, 255, 255)),
                      (bx + 5 * S, by + (bh - FH) // 2))

    # ── pokeball helpers (send-out + catch animations) ───────────────
    def _pos(self, side):
        """Top-left of a battler's sprite frame."""
        return (16 * S, 90 * S) if side == P1 else (LOGICAL_W - 72 * S, 28 * S)

    def _battler_center(self, side):
        x, y = self._pos(side)
        return (x + SPRITE_PX // 2, y + int(SPRITE_PX * 0.55))

    def _throw_origin(self, side):
        """Where a thrown ball starts (the off-screen trainer's hand)."""
        return ((LOGICAL_W * 0.16, LOGICAL_H - 40 * S) if side == P1
                else (LOGICAL_W * 0.9, 18 * S))

    def _ball_rest(self):
        """Where a ball settles after sucking the foe in."""
        x, y = self._pos(P2)
        return (x + SPRITE_PX * 0.34, y + SPRITE_PX * 0.55)

    def _pokeball(self):
        if self._ball_img is None:
            d = BALL_D
            r = d // 2
            img = pygame.Surface((d, d), pygame.SRCALPHA)
            pygame.draw.circle(img, (244, 244, 244), (r, r), r)     # white base
            top = pygame.Surface((d, r), pygame.SRCALPHA)
            pygame.draw.circle(top, (224, 64, 60), (r, r), r)       # red dome
            img.blit(top, (0, 0))
            band = max(2, d // 6)
            pygame.draw.rect(img, (32, 32, 36), (0, r - band // 2, d, band))
            pygame.draw.circle(img, (32, 32, 36), (r, r), r, max(1, d // 16))
            pygame.draw.circle(img, (32, 32, 36), (r, r), max(2, d // 6))
            pygame.draw.circle(img, (244, 244, 244), (r, r), max(1, d // 11))
            self._ball_img = img
        return self._ball_img

    def _draw_ball(self, surf, cx, cy, *, tilt=0.0, opening=0.0):
        img = self._pokeball()
        d = img.get_width()
        r = d // 2
        cx, cy = int(cx), int(cy)
        if opening > 0:                              # halves split + flash
            sep = int(opening * d * 0.5)
            surf.blit(img.subsurface((0, 0, d, r)), (cx - r, cy - r - sep))
            surf.blit(img.subsurface((0, r, d, d - r)), (cx - r, cy + sep))
            if opening > 0.25:
                fr = int(r * (0.8 + opening))
                fl = pygame.Surface((fr * 2, fr * 2), pygame.SRCALPHA)
                pygame.draw.circle(fl, (255, 255, 255,
                                        int(150 * (1 - opening))), (fr, fr), fr)
                surf.blit(fl, (cx - fr, cy - fr))
            return
        if tilt:
            img = pygame.transform.rotate(img, tilt)
        surf.blit(img, (cx - img.get_width() // 2, cy - img.get_height() // 2))

    @staticmethod
    def _arc(o, t, k, height):
        return (o[0] + (t[0] - o[0]) * k,
                o[1] + (t[1] - o[1]) * k - height * math.sin(math.pi * k))

    def _draw_ball_overlay(self, surf) -> None:
        a = self.anim
        rest = self.ball_pos or self._ball_rest()
        if a and a["type"] == "throw":
            if a["t"] < THROW_ARC:                   # ball still in flight
                x, y = self._arc(self._throw_origin(a["side"]),
                                 self._battler_center(a["side"]),
                                 a["t"] / THROW_ARC, 24 * S)
                self._draw_ball(surf, x, y, tilt=a["t"] * 30)
            return
        if a and a["type"] == "catch_throw":
            t, c = a["t"], self._battler_center(P2)
            if t < CATCH_FLY:
                x, y = self._arc(self._throw_origin(P1), c,
                                 t / CATCH_FLY, 34 * S)
                self._draw_ball(surf, x, y, tilt=t * 30)
            elif t < CATCH_FLY + CATCH_ABSORB:
                self._draw_ball(surf, c[0], c[1], opening=1.0)
            else:
                k = (t - CATCH_FLY - CATCH_ABSORB) / max(1, CATCH_DROP)
                self._draw_ball(surf, c[0] + (rest[0] - c[0]) * k,
                                c[1] + (rest[1] - c[1]) * k)
            return
        if a and a["type"] == "catch_shake":
            tilt = math.sin(a["t"] / a["dur"] * math.pi * 2) * 16
            self._draw_ball(surf, rest[0], rest[1], tilt=tilt)
            return
        if a and a["type"] == "catch_click":
            self._draw_ball(surf, rest[0], rest[1])
            if a["t"] < 10:                          # a small "click" sparkle
                fr = int(BALL_D * (0.6 + a["t"] * 0.12))
                fl = pygame.Surface((fr * 2, fr * 2), pygame.SRCALPHA)
                pygame.draw.circle(fl, (255, 255, 255, max(0, 150 - a["t"] * 16)),
                                   (fr, fr), fr, max(1, S // 2))
                surf.blit(fl, (int(rest[0]) - fr, int(rest[1]) - fr))
            return
        if a and a["type"] == "catch_break":
            self._draw_ball(surf, rest[0], rest[1], opening=a["t"] / a["dur"])
            return
        if self.foe_absorbed:                        # static (between wobbles)
            self._draw_ball(surf, rest[0], rest[1])

    def _draw_battler(self, surf, side, pos) -> None:
        a = self.anim
        scale, alpha = 1.0, 255
        # send-out: ball in flight (hide) then the creature materialises
        if a and a.get("type") == "throw" and a.get("side") == side:
            if a["t"] < THROW_ARC:
                return
            scale = 0.4 + 0.6 * (a["t"] - THROW_ARC) / max(1, a["dur"] - THROW_ARC)
        # catch: the foe shrinks into the ball, or pops back out, or is gone
        if side == P2:
            if a and a.get("type") == "catch_throw":
                t = a["t"]
                if t >= CATCH_FLY + CATCH_ABSORB:
                    return                            # absorbed
                if t >= CATCH_FLY:
                    k = (t - CATCH_FLY) / CATCH_ABSORB
                    scale, alpha = max(0.05, 1 - k), int(255 * (1 - k))
            elif a and a.get("type") == "catch_break":
                k = a["t"] / a["dur"]
                scale, alpha = max(0.05, k), int(255 * k)
            elif self.foe_absorbed:
                return

        # faint progress eases from the active faint animation, then sticks
        prog = self.faint[side]
        if a and a.get("type") == "faint" and a.get("side") == side:
            prog = min(1.0, a["t"] / a["dur"])
        if prog >= 1.0:
            return
        if not self.revealed[side]:
            return
        bp = self.display_mon[side]
        dex = getattr(self.game.data.species(bp.state.species_id), "dex", None)
        img = self.game.assets.battler(bp.state.species_id, bp.name,
                                       dex=dex, back=(side == P1))
        x, y = pos
        if a and a.get("type") == "lunge" and a.get("side") == side:
            amp = math.sin(math.pi * a["t"] / a["dur"]) * LUNGE_AMP
            x += int(amp if side == P1 else -amp)    # toward the opponent
            y += int(-amp if side == P1 else amp)
        if prog > 0:                                 # sink + fade out
            img = img.copy()
            img.fill((255, 255, 255, int(255 * (1 - prog))),
                     special_flags=pygame.BLEND_RGBA_MULT)
            y += int(prog * SPRITE_PX)
        elif self.flash[side] > 0 and (self.flash[side] // 3) % 2 == 1:
            return                                   # blink off this frame
        if scale != 1.0:                             # materialise / absorb
            w = max(1, int(SPRITE_PX * scale))
            img = pygame.transform.scale(img, (w, w))
            x += (SPRITE_PX - w) // 2                 # keep centred
            y += (SPRITE_PX - w)                      # keep feet planted
        if alpha < 255:
            img = img.copy()
            img.fill((255, 255, 255, alpha), special_flags=pygame.BLEND_RGBA_MULT)
        # Level-up glow: blue radial rings that pulse in then out (player only).
        if a and a.get("type") == "levelup" and side == P1:
            progress = a["t"] / max(1, a["dur"])
            glow_alpha = int(200 * math.sin(math.pi * progress))
            if glow_alpha > 0:
                cx = x + SPRITE_PX // 2
                cy = y + SPRITE_PX // 2
                glow_w = SPRITE_PX * 3
                glow = pygame.Surface((glow_w, glow_w), pygame.SRCALPHA)
                gc = glow_w // 2
                for i, r_frac in enumerate((0.65, 0.85, 1.05)):
                    radius = int(SPRITE_PX * r_frac)
                    ring_a = max(0, glow_alpha >> i)   # halve alpha each ring out
                    pygame.draw.circle(glow, (80, 150, 255, ring_a),
                                       (gc, gc), radius, max(1, 3 * S))
                surf.blit(glow, (cx - gc, cy - gc))
        surf.blit(img, (x, y))

    def _draw_info(self, surf, side, rect, *, numbers: bool = False) -> None:
        if not self.revealed[side]:
            return
        bp = self.display_mon[side]
        draw_panel(surf, rect, PANEL_DARK, BOX_BORDER, radius=4 * S)
        font = self.game.assets.font
        FH = font.get_height()
        # Name + level
        surf.blit(font.render(f"{bp.name}", True, (250, 252, 255)),
                  (rect.x + 6 * S, rect.y + 3 * S))
        lv = f"Lv{bp.level}"
        lw = font.size(lv)[0]
        surf.blit(font.render(lv, True, (220, 236, 255)),
                  (rect.right - lw - 5 * S, rect.y + 3 * S))
        # Status badge (between name and Lv)
        if bp.state.status:
            draw_status_badge(surf, font, bp.state.status,
                              rect.x + 6 * S, rect.y + 3 * S + FH + 1 * S)
        # HP bar
        frac = max(0.0, min(1.0, self.disp_hp[side] / bp.max_hp))
        bar = pygame.Rect(rect.x + 6 * S, rect.y + 18 * S,
                          rect.width - 12 * S, 5 * S)
        from .dialog import draw_hp_bar
        draw_hp_bar(surf, bar, frac)
        if numbers:
            hp_txt = f"{max(0, int(round(self.disp_hp[side])))}/{bp.max_hp}"
            surf.blit(font.render(hp_txt, True, (228, 244, 255)),
                      (rect.x + 6 * S, rect.y + 25 * S))
            # EXP bar
            exp_frac = self.disp_exp_frac
            exp_bar = pygame.Rect(rect.x + 6 * S, rect.y + 38 * S,
                                  rect.width - 12 * S, 3 * S)
            pygame.draw.rect(surf, (35, 42, 65), exp_bar, border_radius=S)
            if exp_frac > 0:
                fill = exp_bar.copy()
                fill.width = max(1, int(exp_bar.width * exp_frac))
                pygame.draw.rect(surf, (72, 136, 220), fill, border_radius=S)
