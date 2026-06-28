# Essentials compatibility: the parity roadmap

## The goal

**Reliably reproduce the full functionality of RPG Maker XP + Pokémon
Essentials, delivered as pure Python.** Anything an author can build in
Essentials, they should be able to build here — without RPG Maker, without
Ruby, without a proprietary editor, using only Python and human-editable
content folders.

This is a deliberate expansion of scope. Earlier the project treated
*simplicity* as a ceiling and declared an eventing VM, layered maps, and
multi-active battles out of scope. That ceiling is removed. Simplicity is
still a craft value — clean modules, deterministic cores, data-driven
content — but it now lives *inside* each subsystem rather than capping the
feature set. Where Essentials has a capability, we build it; we just build
it modularly, with clean seams, so authors can take what they need and
replace what they don't. See `ENGINE_PHILOSOPHY.md` for the full stance.

## How "parity" is measured

The RMXP→engine converter (`tools/` / the `rmxp2kanto` work) is not just a
migration aid — it's the **parity oracle**. For every feature below, the
test of "done" is that the converter can carry the corresponding Essentials
construct across *mechanically*, with no semantic collapsing. Today the
converter has to flatten 3 map layers to 1, drop every event but transfer
warps, and discard all trainers; each item on this roadmap is a chunk of
that lossy translation we get to delete. When a clean, full Essentials
project round-trips through the converter and plays faithfully, parity is
reached.

Effort key: **S** = hours · **M** = a focused session · **L** =
multi-session / architectural · **XL** = a subsystem in its own right.

## Current state (the v1 curated engine)

What exists is genuinely strong and most of it is *retained unchanged* — it
is the modular foundation parity is built on:

- A pure, deterministic battle engine (Gen 5 values, ~50 move handlers,
  abilities, held items, weather, hazards) — actions in, typed events out.
- The full PokeAPI Gen 1–5 catalog as data, with battle behavior layered on
  top and an audit that reports implemented-vs-data-only.
- A content-folder authoring format with a validated contract
  (`pkmn/game/contract.py`) and the "if it lints, it runs" guarantee.
- An agnostic core: no region literals, a recursive `World.resolve`
  seamless-overworld primitive, a uniform warp model, a fixed tile-flag
  vocabulary, and a small JSON script interpreter.

The gap to Essentials is not in *format reading* (a TMX or `.rxdata`
importer is thin) — it is **semantic**: Essentials' map and event models
are richer than ours, and closing that difference is what the tiers below
do.

---

## Tier 1 — Map & rendering parity  [DONE — functional; minor cosmetics deferred]

*Imported maps now look and collide correctly. The functional gaps are
closed in the engine + contract + linter, the converter emits the richer
format, and `tests/test_layers.py` locks the behavior in.*

- [x] **Multiple tile layers + per-tile draw priority** — maps load all
  tile layers; collision is OR'd across them; tiles flagged `over` (RMXP
  priority > 0) draw in a second pass above the player (canopies, roofs,
  bridges). The converter no longer flattens 3→1.
- [x] **Configurable tile size** — 32px (RMXP) tilesets load and upscale to
  the render size; no downscaling pass.
- [x] **Autotiles** — autotile tiles are sampled to their correct interior
  graphic per animation frame (fixing the flat-dark water) and emitted as
  animated tiles. *Approximation:* full 47-piece edge/border blending is
  not yet done (interior tile is used); cosmetic, tracked below.
- [x] **Directional / partial passability** — `block_{up,down,left,right}`
  tile flags; `TileMap.passable(x, y, dir)` plus a source-exit + dest-entry
  check in movement. The converter emits these from RMXP passage bits.
- [x] **Tile animation** — the engine cycles TMX animated tiles on the wall
  clock; the converter bakes RMXP autotile animation frames, so water and
  other autotiles shimmer.
- [ ] **Panorama & fog layers** — scrolling backgrounds / cave fog. Cosmetic;
  not required to import or play RMXP maps. **M**
- [ ] **Full autotile edge-blending** (47-piece) and **reflection /
  surf-overlay sprites**. Cosmetic polish. **M**

## Tier 2 — Event & scripting runtime (the architectural fork)  [CORE DONE]

*Makes maps **function**. This is the hard tier and the place the old
philosophy explicitly refused to go. The runtime core is now implemented
in the codebase, tested, and demonstrated by `examples/eventlab`.*

The flat ~18-command JSON interpreter has been rebuilt as a compiled,
instruction-pointer **event VM** (`pkmn/game/script.py`): scripts compile
to a flat instruction array with real jumps, so control flow composes with
the blocking commands (dialogue, battle, NPC walks, timed waits) that
suspend and resume the VM. State gained integer **variables** and
per-event **self-switches** alongside flags, and all three persist in saves.

- [x] **Integer variables + arithmetic** — `set_var`/`add_var`, and `var`
  conditions with the full comparison set (`== != < <= > >=`). Persisted.
- [x] **Self-switches** (per-event local state) — `set_self_switch` /
  `clear_self_switch`, scoped to the running event's identity; the
  "do this once" backbone. *Common events:* `parallel`/`autorun` triggers
  cover the autorun/parallel kinds; a named shared-event call is a thin
  follow-up. Persisted.
- [x] **Multi-page events with conditional activation** — a script
  definition may be `{"pages": [{"when": <cond>, "do": [...]}]}`; the
  runtime runs the last page whose condition holds (RMXP page priority).
  Demonstrated by the give-a-starter-once Professor in eventlab.
- [x] **Trigger types** beyond step/enter: **autorun** (locks the player,
  fires on entry; spawn-map autoruns are deferred until the scene is
  active) and **parallel-process** (non-blocking; ticked each frame).
- [x] **Move routes** — `move_route` walks an NPC through a direction
  sequence, blocking or in parallel. *Thin:* speed/frequency/jump/through
  flags are not yet modeled (straight directional steps + turns).
- [x] **Control flow + expanded command set** — `if`/`then`/`else` over a
  general condition object (flag/var/self_switch/item/money/not/all/any),
  `while`/`do` loops, `label`/`goto`, and `wait`. A runaway-loop budget
  guards the VM. *Thin/stubbed:* `screen` tint/flash/shake is a minimal
  overlay+wait; show-picture, weather/audio control, and name-input are
  deferred.
- [x] **A Python authoring API for events** — `pkmn/game/events.py`: a
  fluent `Event()` builder plus condition helpers (`var("x") >= 3`,
  `~self_switch("A")`, `flag(...) & money(...)`) that compile to the same
  command dicts. Events can be authored as pure Python or as JSON data.
- [x] **Custom-command / system extension seam** — `register_command(name,
  fn)`; the VM consults the registry before erroring, so a game adds its
  own commands without forking the engine.

*Accepted:* `tests/test_events.py` (VM, conditions, control flow, pages,
extension, Python API) and `tests/test_eventlab.py` (the demo through the
real overworld: parallel route, deferred autorun, multi-page) are green;
the full suite is green and `examples/eventlab` lints 0/0 and plays.

> This tier re-introduces the complexity the original `ENGINE_PHILOSOPHY.md`
> argued against. That is intentional and now policy: "scalable games" in
> the Essentials sense *require* an event runtime. The discipline held: it
> landed as a clean, testable module with a stable interface
> (`ScriptRunner` unchanged) and an extension seam.

## Tier 3 — Game systems

*Reaches feature-completeness for the trainer/RPG layer.*

- [~] **Full trainer spec** — type, EVs/IVs/nature/ability/moves, intro/
  defeat/after text, vision, AI level, items, doubles, rematches (from
  `trainers.txt`). **Done:** battle parties accept a rich per-mon list
  (`[{species, level, ivs, evs, nature, ability, moves, item, gender}]`)
  alongside the compact string, so trainers can field fully-specified
  teams; vision + intro/defeat/after text already exist. **Remaining:** an
  explicit AI level, held-item use in AI, rematches, and the doubles flag
  (the last waits on multi-active battles). **L**
- [x] **EV yield from battle** — `ev_yield` on all 649 species (Phase A);
  awarded on knockout, capped 252/stat and 510 total.
- [~] **Badges + badge-gated mechanics** — `give_badge` command,
  `{"badge": …}`/`{"badge_count": …}` conditions, `BadgesScene` in the pause
  menu (Phase D). **Remaining:** obedience checks (HM field gating exists,
  battle obedience by badge count deferred). **S** remaining.
- [x] **Multi-method encounters** — per-method tables
  (`{map: {method: [...]}}`, back-compat with the legacy flat list):
  **land**, **surf** (rolled while surfing), **old/good/super rod**
  (fishing — press A facing water with a rod), plus `rock_smash`,
  `headbutt`, and `cave` tables the schema and converter emit. The RMXP
  importer now reads every PBS method, so `examples/kanto_frlg` fishes and
  surfs with the bootleg's real Kanto water rosters (Tentacool, Magikarp,
  Staryu, …). *Thin:* day/night & season variants, and the `rock_smash`/
  `headbutt` field *triggers*, ride on the remaining field moves below.
- [~] **Remaining HM/field moves** — **Done (Phase D):** Rock Smash
  (`rock_smash` tile flag, clears boulders like Cut), Waterfall (`waterfall`
  flag, blocks upward surf without `can_waterfall`), Headbutt (`headbutt_tree`
  flag, rolls encounter table), Flash (`can_flash` halves encounter rate,
  lifts `dark_cave` overlay), Fly (`FlyScene` lists visited maps with
  `fly_name`). **Remaining:** Strength (pushable boulders — needs per-map
  boulder-position state), Dive (underwater depth layer), Dig (warp to last
  outdoor map), Whirlpool, Bicycle terrain. ~**M** each.
- [ ] **Bike** (speed + cycling-only terrain) and **Escape Rope** polish.
  **S–M**
- [ ] **Breeding, move relearner/deleter/tutors, reusable TMs, nicknaming,
  Pokédex evaluation** — the long tail of services. **M–L** each.
- [ ] **Multi-active battle formats — double / triple / rotation.**
  Essentials supports these; they were previously declared permanently out
  of scope. Under the parity goal they are **in scope** but **XL**: the
  pure engine is single-active today, so this is real architectural work
  (multiple active slots, targeting, spread moves, ally interactions). See
  `GEN5_GAPS.md`. **XL**

## Tier 4 — World structure & pipeline

*Glue, metadata, and the importer that makes "run the files" near-
mechanical.*

- [~] **Town Map / Fly data** — `FlyScene` lists visited maps that declare a
  `fly_name` property (Phase D). **Remaining:** graphical Town Map overlay
  showing region geography. **M**
- [~] **Richer map metadata** — `heal_point`, `escape_point`, `dark_cave`,
  `fly_name` added to `MAP_PROPS` (Phase D). **Remaining:** bicycle-allowed
  flag, dungeon flag. **S**
- [ ] **A first-class PBS / RMXP importer** — promote the converter to a
  supported tool: `.rxdata` map + event parsing, `Tilesets.rxdata`
  terrain/passage mapping, and PBS ingestion (species/move/item/ability/
  trainer/encounter/connection/metadata) with an ID-normalization layer
  (`NIDORAN♀`, `FARFETCH'D`, the `NNN-name` scheme). This is the
  lightweight processing that never fully disappears, but every tier above
  shrinks it. **L**
- [ ] **Audio loop-point metadata** (`.ogg` loopstart/loopend, MEs). **S**
- [ ] **Save-schema expansion** — persist variables + self-switches +
  per-event state once Tier 2 lands. **M**
- [ ] **Configurable title screen / new-game-or-continue shell.** **M**

---

## Suggested sequencing

1. **Tier 1 first** — imported maps that *look* right are the most visible
   win and unblock authoring against real geometry. Layers + tile size +
   passability before autotiles.
2. **Tier 2 next, in halves** — (a) variables + self-switches + common
   events + triggers (the data model), then (b) move routes + control flow
   + the Python authoring API (the expressive layer). This is the longest
   pole; everything functional depends on it.
3. **Tier 3 trainers + encounters** ride on Tier 2 (trainers become events
   with parties; multi-method encounters are data).
4. **Tier 4 importer** is promoted to a product once Tiers 1–3 mean it no
   longer has to discard anything; multi-active battles (Tier 3, XL) can
   proceed in parallel since they live entirely in the battle module.

## Invariants to preserve while doing all of this

The new direction does not loosen the disciplines that make the engine
modular — it depends on them:

- **The battle engine stays pure** (actions in, typed events out, injected
  RNG). Multi-active formats extend it from the inside; they do not make it
  import game state.
- **One source of truth** for persistent state, now extended to variables
  and self-switches.
- **"If it lints, it runs"** — every new tile flag, layer rule, object
  type, event command, and trigger kind is added to `pkmn/game/contract.py`
  first, so the linter and runtime can never disagree.
- **No region literals in core.** New systems read everything from the
  content folder.
- **Each subsystem is independently usable.** A new module (event runtime,
  layered renderer, multi-active battles) ships behind a stable interface
  and a feature flag, so a game can use as much or as little as it wants.
