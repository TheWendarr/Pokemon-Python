# Roadmap

## Vision

**Reliably reproduce the full functionality of RPG Maker XP + Pokémon
Essentials, delivered as pure Python.** Anything you can build in Essentials
should be buildable here — without RPG Maker, without Ruby, without a
proprietary editor. The engine is a set of modular subsystems over an editable
content contract, designed to be extended.

Three co-equal goals:

1. **Parity** — Essentials is the functional target. A gap in capability is a
   gap to close, not a feature to decline.
2. **Modularity** — subsystems (data, battle, overworld, event runtime,
   rendering, audio) are independently usable and replaceable behind stable
   interfaces.
3. **Pure-Python authoring** — making a game means writing Python and editing
   content folders, not learning Ruby or a GUI editor.

---

## Phase history

### Phases 0–6 — Foundation and v1 engine ✅ DONE

| Phase | Summary |
|-------|---------|
| 0 | Repo structure, GameData repository, PokeAPI pipeline (REST + CSV), Gen 1–5 dataset with Gen 5 values |
| 1 | Pure seeded battle engine: Gen 5 damage, statuses, stages, ordering, PP, Struggle, switching, items, flee/catch, CLI demo |
| 2 | ~35 abilities, 11 held items, all four weathers, entry hazards, screens, Protect/Endure, two-turn/recharge/rampage moves, trapping, Leech Seed, ~50 special-case move handlers, KO-aware AI |
| 3 | Pygame-CE overworld: scene stack, Tiled maps, grid movement, NPCs, warps, grass encounters, full battle UI, catching, whiteout |
| 4 | Event scripting: flags, money, triggers, JSON command set, trainer line-of-sight battles |
| 5 | Save/load, EXP and all growth curves, level-up move learning, post-battle evolution, pause menu, PC box, bag |
| 6 | Content-folder authoring format, linter (`pkmn-lint`), examples: `isleton` and `triad` |

### Phase 7 — Map and rendering parity ✅ DONE

Multiple tile layers with draw priority, configurable tile size, autotile animation,
directional / partial passability, tile animation. RMXP converter emits the format;
`examples/kanto_frlg` (converted from FireRed) plays on it.
*Accepted:* `tests/test_layers.py` green; converted maps render overhead layers + animated water.

### Phase 8 — Event runtime ✅ DONE

Compiled IP-based event VM: integer variables + arithmetic, per-event self-switches,
multi-page conditional events, autorun/parallel triggers, move routes, full control
flow (if/then/else, while, label/goto, wait). Exposed as data and as a Python
authoring API (`events.py`) with a `register_command` extension seam. Save schema v2
persists variables, self-switches, badges, and visited maps.
*Accepted:* `tests/test_events.py` + `tests/test_eventlab.py` green; `examples/eventlab` lints 0/0 and plays.

### Phase 9 — Game systems (in progress)

Multi-method encounters, rich trainer parties, badges + HM field gating, field moves,
Fly / Town Map, map metadata, visited maps — all complete. Ability and move coverage
milestones also landed here.

**Done:**
- Multi-method encounters (land / surf / fishing / rock_smash / headbutt / cave)
- Rich trainer parties (full per-mon IVs/EVs/nature/ability/moves/item)
- Badges, BadgesScene, `give_badge` command, badge-count conditions
- Field moves: Rock Smash, Waterfall, Headbutt, Flash
- Fly / Town Map scene
- Map metadata: `heal_point`, `escape_point`, `dark_cave`, `fly_name`
- `visited_maps` serialized in saves
- **559/559 Gen 5 moves (100%)** handled — EFFECT_SKIPPED rate 0%
- **143/164 Gen 5 abilities (87%)** implemented
- New volatile infrastructure: `substitute_hp`, `type_override`, `foresight_active`,
  `miracle_eye_active`, `disabled_move`, `magic_coat_active`, `last_received_move`,
  `last_used_item`, `power_trick_swapped`; side fields: `wish_turns`, `wish_hp`,
  `lunar_dance`; engine fields: `trick_room`, `gravity_turns`, `magic_room`

**Remaining for v1.0:** *(all done — see RELEASE.md gate table)*

**Remaining for post-1.0:**
- Strength boulder persistence (per-map, not per-session)
- Bike
- Dive (underwater maps + map model support)
- Double / triple / rotation battles (XL architectural project — see below)

### Phase 10 — Importer and shell [PLANNED]

Promote the converter to a supported PBS/RMXP importer: map + event parsing,
tileset terrain/passage mapping, full PBS ingestion with ID normalization.
Add Town Map / Fly data, richer map metadata, audio loop-point metadata, and
a configurable title / new-game-or-continue shell.
*Acceptance:* a clean, full Essentials project imports and plays without hand-editing.

---

## The XL project — multi-active battles

Double / triple / rotation battles are a dedicated battle-module refactor, not a
bolt-on. The engine is currently singles-only (`active(side)` is one slot,
`_do_move` reads the defender as `active(other(side))`).

Planned approach:
1. Generalize `active_idx[side]` → an active-slot list (singles = length 1,
   preserving all current tests and behavior)
2. Parameterize target/defender through `_do_move` and the `moves.py` damage path
3. Add target selection, spread-move iteration (with spread damage ×0.75),
   and ally/redirection handling
4. Order all actors per turn; handle per-slot faints and replacements
5. Double battle UI + AI in `battle_scene.py`

*Acceptance:* a double battle resolves through the pure engine under test with
`tests/test_doubles.py` passing; all existing single-battle tests unchanged.

---

## v1.0 release gate

The tag will not be cut until all items are checked. Tracked in `RELEASE.md`.

| # | Criterion |
|---|-----------|
| 1 | Clean wheel install outside repo root |
| 2 | `pkmn-play` starts with bundled default/example content |
| 3 | `pyproject.toml` dependencies match actual runtime imports |
| 4 | `pytest` fully green |
| 5 | `pkmn-lint` 0/0 for all six bundled examples |
| 6 | `pkmn-audit` no broken cross-references |
| 7 | `pkmn-coverage` 0 unexpected EFFECT_SKIPPED |
| 8 | Held-item Batch A implemented |
| 9 | README, ROADMAP, RELEASE, AUTHORING internally consistent |
| 10 | `CHANGELOG.md` up to date |
| 11 | No `__pycache__` / `.pyc` in release artifacts |
| 12 | CI runs: tests → lint → audit → coverage → wheel build → smoke test |
| 13 | IP / distribution note explicit in LICENSE and README |

---

## Design principles (unchanged)

These disciplines keep the engine modular as it grows toward parity.

- **No region literals in core.** Everything is learned from the content folder.
- **If it lints, it runs.** `contract.py` is the single spec the runtime and
  linter share. Every new feature is added there first.
- **`engine_version` in the manifest.** Content and a fast-moving engine evolve
  without silent breakage.
- **The battle engine stays pure.** Actions in, typed Events out, one injected
  RNG, no I/O. Multi-active will extend it from the inside.
- **One source of truth for state.** `PokemonState` owns all persistent Pokémon
  data. The engine mutates it directly — HP, PP, and status persist after battle
  with no copy-back step.
- **Every subsystem ships behind a feature flag.** A game uses as much or as
  little of the engine as it wants — walking sim, battle tool, or full RPG.
