# Architecture

## Project direction (architectural implications)

The project's goal has expanded to **parity with RPG Maker XP + Pokémon
Essentials, delivered as pure Python** (see `docs/ENGINE_PHILOSOPHY.md` and
`docs/ROADMAP.md`). Most of what follows in this document is
the factual record of the v1 engine and is retained — those subsystems are
the modular foundation parity is built on. What the new direction adds,
architecturally:

**Done (Phases 7–9):**

- **Event VM** (`pkmn/game/script.py`): promoted from a flat JSON interpreter
  to a compiled, IP-based VM with integer variables, self-switches, multi-page
  conditional events, autorun/parallel triggers, move routes, and full control
  flow — exposed through a Python authoring API (`pkmn/game/events.py`) and a
  `register_command` extension seam. Save schema v2 persists variables and
  self-switches alongside flags/money/party/box/badges.
- **Layered maps** (`pkmn/game/tilemap.py`): multiple tile layers with per-tile
  draw priority (`over`), configurable tile size, autotile rendering (interior
  + animation), and directional/partial passability (`block_<dir>` flags).
- **Badges, HM gating, field moves**: `GameState.badges`, `give_badge` script
  command, badge/visited conditions, `FlyScene`, `visited_maps`, Rock Smash,
  Waterfall, Headbutt, Flash, and the `dark_cave` overlay.
- **Multi-method encounters**: per-method tables (land/surf/old_rod/good_rod/
  super_rod/rock_smash/headbutt/cave), surf rolls while surfing, fishing on
  A-press.
- **Rich trainer parties**: full per-mon specs (IVs/EVs/nature/ability/moves/
  item) alongside the compact string format.
- **Extension seams**: `register_command` lets a content folder add custom
  script commands without forking the engine.

**Planned (Phase C):**

- **Multi-active battles**: generalize `active_idx[side]` → an active-slot
  list; parameterize `_do_move` for target(s); add spread moves, ally/
  redirection, per-slot faints, and doubles UI. See `docs/PhaseProgress.md`.

All additions go into `pkmn/game/contract.py` first ("if it lints, it runs"),
ship behind a feature flag and a stable interface, and add no region literal
to core.

## Why a rewrite

The autopsy of the original prototype found structural problems that
patching couldn't fix:

* **Two parallel battle engines** (`Battle.py` and `engine.py`) and two
  orchestrators, one of which had a literal `pass` where battles should
  run. Neither was authoritative.
* **Three sources of truth** for a Pokemon's state: roster JSON dicts,
  `Pokemon` instances, and the engine's deep copies (which silently
  reset HP to full). Display, persistence, and simulation disagreed.
* **Key-format drift**: species data normalized stats to underscores
  while the engines indexed `'special-attack'` — a guaranteed KeyError
  on the first special move. Party files used a third format.
* **Wrong-generation constants**: Gen 6 crit multiplier (1.5x) and
  damage roll (90-100%), Gen 1 approximate stage multipliers.

## The replacement model

```
GameData (pkmn/data)          PokemonState (pkmn/core)
  reads the game folder         the ONE persistent Pokemon:
  once, caches, normalizes      species/level/IVs/EVs/nature,
  keys at the boundary          move slots w/ PP, HP, status
        |                                 |
        v                                 v
BattleEngine (pkmn/battle) -- wraps each PokemonState in a
  BattlePokemon (stages + volatiles), consumes Actions, emits Events.
  Pure: injected RNG, no I/O. HP/PP/status mutations go straight to
  PokemonState, so post-battle persistence is automatic.
        |
        v
Renderers (pkmn/cli today, pygame in Phase 3)
  translate the Event stream to text/animation. format_event() in
  cli/battle_demo.py is the canonical translator.
```

### Phase machine

`WAITING_ACTIONS -> submit_turn(a1, a2) -> [WAITING_REPLACEMENT ->
submit_replacement(side, idx)]* -> ... -> OVER`. The engine never blocks
on input, which makes it equally driveable by a CLI loop, a pygame event
loop, or an AI-vs-AI test harness.

### Move execution

`MoveEffect` mirrors PokeAPI's move meta (ailment, chances, stat
changes, drain/recoil, hit counts, healing). A single interpreter in
`battle/moves.py` executes any move from that metadata; special cases
register named handlers (`@handler("rest")`). Unknown effects emit
`EFFECT_SKIPPED` events rather than misbehaving silently — grep the
event log to measure coverage.

One data quirk worth knowing: PokeAPI's `damage+raise` category means
the stat changes apply to the **user** (this includes Superpower's and
Overheat's self-drops, which are negative "raises"), while
`damage+lower` applies to the **target**. The interpreter encodes this.

### Gen 5 fidelity notes

Implemented to Gen 5 values: 2.0x crits at 1/16 base (ignoring helpful
stages), 85-100% damage roll, integer-floor damage pipeline, exact stage
fractions, paralysis speed/4 + 25% block, sleep 1-3 turns (re-rolled on
re-entry), 20% thaw + defrost flag + fire-move thaw, 1/8 burn and
poison, ramping n/16 toxic with counter reset on switch, Gen 5 flee and
capture formulas, Thunder Wave's type-immunity check, Gen 2-5 status
type immunities (Electric CAN be paralyzed pre-Gen 6), Struggle with
1/4 max-HP recoil, Gen 5 2-5 multi-hit distribution.

Known simplifications (documented so they're decisions, not surprises):

* Modifier rounding uses plain floors rather than the games'
  round-half-down at every step; damage can differ by 1 in rare rolls.
* Sleep counter semantics: counter = failed turns; Rest = exactly 2.
* Capture uses 4 shake checks, no critical-capture mechanic.
* Run/item/switch ordering uses fixed category priorities (run > item >
  switch > moves) rather than per-gen edge cases like Pursuit.

## Phase 2 additions

* **`pkmn/battle/passives.py`** — every ability and held-item hook in
  one place (stat/power/speed modifiers, immunities and absorbs,
  contact punishment, switch-in effects, end-of-turn residuals,
  survive-lethal). Adding an ability usually touches only this file.
* **`pkmn/battle/field.py`** — `SideState`: hazards (Spikes layers,
  Toxic Spikes layers, Stealth Rock) and timed side conditions
  (Reflect, Light Screen, Safeguard, Mist, Lucky Chant, Tailwind,
  Healing Wish). Weather lives on the engine (whole-field).
* **Two-turn flow** — charge/semi-invulnerable state, recharge turns,
  and rampage locks are engine concerns (`_do_move`); `legal_actions`
  reflects every lock (charging, recharging, rampaging, choice items,
  Encore, Torment, Taunt, Imprison, trapping).
* **Handler registry** — ~50 moves with bespoke behavior register via
  `@handler("move-id")` in `moves.py`. Unknown effects still emit
  `EFFECT_SKIPPED`, and `pkmn/cli/coverage.py` measures the honest gap.

### Documented simplifications
* Attract ignores gender (genders aren't modeled yet) and always takes.
* Baton Pass sends a random able bench member (replacement prompt is a UI
  nicety deferred to a later pass); stages and passable volatiles carry
  over, hazards apply.
* Mud/Water Sport last 5 turns instead of "while the user is active".
* Weather moves ignore the duration-extending rocks (Damp Rock etc.).
* Sleep counters tick on failed move attempts, not elapsed turns.

## Phase 3 additions (`pkmn/game/`)

* **`scene.py`** — `Game` shell + scene stack + an `Input` abstraction.
  The pygame event pump only *feeds* Input, so tests drive the real
  game frame by frame with SDL's dummy drivers — every client test runs
  headless in CI.
* **`tilemap.py`** — pytmx wrapper exposing the gameplay queries
  (blocked / tall grass via tile properties; warps, NPCs, signs, spawn
  via the object layer). Maps remain ordinary Tiled files. Extended in
  Phase 7 to support multiple layers, autotiles, and directional passability.
* **`overworld.py`** — grid movement with pixel interpolation, NPC
  collision + interaction, warp handling, encounter rolls.
* **`battle_scene.py`** — a state machine (msg/menu/moves/bag/party)
  over the pure engine. Battle text comes from the same `format_event`
  as the CLI demo; HP bars animate toward engine truth each frame. The
  engine still never imports the client.
* **`tools/make_assets.py`** — procedurally draws the tileset and
  character strips and writes the .tmx maps, so the repo ships no
  third-party art.

## Data pipeline (full-catalog restructure)

`pkmn/datagen/fetch.py` builds `game/data/` from PokeAPI with two
interchangeable, fully cached sources: the REST API (pokeapi.co/api/v2;
every response cached in `.pokeapi_cache/`, so refreshing one resource
means deleting its cache file and re-running) and PokeAPI's own CSV
database on GitHub (`--source csv`, much faster for full builds).
Both emit identical normalized JSON.

The dataset is now the complete Gen 1-5 catalog: `abilities.json` (164,
generation + effect text), `items.json` (678, category/pocket/flags/
cost/effect text), per-move `short_effect` strings, and species
back-dated to Gen 5 — `pokemon_types_past` restores pre-Fairy typings
(22 species) and post-Gen-5 abilities are filtered out.

Battle *behavior* is deliberately a separate layer from data:

* `pkmn/datagen/mechanics.py` — structured bag mechanics (medicine
  heal/cure/revive amounts, X-item stages, ball multipliers) merged
  into items.json at build time, since PokeAPI stores these as prose.
  Conditional balls use flat simplified rates.
* `pkmn/battle/passives.py` — held-item and ability hooks, with
  explicit `IMPLEMENTED_ABILITIES` / `IMPLEMENTED_HELD` registries.
* Anything without an entry in either layer is *data-only and inert* —
  visible, listable, holdable, but without battle effect. Nothing in
  the catalog can crash the engine by existing.

`python -m pkmn.cli.audit` prints catalog counts, implementation
coverage, and cross-validates every reference (species -> abilities,
learnsets -> moves, types -> chart); it exits nonzero on any dangling
reference, making it CI-able alongside `pkmn.cli.coverage`.

## Phase 4 additions (events & scripting)

* **`pkmn/game/script.py`** — initially a flat JSON interpreter; later
  promoted to a compiled event VM in Phase 8 (see below). The Phase 4
  additions established the trigger/cutscene model, trainer battle wiring,
  and the yield/resume pattern the VM builds on.
* **Triggers** — Tiled objects (`trigger`) fire scripts on step-on or
  map entry, each gated by `unless_flag`; trainers (`trainer` objects)
  carry party specs ("snivy:8|patrat:5"), sight range, prize, defeat
  flag, and pre/post dialogue directly in map properties.
* **Cutscenes** — trainer spotting pauses input, shows the "!", walks
  the trainer adjacent with the same grid interpolation as the player,
  then hands control to a generated script. `move_npc` reuses the same
  walking machinery from scripts.
* **GameState** gains `flags` (a set) and `money`; whiteout during a
  scripted battle aborts the script naturally because the map reload
  drops the runner.

## Phase 5 additions (game systems)

* **`pkmn/core/experience.py`** — all six official growth curves with
  the canonical piecewise formulas, plus the classic flat battle award
  (base * level / 7, x1.5 vs trainers).
* **Growth lives on the core, not the client** — `gain_exp()` /
  `evolve()` in `pkmn/core/pokemon.py` mutate PokemonState (level-up
  move learning, stat recalc preserving the HP delta, evolution edges
  from the dataset). The battle scene only narrates the results and
  defers evolutions to after victory, as the games do. Move learning
  auto-skips when all four slots are full (replacement prompt is a UI
  nicety for later).
* **Persistence** — `GameState.to_dict()/from_dict()` round-trips the
  party, PC box, bag, money, flags, vars, self-switches, badges,
  visited_maps, and location through one JSON file (`pkmn/game/save.py`,
  atomic via `os.replace`). The flag store from Phase 4 is what makes
  world progress save for free; `badges` and `visited_maps` extend the
  same pattern.
* **`pkmn/game/menus.py`** — pause/party/summary/bag/PC scenes on the
  same translucent scene-stack pattern as dialogs; the PC refuses to
  deposit your last able Pokemon.

## Phase 6 additions (authoring toolkit)

* **Game folders** — the client is fully parameterized by a content
  directory: `Game(game_dir=...)` loads game.json and threads the root
  through Assets, TileMap, encounters, and scripts. GameState.new_game
  is manifest-driven (starter, bag, money, start location, flags).
  Hexton (`game/assets/`) is simply the reference folder; nothing in
  the engine refers to its content by name.
* **`pkmn/cli/lint.py`** — headless validation (pytmx base loader, no
  pygame window) of every cross-reference an author can break: warps,
  scripts, party specs, encounter tables, items, the optional dex
  subset, spawn/start walkability, and sprite presence. Exit codes make
  it CI-able next to `audit` and `coverage`.
* **`examples/isleton/`** — the proof region: its own tileset, sprites,
  manifest, two maps, a trainer gate, and a flag-gated ending, with no
  engine code in the folder. `tools/make_example_region.py` rebuilds it.

## Polish & extensibility pass

* **Feature flags** — `Game.feature(name)` / `Game.setting(name)` read
  the manifest; encounters, trainer battles, experience, evolution,
  move-replacement prompts, running, and each pause-menu entry are
  individually toggleable, defaulting ON. Systems check their own flag
  at the call site, so a disabled system simply never engages.
* **Per-map properties** — Tiled map properties carry `weather`
  (overworld tint + initial battle weather via engine.set_weather) and
  `encounter_chance`; the manifest's `settings` provides globals.
* **Deeper scripts** — choice (modal options spliced into the queue
  like if_flag), shop (catalog-priced, script-overridable), give_pokemon,
  take_money, if_money. Trainer/party specs accept `@held-item`.
* **Move replacement** — gain_exp surfaces `full_moves`; the battle
  scene runs an interactive forget/learn prompt (or auto-skips when the
  feature is off).
* **Form aliases** — repository.species() resolves base names to the
  default form (basculin -> basculin-red-striped), so content authors
  never need to know PokeAPI's form suffixes.
* **`examples/triad/`** — the showcase: 6 maps, 8 trainers (held items
  included), 3 shops, weather routes, a gift-Pokemon choice, a roadblock
  NPC on `visible_unless`, and a doubly flag-gated finale.

## Phase 7 additions (map & rendering parity)

* **Multiple tile layers** — `TileMap` loads all layers and composites them in
  order; `over`-flagged tiles draw above the player sprite (tree canopies,
  roofs, bridges, second-floor overpasses).
* **Configurable tile size** — `tilewidth` is read from the `.tmx` rather than
  hard-coded; `examples/kanto_frlg` uses 32×32 tiles.
* **Autotile rendering** — interior-fill autotiles animate via `frames` metadata
  (water shimmer, etc.). Full 47-piece edge-blending is deferred as cosmetic.
* **Directional / partial passability** — `block_<dir>` tile flags gate movement
  by crossing direction (counters you can talk over, one-way fences, cliff
  edges). `ledge_<dir>` tiles produce two-tile hops.
* **`tools/rmxp2kanto.py`** — converts RMXP/Essentials PBS + TMX data to the
  engine's format, emitting autotile frames, per-method encounter tables, and
  directional flags.

## Phase 8 additions (event VM)

* **Compiled IP-based VM** (`pkmn/game/script.py`) — scripts compile to an
  instruction list; the runner holds an instruction pointer that yields to
  scenes and resumes when they pop.
* **Variables and self-switches** — integer `vars` and per-event boolean
  `self_switches` are first-class state types alongside flags; all three persist
  in saves (schema v2).
* **Multi-page conditional events** — a script id may resolve to
  `{"pages": [...]}` where each page has a `when` condition; the runtime
  activates the last page whose condition holds. The backbone of one-shot NPCs,
  gym puzzles, and branching dialogue.
* **Autorun / parallel triggers** — `when: "autorun"` locks the player and runs
  once the scene activates; `when: "parallel"` ticks each frame without blocking
  input. Both are deferred to scene activation so autoruns never fire during a
  warp transition.
* **Move routes** — the `move_route` script command walks an NPC along a path
  using the same pixel-interpolation machinery as the player.
* **General condition object** — `if` / `while` / event pages share one schema:
  `{"flag":...}`, `{"var":..., "op":..., "value":...}`, `{"self_switch":...}`,
  `{"badge":...}`, `{"visited":...}`, `{"not":...}`, `{"all":[...]}`,
  `{"any":[...]}`.
* **Python authoring API** (`pkmn/game/events.py`) — the `Event` builder and
  `page()` helper produce valid VM programs without writing raw JSON.
* **`register_command` seam** — a content folder registers custom commands
  against the VM without forking engine code.

## Phase 9 additions (game systems & field moves)

* **Badges + HM gating** — `GameState.badges: set`, `give_badge` script command,
  `{"badge": name}` / `{"badge_count": n}` conditions, and `BadgesScene`
  pause-menu entry (opt-in `"badges"` feature).
* **Expanded capability flags** — `can_rock_smash`, `can_flash`, `can_waterfall`,
  `can_dive`, `can_fly`, `can_headbutt`, `can_strength` added to `contract.py`
  and `GameState`.
* **Field moves** — Rock Smash (clears `rock_smash` tiles like Cut), Waterfall
  (blocks upward surf on `waterfall` tiles without `can_waterfall`), Headbutt
  (rolls the map's `headbutt` encounter table from `headbutt_tree` tiles), Flash
  (halves encounter rate; lifts the `dark_cave` overlay).
* **Fly / Town Map** — `FlyScene` lists maps that declare a `fly_name` property
  and warps the player to the chosen one (opt-in `"fly"` feature; requires
  `can_fly`).
* **`visited_maps`** — `GameState.visited_maps: set` tracks entered maps and
  persists in saves; powers the `{"visited": map_id}` condition.
* **Map metadata** — `heal_point`, `escape_point`, `dark_cave`, `fly_name` added
  to `MAP_PROPS` and `contract.py`.
* **Multi-method encounters** — per-method tables (land/surf/old_rod/good_rod/
  super_rod, plus rock_smash/headbutt/cave in the schema); surf rolls while
  surfing; fishing on A-press facing water.
* **Rich trainer parties** — battle parties accept a full per-mon list
  (IVs/EVs/nature/ability/moves/item) alongside the compact string format.
* **EV yield** — species `effort` data wired through `pkmn/datagen/fetch.py`;
  EVs awarded on knockout, capped per stat.

## Gen 5 sprites (cached)

`pkmn/game/sprites.py` resolves a species' national dex number to a Gen
5 Black/White sprite from github.com/PokeAPI/sprites (the same files the
REST API exposes), caching each PNG under `.sprite_cache/gen5/{front,
back}/{dex}.png`. `Assets.battler(species_id, name, dex=, back=)` loads
the cached sprite (foe = front, player's side = back), scales 96x96 down
to SPRITE_PX (64), memoizes per (species, back), and falls back to the
procedural blob when a sprite isn't available. Fetching is opt-in
(`sprites.FETCH_ENABLED`, turned on by `play.py` and the sprites CLI,
force-off via `PKMN_NO_SPRITE_FETCH`), so cache hits work everywhere but
the test suite never touches the network. `python -m pkmn.cli.sprites`
pre-warms the cache for a whole game folder (dex subset, starter, wild
encounters, gift Pokemon, and every trainer party) or the full 1-649
dex. This keeps the philosophy intact — the repo ships no third-party
assets; the cache is populated on demand.

## Sequenced battle animations

The engine still resolves a whole turn and returns an ordered Event
list; the battle scene no longer dumps it. `_enqueue` translates events
into a queue of timed *steps* (`pkmn/game/battle_scene.py`):

* `text` -- a message page; may carry a lunge animation for the mover.
  Auto-advances after a readable hold; A/B skips it.
* `hp` -- eases `disp_hp[side]` toward the event's `remaining_hp` (every
  HP-changing event carries it), with a hit-flash on damage. Completes
  when the bar settles.
* `faint` -- sinks + fades the sprite over FAINT_DUR.
* `send` -- instantly snaps a freshly sent-in Pokemon's bar.

`update()` plays one step at a time and only advances when the current
one finishes, so a turn reads: mover lunges + "X used Y!" -> target bar
drains -> "super effective!" -> next mover -> its target drains -> faints
sink. `disp_hp` now tracks a per-side target the steps drive, decoupled
from the engine's already-final HP, which is what lets the bar stop at
correct intermediate values. The message box persists the last line
through HP/faint beats so text stays aligned with what is happening.

## Default art + character animation

`tools/art.py` is the shared art library every bundled region draws from,
so the detailed default look lives in one place and the repo still ships
no third-party image files. It provides shaded/textured tile painters
(grass, tall grass, path, water, sand, tree, rock, flower, sign, fence,
brick wall, roof, floor, rug, counter, mat, dune, dead tree, reed, plank,
palm, shell) parameterised by palette, plus `character_sheet(...)` which
renders a 4-direction x 4-frame walk-cycle (outline, 3-tone shading,
swinging arms, striding legs, head-bob, ground shadow).

Character sheets are a grid: 4 rows (down, up, left, right) x N columns
(walk frames), each cell 16 wide x 24 tall. `Assets._char_sheet`
auto-detects this against the legacy 64x16 single-frame strip and reports
the frame height; the overworld blits with a `(frame_h - TILE)` y-offset
so a taller sprite stands a head above its tile. `OverworldScene`
advances a per-mover `walk_t` while moving (player and walking NPCs) and
picks the frame via `_frame_idx` (an 8-tick 0-1-2-3 cycle); idle snaps to
frame 0. The three `tools/make_*` scripts compose each region's tileset
and sprites from `art.py` with their own palettes, then write the PNGs.

## Render resolution & display scaling

The game renders at a high native resolution so text and sprites have
real pixels rather than relying on upscaling a tiny canvas. `config.py`
defines a `SCALE` (default 4) over a 256x192 design grid:
`BASE_TILE = 16` is the grid art is authored on, `TILE = BASE_TILE *
SCALE = 64` is the on-screen tile, and `LOGICAL_W/H = 1024x768` is the
canvas every scene draws to. All on-screen geometry and font sizes
derive from `SCALE`, `TILE`, or `LOGICAL_*`, so changing `SCALE` rescales
the whole UI uniformly.

Art stays authored at 16px on disk (no regeneration when SCALE changes):
`TileMap` upscales each tile to `TILE` at load with nearest-neighbour
(cached), and `Assets._char_sheet` slices character sheets on the
`BASE_TILE` grid and upscales frames to the render size. Object
coordinates in maps are interpreted with the map's own `tilewidth`
(16), independent of the render `TILE` -- so the `.tmx` files and the
lint CLI need no changes. Gen 5 battlers (96px) are upscaled to
`SPRITE_PX` (192) via a crisp integer scale, never downscaled.

`Game._present` then scales the 1024x768 canvas to the window. By
default `Game._fit` uses the largest *integer* 4:3 factor (1:1 at 1080p)
and centres it -- integer scaling keeps every pixel uniform. `--fill`
switches to sharp-bilinear (integer pre-scale, then one gentle
`smoothscale` to the exact size) to fill the screen without uneven
pixels; because the source is already high-resolution, the result stays
crisp. Headless mode renders the canvas 1:1 so tests are unaffected.

## The content contract (`pkmn/game/contract.py`)

`contract.py` is the single authority for what a region may contain: the
`ENGINE_VERSION`, tile flags (`blocked`, `grass`, `surf`, `cuttable`,
`rock_smash`, `waterfall`, `headbutt_tree`, ledges, directional blocks),
per-map properties (`weather`, `encounter_chance`, the `connect_*`/`offset_*`
seamless metadata, `border`, `heal_point`, `escape_point`, `dark_cave`,
`fly_name`), the object types and their property keys, the script-command set
(including `give_badge`, `set_var`, `add_var`, `set_self_switch`), the weather
names, reserved `CAPABILITY_FLAGS` (`can_surf`, `can_cut`, `can_rock_smash`,
`can_flash`, `can_waterfall`, `can_dive`, `can_fly`, `can_headbutt`,
`can_strength`), and the manifest `FEATURES`/`SETTINGS` key sets (so the
linter catches typo'd toggle names). Both the runtime and the linter import
these constants, so the validator and the engine cannot drift. `Game` checks
the manifest's `engine_version` on load (a region targeting a newer engine is
refused with a clear message), and `pkmn.cli.lint` rejects unknown
flags/objects/commands and bad versions in addition to its referential checks,
making "if it lints, it runs" a real guarantee.

## Seamless overworld (`World` in `tilemap.py`)

A region is a graph of maps. Discrete maps are linked by `warp` objects;
maps that declare per-edge `connect_*` + `offset_*` properties are
stitched into one continuous, scrolling overworld. All of that seamless
behaviour flows through a single recursive primitive, `World.resolve`,
mirroring Gen 1's `get_tile`: an in-bounds coordinate returns its own
tile; an off-edge coordinate recurses into the neighbour on that edge
(shifted by the offset and the crossed map's size); an unconnected edge
returns nothing (a border tile / wall). Rendering (`World.draw`, with the
camera centred and unclamped), collision (`World.blocked`), and seamless
boundary crossing in the overworld all call through `resolve`, so the
stitch is defined in exactly one place. A map with no connections keeps
the original clamped single-map path, so a region mixes both topologies
per map. See `examples/seamless` and `docs/ENGINE_PHILOSOPHY.md`.
