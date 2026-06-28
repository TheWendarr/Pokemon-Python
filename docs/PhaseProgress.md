# Phase Progress — acceptance criteria and current status

This document maps the phased release plan to concrete acceptance tests
and short-term next steps for each phase. See also: `docs/ROADMAP.md`
(project history) and `docs/Features.md` (feature-level status).

**v1.0 scope:** a releasable product — installable, title/new-game shell,
recommended example region, passing test suite, clear packaging. Essentials
parity is the 1.x program. **Phase A is satisfied; Phase B1 and B2 are
complete (ability 87%, move 100%). Remaining v1.0 work: B3 (held items) and
packaging smoke-run.**

Phase A — Release hardening (v1.0 gate)
- Acceptance
  - Test suite and core checks green
  - All example regions lint 0/0
  - Headless title → new-game → save → continue verified
- Current status / next actions
  - A1 TitleScene: IMPLEMENTED (`pkmn/game/title.py`, `tests/test_title.py`).
  - A2 `examples/kanto_frlg`: COMPLETE (converter emits tiles/flags; examples and
    tests exercise `examples/kanto_frlg`; CHANGELOG notes warnings resolved).
  - A3 EV-yield: IMPLEMENTED (`pkmn/datagen/fetch.py`, `game/data/species/*.json`,
    `tests/test_ev_yield.py`).
  - A4 Contract validation: IMPLEMENTED (`pkmn/game/contract.py` includes
    `FEATURES` and `SETTINGS`).
  - A5 CI smoke: EXISTING test present (`tests/test_examples_boot.py`).
  - A6 Packaging: README, `CHANGELOG.md`, and entry points exist; recommend
    one final packaging smoke-run before tag.

Notes: Phase A acceptance criteria are largely satisfied by the current
codebase; the repository contains tests and implementations for the
title shell, EV-yield, badges/Fly/Town Map, event runtime, layered maps,
and the example regions. The remaining gating work for v1.0 is Phase B1
(ability coverage) per the release sequencing.

Phase B — Battle credibility  ✅ B1 + B2 DONE
- Acceptance
  - `pkmn.cli.audit` shows targeted ability/item coverage improvements
  - Effect-skip rate reduced; new handlers unit-tested
- Verify: `python -m pkmn.cli.audit` / `python -m pkmn.cli.coverage`
- Current status / next actions
  - B1 (v1.0 gate): DONE. Ability coverage reached 143/164 (87%) in
    `pkmn/battle/passives.py`. Exceeds the 80% target. Remaining 21 are
    doubles-only, cosmetic, or unreachable in singles.
  - B2 (fast-follow): DONE. Move coverage is 559/559 (100%); EFFECT_SKIPPED
    rate is 0%. Implemented Substitute, Wish, Lunar Dance, Trick Room,
    Gravity, Magic Room, Magic Coat, Disable, Sleep Talk, Skill Swap,
    Heart Swap, Conversions, Mirror Move, Assist, Sketch, Recycle, and more.
    Field infrastructure added: `trick_room`, `gravity_turns`, `magic_room`,
    `substitute_hp`, `type_override`, `foresight_active`, `wish_turns`, etc.
  - B3 (fast-follow): held-item effect breadth remains partial; infrastructure
    and held-item UI exist but many item effects unimplemented.

Phase C — Multi-active battles (XL)
- Acceptance
  - Pure engine resolves a double battle under tests; single-active tests unchanged
- Verify: `pytest tests/test_doubles.py -q`
- Current status / next actions
  - `tests/test_doubles.py` exists with fixture scaffolding; engine not yet wired.
  - Design active-slot list, make `_do_move` parameterized for target(s).
  - Implement spread move iteration and ally/redirection mechanics.
  - Order all actors, then add UI/AI support in `battle_scene.py`.

Phase D — Importer & parity long tail
- Acceptance
  - A clean Essentials project imports and plays without hand edits
- Verify: `python tools/rmxp2kanto.py --check examples/kanto_frlg`
- Current status / next actions
  - Promote `tools/rmxp2kanto.py` into an importer with `.rxdata` map/event parsing.
  - Add PBS ingestion and ID-normalization layer in `datagen`.
  - Long tail: breeding, move relearner, reusable TMs, nicknaming UI, PC multi-box.
