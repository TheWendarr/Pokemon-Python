"""Python authoring API for the event runtime (Phase 8).

Write events in Python instead of raw JSON. An ``Event`` is a fluent
builder whose ``.build()`` returns the command list the runtime executes,
and the condition helpers build the condition dicts used by ``if_`` /
``while_`` and multi-page events. This is the pure-Python authoring path:
a whole region's logic can be written without touching scripts.json.

    from pkmn.game.events import Event, var, flag, self_switch

    # a "give the starter once" NPC, in Python
    oak = (Event()
        .if_(~self_switch("A"),
             Event()
               .say("Take this POKEMON!")
               .give_pokemon("charmander", level=5)
               .set_self_switch("A"),
             Event().say("How is it doing?"))
        .build())

    # a variable-driven gym puzzle
    gym = (Event()
        .while_(var("switches") < 3,
                Event().say("Step on a switch.").add_var("switches", 1))
        .set_flag("gym_solved")
        .build())

Multi-page events use ``pages``:

    from pkmn.game.events import Event, page, self_switch
    rival = [page(~self_switch("A"), Event().say("Let's battle!")...),
             page(self_switch("A"), Event().say("Good luck!"))]
    # -> {"pages": rival}  (or use Event.pages([...]))
"""
from __future__ import annotations


# ── conditions ───────────────────────────────────────────────────────
class Cond:
    """A condition expression. Combine with & (all), | (any), ~ (not)."""
    def __init__(self, d: dict):
        self.d = d

    def __and__(self, other: "Cond") -> "Cond":
        return Cond({"all": [self.d, _cd(other)]})

    def __or__(self, other: "Cond") -> "Cond":
        return Cond({"any": [self.d, _cd(other)]})

    def __invert__(self) -> "Cond":
        return Cond({"not": self.d})


def _cd(c):
    return c.d if isinstance(c, Cond) else (c or {})


class _Var:
    def __init__(self, name: str):
        self.name = name

    def _c(self, op: str, v) -> Cond:
        return Cond({"var": self.name, "op": op, "value": int(v)})

    def __eq__(self, v): return self._c("==", v)
    def __ne__(self, v): return self._c("!=", v)
    def __lt__(self, v): return self._c("<", v)
    def __le__(self, v): return self._c("<=", v)
    def __gt__(self, v): return self._c(">", v)
    def __ge__(self, v): return self._c(">=", v)
    __hash__ = None


def var(name: str) -> _Var:
    return _Var(name)


def flag(name: str) -> Cond:
    return Cond({"flag": name})


def self_switch(sw: str = "A") -> Cond:
    return Cond({"self_switch": sw})


def item(item_id: str, qty: int = 1) -> Cond:
    return Cond({"item": item_id, "qty": qty})


def money(amount: int) -> Cond:
    return Cond({"money": amount})


def page(when, do: "Event"):
    """One page of a multi-page event: active when `when` holds."""
    return {"when": _cd(when), "do": do.build() if isinstance(do, Event) else list(do)}


# ── the event builder ────────────────────────────────────────────────
class Event:
    def __init__(self):
        self.steps: list = []

    def build(self) -> list:
        return list(self.steps)

    def _add(self, step):
        self.steps.append(step)
        return self

    # dialogue / flow
    def say(self, text): return self._add({"say": text})
    def wait(self, frames): return self._add({"wait": int(frames)})
    def pc(self): return self._add({"pc": True})
    def shop(self, items, prices=None):
        return self._add({"shop": {"items": list(items), "prices": prices or {}}})

    def choice(self, prompt, options):
        """options: list of (label, Event) pairs."""
        return self._add({"choice": {"prompt": prompt, "options": [
            {"label": lbl, "then": ev.build() if isinstance(ev, Event) else list(ev)}
            for lbl, ev in options]}})

    # flags / money / items
    def heal(self): return self._add({"heal": True})
    def set_flag(self, n): return self._add({"set_flag": n})
    def clear_flag(self, n): return self._add({"clear_flag": n})
    def give_item(self, item_id, qty=1):
        return self._add({"give_item": {"item": item_id, "qty": qty}})
    def give_money(self, n): return self._add({"give_money": int(n)})
    def take_money(self, n): return self._add({"take_money": int(n)})
    def give_pokemon(self, species, level=5, moves=None, held=None):
        g = {"species": species, "level": level}
        if moves: g["moves"] = moves
        if held: g["item"] = held
        return self._add({"give_pokemon": g})

    # variables / self-switches
    def set_var(self, name, value): return self._add({"set_var": {"var": name, "value": int(value)}})
    def add_var(self, name, by=1): return self._add({"add_var": {"var": name, "by": int(by)}})
    def set_self_switch(self, sw="A"): return self._add({"set_self_switch": sw})
    def clear_self_switch(self, sw="A"): return self._add({"clear_self_switch": sw})

    # world / npcs
    def warp(self, map_id, x, y, facing="down"):
        return self._add({"warp": {"map": map_id, "x": x, "y": y, "facing": facing}})
    def move_npc(self, name, to): return self._add({"move_npc": {"name": name, "to": list(to)}})
    def move_route(self, name, route):
        return self._add({"move_route": {"name": name, "route": list(route)}})
    def face_npc(self, name, facing): return self._add({"face_npc": {"name": name, "facing": facing}})
    def hide_npc(self, name): return self._add({"hide_npc": name})
    def battle(self, party, trainer=None, prize=0, flag=None):
        b = {"party": party, "prize": prize}
        if trainer: b["trainer"] = trainer
        if flag: b["flag"] = flag
        return self._add({"battle": b})
    def screen(self, **spec): return self._add({"screen": spec})

    # control flow
    def if_(self, cond, then: "Event", else_: "Event | None" = None):
        step = {"if": _cd(cond),
                "then": then.build() if isinstance(then, Event) else list(then)}
        if else_ is not None:
            step["else"] = else_.build() if isinstance(else_, Event) else list(else_)
        return self._add(step)

    def while_(self, cond, body: "Event"):
        return self._add({"while": _cd(cond),
                          "do": body.build() if isinstance(body, Event) else list(body)})

    def label(self, name): return self._add({"label": name})
    def goto(self, name): return self._add({"goto": name})

    # multi-page wrapper
    @staticmethod
    def pages(pages: list) -> dict:
        return {"pages": list(pages)}
