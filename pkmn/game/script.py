"""The event runtime (Phase 8).

Event scripts are lists of command dicts (game/assets/scripts.json, or
built programmatically by trainers and the Python authoring API in
events.py). A script is *compiled* into a flat instruction array with
explicit jumps, then executed by a small VM with an instruction pointer.
This is what lets control flow -- if/else, while loops, label/goto -- work
properly alongside the blocking commands (dialogue, battle, NPC walks,
timed waits) that suspend the VM and resume it when the scene pops.

State model
-----------
* flags          -- booleans (set/clear/if via `flag` conditions)
* vars           -- integers (set_var/add_var/if via `var` conditions)
* self_switches  -- per-event booleans A/B/C/D (the "I already did this"
                    backbone), keyed by the running event's identity

Conditions (used by `if`, `while`, and multi-page event selection) are
dicts: {"flag": n} | {"var": n, "op": ">=", "value": k} |
{"self_switch": "A"} | {"item": id, "qty": k} | {"money": k} |
{"not": c} | {"all": [..]} | {"any": [..]}.

Commands -- leaf: say, heal, give_item, give_money, take_money, set_flag,
clear_flag, set_var, add_var, set_self_switch, clear_self_switch, warp,
move_npc, move_route, face_npc, hide_npc, wait, shop, give_pokemon, pc,
battle, screen.  structured (compiled): if/then/else, if_flag, if_money,
if_var, if_self_switch, while/do, label, goto, choice.

Extension seam: register_command(name, fn) lets a game add its own leaf
commands without forking the engine; fn(runner, payload) -> None|WAIT|DONE.
"""
from __future__ import annotations

import operator

from ..core.pokemon import PokemonState
from .contract import SCRIPT_COMMANDS
from .dialog import DialogScene

WAIT, DONE = "wait", "done"

# ── extension registry ───────────────────────────────────────────────
_COMMANDS: dict = {}            # name -> fn(runner, payload) -> None|WAIT|DONE


def register_command(name: str, fn) -> None:
    """Register a custom leaf command. Games call this at load time to
    extend the runtime without modifying the engine."""
    _COMMANDS[name] = fn


# ── conditions ───────────────────────────────────────────────────────
_CMP = {"==": operator.eq, "!=": operator.ne, "<": operator.lt,
        "<=": operator.le, ">": operator.gt, ">=": operator.ge}


def eval_condition(cond, st, event_key: str = "") -> bool:
    """Evaluate a condition dict against game state. Pure; also used to
    pick the active page of a multi-page event."""
    if not cond:
        return True
    if "flag" in cond:
        return cond["flag"] in st.flags
    if "var" in cond:
        cur = int(st.vars.get(cond["var"], 0))
        return _CMP.get(cond.get("op", "=="), operator.eq)(
            cur, int(cond.get("value", 0)))
    if "self_switch" in cond:
        return f"{event_key}:{cond['self_switch']}" in st.self_switches
    if "item" in cond:
        return st.bag.get(cond["item"], 0) >= int(cond.get("qty", 1))
    if "money" in cond:
        return st.money >= int(cond["money"])
    if "not" in cond:
        return not eval_condition(cond["not"], st, event_key)
    if "all" in cond:
        return all(eval_condition(c, st, event_key) for c in cond["all"])
    if "any" in cond:
        return any(eval_condition(c, st, event_key) for c in cond["any"])
    if "badge" in cond:
        return cond["badge"] in st.badges
    if "badge_count" in cond:
        cur = len(st.badges)
        return _CMP.get(cond.get("op", ">="), operator.ge)(
            cur, int(cond.get("value", 0)))
    if "visited" in cond:
        return cond["visited"] in st.visited_maps
    return False


def resolve_script(defn, st, event_key: str = "") -> list:
    """A script definition is either a flat command list or a multi-page
    event {"pages": [{"when": cond, "do": [...]}, ...]}. Returns the command
    list to run: the *last* page whose condition holds (RMXP page priority),
    or [] if none."""
    if isinstance(defn, dict) and "pages" in defn:
        chosen = []
        for page in defn["pages"]:
            if eval_condition(page.get("when"), st, event_key):
                chosen = page.get("do", [])
        return list(chosen)
    return list(defn or [])


# ── condition extraction for the structured commands ─────────────────
def _cond_of(step):
    if "if" in step:
        return step["if"]
    if "if_flag" in step:
        return {"flag": step["if_flag"]}
    if "if_money" in step:
        return {"money": step["if_money"].get("amount", 0)}
    if "if_var" in step:
        v = step["if_var"]
        return {"var": v["var"], "op": v.get("op", "=="),
                "value": v.get("value", 0)}
    if "if_self_switch" in step:
        return {"self_switch": step["if_self_switch"].get("switch", "A")}
    if "while" in step:
        return step["while"]
    return None


_IF_KEYS = ("if", "if_flag", "if_money", "if_var", "if_self_switch")


def _then_else(step):
    """`then`/`else` live in the payload for if_money/if_var/if_self_switch,
    but top-level for `if`/`if_flag` (matching existing content)."""
    for k in ("if_money", "if_var", "if_self_switch"):
        if k in step:
            p = step[k]
            return p.get("then", []), p.get("else", [])
    return step.get("then", []), step.get("else", [])


# ── compiler: nested command list -> flat instruction array ──────────
def compile_program(steps):
    instrs: list = []          # each: [op, ...]
    labels: dict = {}
    gotos: list = []           # (instr_index, label_name)

    def emit(instr):
        instrs.append(instr)
        return len(instrs) - 1

    def comp(seq):
        for step in seq:
            keys = set(step)
            if keys & set(_IF_KEYS):
                cond = _cond_of(step)
                then_body, else_body = _then_else(step)
                jf = emit(["JFALSE", cond, None])
                comp(then_body)
                jend = emit(["JUMP", None])
                instrs[jf][2] = len(instrs)            # -> else
                comp(else_body)
                instrs[jend][1] = len(instrs)          # -> end
            elif "while" in step:
                top = len(instrs)
                jf = emit(["JFALSE", step["while"], None])
                comp(step.get("do", []))
                emit(["JUMP", top])
                instrs[jf][2] = len(instrs)
            elif "label" in step:
                labels[step["label"]] = len(instrs)
            elif "goto" in step:
                gotos.append((emit(["JUMP", None]), step["goto"]))
            elif "choice" in step:
                c = step["choice"]
                opts = c.get("options", [])
                ch = emit(["CHOICE", c.get("prompt", ""),
                           [o.get("label", "?") for o in opts], None])
                entries, ends = [], []
                for o in opts:
                    entries.append(len(instrs))
                    comp(o.get("then", []))
                    ends.append(emit(["JUMP", None]))
                end = len(instrs)
                for e in ends:
                    instrs[e][1] = end
                instrs[ch][3] = entries
            else:
                emit(["OP", step])

    comp(list(steps))
    for idx, name in gotos:                            # back-patch gotos
        instrs[idx][1] = labels.get(name, len(instrs))
    return instrs


def parse_party(spec, data, rng) -> list:
    """Build a battle party. Two forms are accepted:

    * compact string -- 'species:level@held-item|species:level' (trainers,
      legacy content);
    * rich list -- [{"species", "level", "ivs", "evs", "nature", "ability",
      "moves", "item", "gender"}, ...] for full per-mon control (EVs/IVs/
      nature/ability/moveset/held item), the Tier-3 trainer spec.
    """
    if isinstance(spec, list):
        out = []
        for m in spec:
            mon = PokemonState.generate(
                data, m["species"], int(m.get("level", 5)),
                ivs=m.get("ivs"), evs=m.get("evs"), nature=m.get("nature"),
                ability=m.get("ability"), moves=m.get("moves"),
                gender=m.get("gender"), shiny=m.get("shiny"), rng=rng)
            if m.get("item"):
                mon.held_item = m["item"]
            out.append(mon)
        return out
    out = []
    for part in str(spec).split("|"):
        species, _, rest = part.strip().partition(":")
        level, _, item = rest.partition("@")
        mon = PokemonState.generate(data, species, int(level or 5), rng=rng)
        if item:
            mon.held_item = item
        out.append(mon)
    return out


class ScriptRunner:
    """Compiles a script and runs it. `event_key` identifies the running
    event so self-switches are scoped to it; `parallel` runners never push
    blocking scenes."""

    def __init__(self, game, overworld, steps, event_key: str = "",
                 parallel: bool = False):
        self.game = game
        self.ow = overworld
        self.event_key = event_key
        self.parallel = parallel
        self.instrs = compile_program(steps)
        self.ip = 0
        self.pending_battle: dict | None = None
        self.pending_choice: list | None = None     # entry addresses
        self.wait_frames = 0

    # ── conditions ───────────────────────────────────────────────────
    def eval_cond(self, cond) -> bool:
        return eval_condition(cond, self.game.state, self.event_key)

    def _ss(self, sw: str) -> str:
        return f"{self.event_key}:{sw}"

    # ── resume hook: called after a scene pops / walk ends / wait ends ─
    def resume(self) -> str:
        if self.pending_choice is not None:
            entries, self.pending_choice = self.pending_choice, None
            idx = max(0, min(len(entries) - 1,
                             int(getattr(self.game, "last_choice", 0))))
            self.ip = entries[idx]
            return self.advance()
        if self.pending_battle is not None:
            step, self.pending_battle = self.pending_battle, None
            if self.game.last_battle != "p1":
                return DONE                          # lost/fled: abort
            st = self.game.state
            if step.get("flag"):
                st.flags.add(step["flag"])
            st.money += int(step.get("prize") or 0)
        return self.advance()

    # ── the VM ───────────────────────────────────────────────────────
    def advance(self) -> str:
        budget = 100000                              # runaway-loop guard
        while 0 <= self.ip < len(self.instrs):
            budget -= 1
            if budget <= 0:
                return DONE
            instr = self.instrs[self.ip]
            op = instr[0]
            if op == "JUMP":
                self.ip = instr[1]
                continue
            if op == "JFALSE":
                self.ip = self.ip + 1 if self.eval_cond(instr[1]) else instr[2]
                continue
            if op == "CHOICE":
                if self.parallel:                    # no UI in parallel
                    self.ip = (instr[3] or [self.ip + 1])[0]
                    continue
                from .menus import ChoiceScene
                self.pending_choice = instr[3]
                self.game.push(ChoiceScene(self.game, instr[1], instr[2]))
                return WAIT
            # op == "OP"
            r = self.exec_op(instr[1])
            if r == DONE:
                return DONE
            self.ip += 1
            if r == WAIT:
                return WAIT
        return DONE

    # ── leaf command execution ───────────────────────────────────────
    def exec_op(self, step):
        st = self.game.state
        key = next(iter(step))
        # --- dialogue / flow-blocking ---
        if key == "say":
            if self.parallel:
                return None
            self.game.push(DialogScene(self.game, step["say"].split("|")))
            return WAIT
        if key == "wait":
            self.wait_frames = max(0, int(step["wait"]))
            return WAIT if self.wait_frames and not self.parallel else None
        if key == "warp":
            w = step["warp"]
            st.facing = w.get("facing", st.facing)
            self.ow.load_map(w["map"], (int(w["x"]), int(w["y"])))
            return DONE                              # load_map drops the script
        if key == "move_npc":
            m = step["move_npc"]
            npc = self.ow.find_npc(m["name"])
            if npc:
                self.ow.start_npc_walk(npc, tuple(m["to"]))
                return WAIT
            return None
        if key == "move_route":
            m = step["move_route"]
            npc = self.ow.find_npc(m["name"])
            if npc:
                self.ow.start_npc_route(npc, list(m.get("route", [])))
                return None if self.parallel else WAIT
            return None
        if key == "battle":
            if self.parallel:
                return None
            from .battle_scene import BattleScene
            b = step["battle"]
            party = parse_party(b["party"], st.data, st.rng)
            self.pending_battle = b
            weather = (self.ow.map.props.get("weather")
                       if getattr(self.ow, "map", None) is not None else None)
            self.game.push(BattleScene(self.game, party, wild=False,
                                       trainer_name=b.get("trainer"),
                                       weather=weather))
            return WAIT
        if key == "shop":
            if self.parallel:
                return None
            from .menus import ShopScene
            sh = step["shop"]
            self.game.push(ShopScene(self.game, sh.get("items", []),
                                     sh.get("prices", {})))
            return WAIT
        if key == "pc":
            if self.parallel:
                return None
            from .menus import PCScene
            self.game.push(PCScene(self.game))
            return WAIT
        # --- non-blocking state mutations ---
        if key == "heal":
            st.heal_party()
            self.game.audio.play_sfx("heal")
        elif key == "give_item":
            g = step["give_item"]
            st.bag[g["item"]] = st.bag.get(g["item"], 0) + int(g.get("qty", 1))
        elif key == "give_money":
            st.money += int(step["give_money"])
        elif key == "take_money":
            st.money = max(0, st.money - int(step["take_money"]))
        elif key == "set_flag":
            st.flags.add(step["set_flag"])
        elif key == "clear_flag":
            st.flags.discard(step["clear_flag"])
        elif key == "set_var":
            v = step["set_var"]
            st.vars[v["var"]] = int(v.get("value", 0))
        elif key == "add_var":
            v = step["add_var"]
            st.vars[v["var"]] = int(st.vars.get(v["var"], 0)) + int(v.get("by", 1))
        elif key == "set_self_switch":
            st.self_switches.add(self._ss(step["set_self_switch"]))
        elif key == "clear_self_switch":
            st.self_switches.discard(self._ss(step["clear_self_switch"]))
        elif key == "face_npc":
            f = step["face_npc"]
            npc = self.ow.find_npc(f["name"])
            if npc:
                npc.facing = f["facing"]
        elif key == "hide_npc":
            self.ow.hide_npc(step["hide_npc"])
        elif key == "give_badge":
            st.badges.add(step["give_badge"])
        elif key == "give_pokemon":
            g = step["give_pokemon"]
            mon = PokemonState.generate(
                st.data, g["species"], int(g.get("level", 5)),
                rng=st.rng, moves=g.get("moves"))
            if g.get("item"):
                mon.held_item = g["item"]
            (st.party if len(st.party) < 6 else st.pc).append(mon)
        elif key == "screen":
            return self._screen(step["screen"])
        elif key in _COMMANDS:                        # extension command
            return _COMMANDS[key](self, step[key])
        elif key not in SCRIPT_COMMANDS:
            raise ValueError(f"unknown script command: {key}")
        return None

    def _screen(self, spec):
        """Minimal screen effect: a brief tint/flash overlay then continue.
        (Full tint/shake/picture pipeline is a documented follow-up.)"""
        if self.parallel:
            return None
        self.ow.screen_fx = dict(spec)
        self.wait_frames = int(spec.get("frames", 12))
        return WAIT if self.wait_frames else None
