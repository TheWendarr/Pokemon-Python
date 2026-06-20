"""A tiny event-script interpreter.

Scripts are JSON lists of command dicts (game/assets/scripts.json, or
built programmatically for trainers). The runner executes commands
until one needs a scene (dialogue, battle, NPC walk) and then yields;
the overworld resumes it when the scene pops. Conditionals splice their
branch into the queue, so nesting works naturally.

Commands:
  {"say": "line|next page"}                    -> dialogue box
  {"heal": true}                               -> full party heal
  {"give_item": {"item": id, "qty": n}}
  {"give_money": n}
  {"set_flag": name} / {"clear_flag": name}
  {"if_flag": name, "then": [...], "else": [...]}
  {"warp": {"map": id, "x": n, "y": n, "facing": dir}}
  {"move_npc": {"name": display, "to": [x, y]}} -> walked, not teleported
  {"face_npc": {"name": display, "facing": dir}}
  {"hide_npc": display}
  {"battle": {"trainer": label, "party": "species:lv|species:lv",
              "prize": n, "flag": name}}       -> steps after run on win only
"""
from __future__ import annotations

from ..core.pokemon import PokemonState
from .contract import SCRIPT_COMMANDS
from .dialog import DialogScene

WAIT, DONE = "wait", "done"


def parse_party(spec: str, data, rng) -> list:
    """'species:level@held-item|species:level' -> PokemonState list."""
    out = []
    for part in spec.split("|"):
        species, _, rest = part.strip().partition(":")
        level, _, item = rest.partition("@")
        mon = PokemonState.generate(data, species, int(level or 5), rng=rng)
        if item:
            mon.held_item = item
        out.append(mon)
    return out


class ScriptRunner:
    def __init__(self, game, overworld, steps):
        self.game = game
        self.ow = overworld
        self.queue = list(steps)
        self.pending_battle: dict | None = None
        self.pending_choice: list | None = None

    # ── resume hook: called by the overworld after a scene pops ──────
    def resume(self) -> str:
        if self.pending_choice is not None:
            options, self.pending_choice = self.pending_choice, None
            idx = max(0, min(len(options) - 1,
                             int(getattr(self.game, "last_choice", 0))))
            self.queue = list(options[idx].get("then", [])) + self.queue
            return self.advance()
        if self.pending_battle is not None:
            step, self.pending_battle = self.pending_battle, None
            if self.game.last_battle != "p1":
                return DONE  # lost/fled: abort the rest of the script
            st = self.game.state
            if step.get("flag"):
                st.flags.add(step["flag"])
            st.money += int(step.get("prize") or 0)
        return self.advance()

    def advance(self) -> str:
        st = self.game.state
        while self.queue:
            step = self.queue.pop(0)
            if "if_flag" in step:
                branch = step.get("then" if step["if_flag"] in st.flags
                                  else "else", [])
                self.queue = list(branch) + self.queue
            elif "say" in step:
                self.game.push(DialogScene(self.game, step["say"].split("|")))
                return WAIT
            elif "heal" in step:
                st.heal_party()
            elif "give_item" in step:
                g = step["give_item"]
                st.bag[g["item"]] = st.bag.get(g["item"], 0) + int(g.get("qty", 1))
            elif "give_money" in step:
                st.money += int(step["give_money"])
            elif "set_flag" in step:
                st.flags.add(step["set_flag"])
            elif "clear_flag" in step:
                st.flags.discard(step["clear_flag"])
            elif "warp" in step:
                w = step["warp"]
                st.facing = w.get("facing", st.facing)
                self.ow.load_map(w["map"], (int(w["x"]), int(w["y"])))
                return DONE  # load_map drops the running script
            elif "move_npc" in step:
                m = step["move_npc"]
                npc = self.ow.find_npc(m["name"])
                if npc:
                    self.ow.start_npc_walk(npc, tuple(m["to"]))
                    return WAIT
            elif "face_npc" in step:
                f = step["face_npc"]
                npc = self.ow.find_npc(f["name"])
                if npc:
                    npc.facing = f["facing"]
            elif "hide_npc" in step:
                self.ow.hide_npc(step["hide_npc"])
            elif "choice" in step:
                from .menus import ChoiceScene
                c = step["choice"]
                self.pending_choice = c.get("options", [])
                self.game.push(ChoiceScene(
                    self.game, c.get("prompt", ""),
                    [o.get("label", "?") for o in self.pending_choice]))
                return WAIT
            elif "shop" in step:
                from .menus import ShopScene
                sh = step["shop"]
                self.game.push(ShopScene(self.game, sh.get("items", []),
                                         sh.get("prices", {})))
                return WAIT
            elif "give_pokemon" in step:
                g = step["give_pokemon"]
                mon = PokemonState.generate(
                    st.data, g["species"], int(g.get("level", 5)),
                    rng=st.rng, moves=g.get("moves"))
                if g.get("item"):
                    mon.held_item = g["item"]
                (st.party if len(st.party) < 6 else st.pc).append(mon)
            elif "take_money" in step:
                st.money = max(0, st.money - int(step["take_money"]))
            elif "if_money" in step:
                m = step["if_money"]
                branch = m.get("then" if st.money >= int(m.get("amount", 0))
                               else "else", [])
                self.queue = list(branch) + self.queue
            elif "pc" in step:
                from .menus import PCScene
                self.game.push(PCScene(self.game))
                return WAIT
            elif "battle" in step:
                from .battle_scene import BattleScene
                b = step["battle"]
                party = parse_party(b["party"], st.data, st.rng)
                self.pending_battle = b
                weather = None
                if getattr(self.ow, "map", None) is not None:
                    weather = self.ow.map.props.get("weather")
                self.game.push(BattleScene(self.game, party, wild=False,
                                           trainer_name=b.get("trainer"),
                                           weather=weather))
                return WAIT
            elif not set(step) & SCRIPT_COMMANDS:
                raise ValueError(f"unknown script command: {sorted(step)}")
        return DONE
