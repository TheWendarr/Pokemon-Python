# Phase Progress — acceptance criteria and current status

This document maps the phased release plan to concrete acceptance tests
and short-term next steps for each phase. See also: `docs/ROADMAP.md`
(project history) and `docs/Features.md` (feature-level status).

**v1.0 scope:** a releasable product — installable, title/new-game shell,
recommended example region, passing test suite, clear packaging. Essentials
parity is the 1.x program. **Current gate: Phase A is largely satisfied;
Phase B1 (ability coverage) is the remaining v1.0 blocker.**

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

Phase B — Battle credibility
- Acceptance
  - `pkmn.cli.audit` shows targeted ability/item coverage improvements
  - Effect-skip rate reduced; new handlers unit-tested
- Verify: `python -m pkmn.cli.audit` / `python -m pkmn.cli.coverage`
- Current status / next actions
  - B1 (v1.0 gate): ability coverage is partial (~50–52% implemented); add
    handlers to reach ~80 implemented handlers for used abilities.
    (`pkmn/battle/passives.py`, `IMPLEMENTED_ABILITIES` registry)
  - B2 (fast-follow): implement top skipped move handlers (destiny-bond,
    perish-song, yawn, transform, snatch, etc.).
  - B3 (fast-follow): broaden held-item effect coverage; infrastructure exists
    but many item effects remain.

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
