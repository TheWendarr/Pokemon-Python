"""Cheat console overlay. Opened by ~ when --cheat is active.

Commands
--------
  party <n> level <value>
  party <n> iv <stat|all> <value>
  party <n> ev <stat|all> <value>
  party <n> moves <move1> [move2] [move3] [move4]

Stat names accepted: hp, atk/attack, def/defense, spa/spatk,
                     spd/spdef, spe/speed  (or full snake_case).
Party slot n is 1-based.
"""
from __future__ import annotations

import pygame

from ..core.pokemon import MoveSlot
from ..data.models import STAT_KEYS
from .config import LOGICAL_H, LOGICAL_W, SCALE as S
from .scene import Scene

# ── appearance ────────────────────────────────────────────────────────
_BG        = (10, 14, 10, 210)   # dark green-black, semi-transparent
_BORDER    = (0, 200, 60)
_TEXT_OUT  = (160, 255, 140)     # output lines
_TEXT_IN   = (220, 255, 200)     # input line
_TEXT_ERR  = (255, 100, 80)      # error output
_TEXT_OK   = (100, 230, 255)     # success output
_PROMPT    = "> "
_MAX_HIST  = 18                  # output lines kept
_BOX_H     = LOGICAL_H // 2      # console takes bottom half

# ── stat name normalisation ───────────────────────────────────────────
_STAT_NORM: dict[str, str] = {
    "hp": "hp", "h": "hp",
    "attack": "attack",         "atk": "attack",     "a": "attack",
    "defense": "defense",       "def": "defense",    "d": "defense",
    "special_attack": "special_attack",
    "special-attack": "special_attack",
    "spatk": "special_attack",  "spa": "special_attack",
    "special_defense": "special_defense",
    "special-defense": "special_defense",
    "spdef": "special_defense",  "spd": "special_defense",
    "speed": "speed",           "spe": "speed",      "s": "speed",
}


class CheatConsoleScene(Scene):
    """Terminal-style dev console pushed onto the scene stack."""
    translucent = True

    def __init__(self, game):
        super().__init__(game)
        self._font = pygame.font.SysFont("monospace", 10 * S // 2)
        self._buf = ""           # current input buffer
        self._history: list[tuple[str, str]] = []  # (colour_key, text)
        self._cursor_tick = 0
        self._out("ok", "Cheat console open. Type 'help' for commands.")

    # ── input ─────────────────────────────────────────────────────────
    def handle(self, inp) -> None:
        self._cursor_tick += 1
        for key, uni in inp.key_downs:
            if key == pygame.K_ESCAPE or key == pygame.K_BACKQUOTE:
                self.game.pop()
                return
            elif key == pygame.K_RETURN or key == pygame.K_KP_ENTER:
                self._submit()
            elif key == pygame.K_BACKSPACE:
                self._buf = self._buf[:-1]
            elif uni and uni.isprintable():
                self._buf += uni

    # ── draw ──────────────────────────────────────────────────────────
    def draw(self, surf) -> None:
        # Semi-transparent background panel
        panel = pygame.Surface((LOGICAL_W, _BOX_H), pygame.SRCALPHA)
        panel.fill(_BG)
        surf.blit(panel, (0, LOGICAL_H - _BOX_H))

        pygame.draw.rect(surf, _BORDER,
                         pygame.Rect(0, LOGICAL_H - _BOX_H, LOGICAL_W, _BOX_H),
                         width=S)

        fh = self._font.get_height() + S
        pad_x = 4 * S
        pad_y = 4 * S

        # Output history (newest at bottom, above input line)
        avail_lines = (_BOX_H - pad_y * 2 - fh * 2) // fh
        hist = self._history[-avail_lines:]
        for i, (col_key, text) in enumerate(hist):
            colour = {"ok": _TEXT_OK, "err": _TEXT_ERR}.get(col_key, _TEXT_OUT)
            y = LOGICAL_H - _BOX_H + pad_y + i * fh
            surf.blit(self._font.render(text, True, colour), (pad_x, y))

        # Divider above input
        div_y = LOGICAL_H - fh * 2 - pad_y
        pygame.draw.line(surf, _BORDER, (pad_x, div_y), (LOGICAL_W - pad_x, div_y), S)

        # Input line with blinking cursor
        cursor = "█" if (self._cursor_tick // 30) % 2 == 0 else " "
        line = _PROMPT + self._buf + cursor
        surf.blit(self._font.render(line, True, _TEXT_IN),
                  (pad_x, LOGICAL_H - fh - pad_y))

    # ── command execution ─────────────────────────────────────────────
    def _submit(self) -> None:
        cmd = self._buf.strip()
        self._buf = ""
        if not cmd:
            return
        self._out("in", _PROMPT + cmd)
        result = self._execute(cmd)
        if result:
            self._out("out", result)

    def _out(self, tag: str, text: str) -> None:
        for line in text.splitlines():
            self._history.append((tag, line))
        if len(self._history) > _MAX_HIST:
            self._history = self._history[-_MAX_HIST:]

    def _execute(self, cmd: str) -> str:
        parts = cmd.strip().split()
        if not parts:
            return ""
        verb = parts[0].lower()

        if verb == "help":
            return (
                "party <n> level <val>\n"
                "party <n> iv <stat|all> <val>   (0-31)\n"
                "party <n> ev <stat|all> <val>   (0-252)\n"
                "party <n> moves <m1> [m2] [m3] [m4]\n"
                "Stats: hp atk def spa spd spe"
            )

        if verb == "party":
            if len(parts) < 3:
                return self._err("usage: party <slot> <subcommand> [args]")
            try:
                slot = int(parts[1]) - 1
            except ValueError:
                return self._err(f"bad slot: {parts[1]!r}")
            party = self.game.state.party
            if not (0 <= slot < len(party)):
                return self._err(
                    f"slot {slot + 1} out of range "
                    f"(party has {len(party)} member(s))")
            ps = party[slot]
            return self._party_cmd(ps, parts[2].lower(), parts[3:])

        return self._err(f"unknown command: {verb!r}  (try 'help')")

    def _err(self, msg: str) -> str:
        self._history.append(("err", msg))
        return ""

    def _ok(self, msg: str) -> str:
        self._history.append(("ok", msg))
        return ""

    def _party_cmd(self, ps, sub: str, args: list[str]) -> str:
        if sub == "level":
            if not args:
                return f"{ps.name} is level {ps.level}."
            try:
                n = int(args[0])
            except ValueError:
                return self._err(f"bad value: {args[0]!r}")
            if not (1 <= n <= 100):
                return self._err("level must be 1-100")
            from ..core.experience import exp_total
            ps.level = n
            ps.exp = exp_total(ps.species.growth_rate, n)
            ps.bind(self.game.data)
            ps.current_hp = min(ps.current_hp, ps.max_hp)
            return self._ok(f"{ps.name} → level {n}  (stats recalculated)")

        if sub in ("iv", "ivs"):
            if len(args) < 2:
                return self._err("usage: party <n> iv <stat|all> <0-31>")
            stat_arg, val_str = args[0].lower(), args[1]
            try:
                val = int(val_str)
            except ValueError:
                return self._err(f"bad value: {val_str!r}")
            if not (0 <= val <= 31):
                return self._err("IV must be 0-31")
            if stat_arg == "all":
                for s in STAT_KEYS:
                    ps.ivs[s] = val
                ps.bind(self.game.data)
                ps.current_hp = min(ps.current_hp, ps.max_hp)
                return self._ok(f"{ps.name} all IVs → {val}")
            s = _STAT_NORM.get(stat_arg)
            if s is None:
                return self._err(f"unknown stat: {stat_arg!r}")
            ps.ivs[s] = val
            ps.bind(self.game.data)
            ps.current_hp = min(ps.current_hp, ps.max_hp)
            return self._ok(f"{ps.name} {s} IV → {val}")

        if sub in ("ev", "evs"):
            if len(args) < 2:
                return self._err("usage: party <n> ev <stat|all> <0-252>")
            stat_arg, val_str = args[0].lower(), args[1]
            try:
                val = int(val_str)
            except ValueError:
                return self._err(f"bad value: {val_str!r}")
            if not (0 <= val <= 252):
                return self._err("EV must be 0-252")
            if stat_arg == "all":
                for s in STAT_KEYS:
                    ps.evs[s] = val
                ps.bind(self.game.data)
                ps.current_hp = min(ps.current_hp, ps.max_hp)
                return self._ok(f"{ps.name} all EVs → {val}")
            s = _STAT_NORM.get(stat_arg)
            if s is None:
                return self._err(f"unknown stat: {stat_arg!r}")
            ps.evs[s] = val
            ps.bind(self.game.data)
            ps.current_hp = min(ps.current_hp, ps.max_hp)
            return self._ok(f"{ps.name} {s} EV → {val}")

        if sub == "moves":
            if not args:
                return self._err(
                    "usage: party <n> moves <move1> [move2] [move3] [move4]")
            slots = []
            unknown = []
            for raw in args[:4]:
                mid = raw.lower().replace("_", "-")
                if self.game.data.has_move(mid):
                    mv = self.game.data.move(mid)
                    slots.append(MoveSlot(mv.id, mv.pp, mv.pp))
                else:
                    unknown.append(raw)
            if unknown:
                return self._err(f"unknown move(s): {', '.join(unknown)}")
            if not slots:
                return self._err("no valid moves given")
            ps.moves = slots
            names = [s.move_id for s in slots]
            return self._ok(f"{ps.name} moves → {', '.join(names)}")

        return self._err(
            f"unknown subcommand: {sub!r}\n"
            "  subcommands: level  iv  ev  moves")
