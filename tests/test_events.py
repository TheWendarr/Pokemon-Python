"""Phase 8 -- the event runtime: variables, self-switches, control flow
(if/else, while, goto/label), multi-page events, the extension seam, and
the Python authoring API. These exercise the VM directly with a light
state stub (no scenes), so they need no dataset."""
import types

from pkmn.game.events import Event, flag, self_switch, var
from pkmn.game.script import (ScriptRunner, eval_condition, register_command,
                              resolve_script, DONE)


def _state():
    return types.SimpleNamespace(flags=set(), vars={}, self_switches=set(),
                                 bag={}, money=0)


def _game(st=None):
    return types.SimpleNamespace(state=st or _state(),
                                 last_choice=0, last_battle="p1")


def _run(steps, event_key="ev", st=None):
    g = _game(st)
    r = ScriptRunner(g, None, steps, event_key=event_key)
    assert r.advance() == DONE
    return g.state


# ── conditions ───────────────────────────────────────────────────────
def test_eval_condition_all_forms():
    st = _state()
    st.flags.add("met"); st.vars["x"] = 5; st.money = 100
    st.self_switches.add("ev:A"); st.bag["potion"] = 2
    assert eval_condition({"flag": "met"}, st)
    assert not eval_condition({"flag": "nope"}, st)
    assert eval_condition({"var": "x", "op": ">=", "value": 5}, st)
    assert not eval_condition({"var": "x", "op": ">", "value": 5}, st)
    assert eval_condition({"self_switch": "A"}, st, "ev")
    assert not eval_condition({"self_switch": "A"}, st, "other")
    assert eval_condition({"item": "potion", "qty": 2}, st)
    assert eval_condition({"money": 100}, st)
    assert eval_condition({"not": {"flag": "nope"}}, st)
    assert eval_condition({"all": [{"flag": "met"}, {"money": 50}]}, st)
    assert eval_condition({"any": [{"flag": "nope"}, {"money": 50}]}, st)


# ── variables + conditional branching ────────────────────────────────
def test_variables_and_if_else():
    st = _run([
        {"set_var": {"var": "n", "value": 2}},
        {"add_var": {"var": "n", "by": 3}},
        {"if_var": {"var": "n", "op": "==", "value": 5,
                    "then": [{"set_flag": "ok"}],
                    "else": [{"set_flag": "bad"}]}},
        {"if": {"flag": "ok"}, "then": [{"set_flag": "also"}]},
    ])
    assert st.vars["n"] == 5
    assert "ok" in st.flags and "bad" not in st.flags and "also" in st.flags


# ── self-switches are event-scoped ───────────────────────────────────
def test_self_switch_scoping():
    st = _run([{"set_self_switch": "A"},
               {"if_self_switch": {"switch": "A",
                                   "then": [{"set_flag": "did_a"}]}}],
              event_key="npc1")
    assert "npc1:A" in st.self_switches and "did_a" in st.flags
    # the same switch under a different event key is independent
    assert not eval_condition({"self_switch": "A"}, st, "npc2")


# ── loops + goto/label ───────────────────────────────────────────────
def test_while_loop_counts():
    st = _run([{"set_var": {"var": "i", "value": 0}},
               {"while": {"var": "i", "op": "<", "value": 5},
                "do": [{"add_var": {"var": "i", "by": 1}}]}])
    assert st.vars["i"] == 5


def test_goto_skips_steps():
    st = _run([{"goto": "skip"},
               {"set_flag": "should_not"},
               {"label": "skip"},
               {"set_flag": "reached"}])
    assert "reached" in st.flags and "should_not" not in st.flags


# ── multi-page events ────────────────────────────────────────────────
def test_resolve_script_pages_picks_last_active():
    st = _state()
    defn = {"pages": [
        {"when": None, "do": [{"say": "page0"}]},
        {"when": {"flag": "advanced"}, "do": [{"say": "page1"}]},
    ]}
    assert resolve_script(defn, st) == [{"say": "page0"}]
    st.flags.add("advanced")
    assert resolve_script(defn, st) == [{"say": "page1"}]


# ── extension seam ───────────────────────────────────────────────────
def test_register_custom_command():
    register_command("bump_score", lambda r, payload:
                     r.game.state.vars.__setitem__(
                         "score", r.game.state.vars.get("score", 0) + int(payload)))
    st = _run([{"bump_score": 10}, {"bump_score": 5}])
    assert st.vars["score"] == 15


# ── Python authoring API ─────────────────────────────────────────────
def test_python_api_builds_and_runs():
    prog = (Event()
            .set_var("s", 0)
            .while_(var("s") < 3, Event().add_var("s", 1))
            .if_(var("s") >= 3, Event().set_flag("solved"),
                 Event().set_flag("unsolved"))
            .build())
    st = _run(prog)
    assert st.vars["s"] == 3 and "solved" in st.flags


def test_python_api_self_switch_once_pattern():
    prog = (Event()
            .if_(~self_switch("A"),
                 Event().set_flag("gave").set_self_switch("A"),
                 Event().set_flag("already"))
            .build())
    st1 = _run(prog, event_key="oak")
    assert "gave" in st1.flags and "oak:A" in st1.self_switches
    # run again with the switch already set -> else branch
    st2 = _run(prog, event_key="oak", st=st1)
    assert "already" in st2.flags
