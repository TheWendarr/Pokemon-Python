# Changelog

## [Unreleased] — v1.0-rc (Phase A hardening)

### Added
- **Title screen** (`TitleScene`): the game now opens to a title screen with
  the region name, "Press START", and a **New Game / Continue** menu.
  Continue is only available when a save file exists. Manifest keys:
  `title.text`, `title.music`, `title.art`.
- **EV-yield data**: all 649 species now carry `ev_yield` (from the PokeAPI
  CSV mirror). Effort values are awarded on knockout, capped 252/stat and
  510 total, and accumulate on `PokemonState.evs`.
- **Feature-toggle contract validation**: `contract.py` now enumerates the
  known `features` and `settings` keys. The linter (`pkmn-lint`) reports
  unknown keys in a manifest's `features:` or `settings:` block.
- **CI smoke harness** (`tests/test_examples_boot.py`): boots all 6 example
  regions headless and ticks 10 frames each — catches a region that lints
  clean but crashes on load.
- **Packaging** (`pyproject.toml`): `pip install -e ".[dev]"` wires up
  `pkmn-demo`, `pkmn-play`, `pkmn-fetch-data`, `pkmn-lint`, `pkmn-audit`,
  `pkmn-coverage`, and `pkmn-sprites` as console scripts.
- **LICENSE** (MIT) with an explicit note on Nintendo IP.

### Fixed
- **`kanto_frlg` lint warnings** (was 17, now 0): all 12 maps without a
  spawn object now have one; 5 invalid one-way seamless connections removed.
  The RMXP converter (`tools/rmxp2kanto.py`) is fixed at the source — spawns
  are now emitted for every map, and conflicting direction slots are skipped
  so re-running the converter produces a clean output.

### Datagen
- `pkmn-fetch-data` (both `--source csv` and `--source rest`) now writes
  `ev_yield` into each species JSON.

---

## Phase D — Badges, field moves, Fly, map metadata

### Added
- **Badge system** — `GameState.badges: set`; `give_badge` script command;
  `{"badge": "name"}`, `{"badge_count": n, "op": ..., "value": n}`, and
  `{"visited": "map_id"}` conditions in `eval_condition`. `BadgesScene`
  in the pause menu (opt-in via `"badges": true` in `features`).
- **Expanded capability flags** — `can_rock_smash`, `can_flash`,
  `can_waterfall`, `can_dive`, `can_fly`, `can_headbutt`, `can_strength`
  added to `CAPABILITY_FLAGS` in `contract.py` and as `@property` shortcuts
  on `GameState`.
- **Rock Smash** — `rock_smash` tile flag; pressing A while facing one clears
  the boulder (per-session, like Cut) when `can_rock_smash` is set. A
  `smashed` set on `TileMap` tracks cleared boulders; cleared tiles are hidden
  in rendering.
- **Waterfall** — `waterfall` tile flag (a surf tile that blocks upward
  movement without `can_waterfall`). `_walkable_dir` extends `_walkable` with
  a direction parameter to enforce the directional restriction.
- **Headbutt** — `headbutt_tree` tile flag; pressing A while facing one rolls
  the map's `headbutt` encounter table (50% chance) when `can_headbutt` is
  set; without the capability a dialogue fires.
- **Flash / dark cave** — `dark_cave` map property; when set and `can_flash`
  is not in flags, a pitch-black radial overlay renders around the player.
  `can_flash` also halves the encounter rate while active.
- **Fly / Town Map** — `FlyScene` (opt-in via `"fly": true` in `features`)
  opens from the pause menu when `can_fly` is set; lists visited maps that
  declare a `fly_name` map property and warps to the selected one.
- **`visited_maps`** — `GameState.visited_maps: set` accumulates every
  `map_id` passed to `load_map`; serialized in saves; tested by the
  `{"visited": …}` condition.
- **New map properties** — `heal_point`, `escape_point` (JSON
  `{map, tile}` overrides for whiteout/Escape Rope), `dark_cave` (bool),
  `fly_name` (display name for Fly) — all added to `MAP_PROPS` in
  `contract.py`.
- **seamless example updated** — tileset extended with `rock_smash` (GID 9),
  `waterfall` (GID 10), and `headbutt_tree` (GID 11) tiles; `rock.tmx` demo
  map; `game.json` grants all new capabilities and enables `badges`/`fly`.
- **23 new tests** in `tests/test_phase_d.py` covering every new system.

### Test suite
343 passed, 1 skipped (baseline before Phase D: 320 passed, 1 skipped).

---

## Phase 8 — Event runtime  (core complete)

Compiled IP-based event VM: integer variables + arithmetic, per-event
self-switches, multi-page conditional events, `autorun`/`parallel` triggers,
move routes, control flow (`if`/`while`/`label`/`goto`/`wait`), and a Python
authoring API (`events.py`). Save schema v2.

## Phase 7 — Map & rendering parity  (functional)

Multiple tile layers with draw priority, configurable tile size, autotile
rendering (interior + animation), directional/partial passability, and tile
animation. RMXP converter emits the richer format.

## Phase 6 — Authoring toolkit

Game-folder format: `game.json` manifest, maps, tileset, sprites,
`scripts.json`, `encounters.json`. `pkmn-lint` validates everything. Rich
script command set (choice/shop/give_pokemon, held items in trainer specs,
form aliases), `examples/triad` showcase region.

## Phase 5 — Game systems

Save/load, experience with all six growth curves, level-ups, move learning,
evolution, START pause menu (party, bag, save), PC box, Pokédex.

## Phase 4 — Events & scripting

Flag store + money, step/interact/enter/autorun triggers, JSON script
interpreter, trainer line-of-sight battles, interior maps.

## Phase 3 — Overworld v1

Pygame-CE client: scene stack, Tiled maps, grid movement, NPCs, warps,
wild encounters, full battle UI.

## Phase 2 — Battle completeness

~35 abilities, 11 held items, four weathers, entry hazards, screens,
Protect, two-turn/recharge/rampage moves, ~50 special-case handlers.
91 pytest cases.

## Phase 1 — Battle core

Pure seeded engine: Gen 5 damage, statuses, stages, ordering, PP/Struggle,
switching, items, flee/catch, CLI demo. 50 pytest cases.

## Phase 0 — Foundations

Repo structure, canonical data models, PokeAPI pipeline, Gen 1-5 dataset
with Gen 5 values.
