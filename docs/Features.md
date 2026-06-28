# Features — status and inclusion for v1.0

This document summarizes features the project maintains, their current
status for the v1.0 program, and whether they are complete, partially
implemented, or planned for post-1.0. See also: `docs/ROADMAP.md`
(project history and phased milestones) and `docs/PhaseProgress.md`
(per-task acceptance criteria and current status).


Complete (ready / tested)
- Battle core (Gen5 stat math, statuses, items, turn order).
- PokeAPI dataset (Gen1–5 catalog present; datagen pipeline in `pkmn/datagen`).
- Event VM (`ScriptRunner`, variables, self-switches, multi-page events,
  autorun/parallel, `register_command`, move routes) — covered by
  `tests/test_events.py` and `tests/test_eventlab.py`.
- Layered maps and partial autotile support: multiple tile layers, per-tile
  draw priority (`over`), directional/partial passability flags, and basic
  autotile interior animation (the `tools/rmxp2kanto.py` converter emits
  autotile frames and `tests/test_layers.py` locks behavior).
- Content-folder authoring format + linter (`pkmn.cli.lint`).
- Multi-method encounters (land/surf/fishing/old_rod/good_rod/super_rod,
  rock_smash, headbutt, cave) and the converter emits PBS methods.
- Badges, HM gating for several HMs, `BadgesScene`, `visited_maps`, and
  `FlyScene` (Town Map) — implemented and covered by `tests/test_phase_d.py`.
- TitleScene and the new-game / continue shell (`pkmn/game/title.py`,
  `tests/test_title.py`).
- EV yield data present for 649 species and wired through battle/exp
  (`pkmn/datagen/fetch.py`, `tests/test_ev_yield.py`).


Partially implemented (close / cosmetic / blocked by data or assets)
- Autotile full 47-piece edge-blending — cosmetic deferred.
- Panorama & fog layers — cosmetic, not required for importer.
- Abilities coverage — partial; audit shows ~50–52% implemented; B1 targets
  raising this.
- Held-item effect breadth — infrastructure and held-item UI exist
  (`HeldItemPicker`, trainer held items), but many item effects remain to
  be implemented and tested.
- Animated battle sprites / per-move animations — presentation assets and
  pipeline required.
- Breeding, move relearner/tutor, reusable TMs, nicknaming UI — long tail.
- Bike & some HM effects (Strength boulder persistence, Dive map pairing).
- Multi-active battles (doubles/triples/rotation) — XL architectural work.


Planned / Post-1.0 (1.x parity program)
- Full RMXP/PBS importer promotion (tileset terrain mapping, `.rxdata` maps/events).
- Full parity items: breeding, PC multi-box, seasons, overworld weather,
  field-move polish, full title/config UI improvements.

Notes
- Use `pkmn/game/contract.py` as the authoritative list of flags/settings
  to expand. Follow "if it lints, it runs" — add contract entries first.
