"""The content contract is the single source of truth shared by the
engine and the linter; these tests pin that they cannot drift and that
the version gate and connection geometry behave."""
import os
import types

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pytest

from pkmn.game import contract


def test_compatible_accepts_le_and_rejects_newer_or_garbage():
    assert contract.compatible(1)          # legacy integer format
    assert contract.compatible("1.0")      # semver — same major as engine
    assert contract.compatible("1.9")      # same major, higher minor — OK
    assert contract.compatible(contract.ENGINE_VERSION)
    assert not contract.compatible("2.0")  # future major — not supported
    assert not contract.compatible("nope")
    assert not contract.compatible(None)


def test_linter_and_engine_share_the_same_command_set():
    # both sides import from contract, so the validator and the runtime
    # are the same object and can never disagree about what's valid
    from pkmn.cli import lint
    from pkmn.game import script
    assert lint.SCRIPT_COMMANDS is contract.SCRIPT_COMMANDS
    assert script.SCRIPT_COMMANDS is contract.SCRIPT_COMMANDS


def test_script_runner_raises_on_unknown_command():
    pytest.importorskip("pygame")
    from pkmn.game.script import ScriptRunner
    g = types.SimpleNamespace(state=types.SimpleNamespace(flags=set()))
    runner = ScriptRunner(g, overworld=None, steps=[{"frobnicate": 1}])
    with pytest.raises(ValueError):
        runner.advance()


def test_rebase_north_round_trips():
    # A is 10x9; its north neighbour B is 20x18 at offset -5. A tile one
    # row above A's top (y=-1) lands on B's bottom row, shifted right by 5.
    assert contract.rebase("north", 3, -1, 10, 9, 20, 18, -5) == (8, 17)
    # and east: offset shifts the y axis, x wraps to the neighbour's left
    assert contract.rebase("east", 10, 4, 10, 9, 12, 9, 2) == (0, 2)
