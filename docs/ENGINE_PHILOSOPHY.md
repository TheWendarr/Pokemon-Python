# Engine philosophy: an agnostic engine over an editable data contract

This document sets the design philosophy for turning the codebase into a
true *engine* — one that knows nothing about any particular region and
runs whatever conforming content it is handed. It is informed by the
Lazy Devs Professor's teardown of how Pokémon Gen 1 stores Kanto and
rebuilds it on a constrained platform (Pico8). The thesis it crystallises:

> **A game engine is a small set of composable, content-agnostic
> primitives operating over a simple, human-editable data contract. The
> region is pure data; the engine never knows its name.**

## What Gen 1 actually teaches (notes)

The video's value is not the Game Boy tricks themselves — it is the
*shape* of the design.

1. **A clean atomic → composite hierarchy with maximal reuse.** Gen 1
   has three levels: 8x8 *tiles* (graphics), 16x16 *squares* (the
   gameplay/movement/collision grid), 32x32 *blocks* (the map-storage
   unit). Maps are sequences of block indices; blocks reference tiles
   from one *shared* blockset used by the entire overworld. Pallet Town
   is 1,440 tiles but stores in 90 numbers. The lesson is reuse and a
   layered model, not the specific 32px packing.

2. **Seamless world = connections + offsets, not a global map.** Kanto
   is not one big map and not a perfect jigsaw. Each map header lists up
   to four neighbours (N/S/E/W) and a per-edge *offset* (Viridian is -5
   relative to Route 1 because their widths differ). That is the entire
   stitching system. The author's own lesson: he over-engineered his
   worries (C-shaped routes, mismatched widths) and the dead-simple
   connection+offset model handled all of them. *Never let the perfect
   be the enemy of the good.*

3. **One recursive primitive produces the whole world.** `get_tile(map,
   x, y)`: if the coordinate is on the map, return its tile; if it is
   off the edge, look up the neighbour in that direction, adjust by the
   offset and dimension, and **call `get_tile` recursively** on that
   neighbour; if there is no neighbour, return the map's *border tile*.
   Stitching, borders, and seamless scrolling all fall out of this one
   function. This is what an engine primitive should look like.

4. **Every transition is a warp.** Doors, stairs, cave mouths, floors,
   building interiors — all are entries in a uniform table mapping
   `(map, location) -> (target map, location, post-step facing)`.
   Interiors are just more maps. One mechanism, kept as readable data.

5. **Tile flags are the entire interaction vocabulary.** Collision and
   behaviour are bitflags on tiles, sampled from the bottom of the
   square you step into: blocked, ledge (per direction), cuttable,
   water/surf, tall-grass. Content sets flags; the engine implements
   behaviour. Ledges = "take two steps"; cut = swap the tile; surf =
   different sprite over water; grass = the split-sprite overlap effect.

6. **The world moves, not the player.** The player stays dead-centre;
   the map scrolls underneath. Movement is a small state machine
   (idle -> walk -> snap). Animation advances every N frames.

7. **Editability is a deliberate tradeoff against efficiency.** He packs
   bulk map data into compact binary, but keeps the warp list as plain,
   readable data *on purpose* — "it allows us to modify the data in case
   we want to change something," even at a token cost.

8. **Scope realism.** "It's easy to catastrophically underestimate how
   big this game is." Adopt proven patterns, ship incrementally, and
   prefer designing something new over boiling the ocean.

## What we adopt — and what we deliberately do not

The single most important reading of this video is **critical**: much of
the cleverness is in service of Game Boy constraints — tiny RAM, 32x32
VRAM, cartridge size, Pico8's token budget. We run on Python/Pygame on a
modern machine and author maps in Tiled. Those constraints do not apply,
and the author says so himself ("with modern computers we get to just
load in all the maps at once").

**Adopt (timeless):**
- Composable, content-agnostic primitives — especially a recursive
  tile-lookup as the core of the world.
- Connections + offsets for an optional *seamless* overworld.
- A uniform warp table for every transition; interiors are just maps.
- A small, fixed, documented **tile-flag vocabulary** as the terrain
  interaction language.
- Human-editable content at the contract boundary; validate it.
- Scope realism and incremental delivery.

**Do NOT cargo-cult (constraint-driven hacks):**
- 32x32 metatile/"block" compression — Tiled already gives us tilesets
  (reuse) and arbitrary map sizes; packing tiles into blocks would add
  complexity and *hurt* editability for zero benefit here.
- "Wallace & Gromit" VRAM strip-drawing and wraparound — we already redraw
  the visible tiles each frame, centred on the player; that is fine.
- Binary string packing of map data — our maps are `.tmx` and our data is
  JSON precisely so a region stays human- and tool-editable.

In short: copy the *architecture of ideas*, not the *workarounds*.

## The engine model we commit to

Three layers, with a hard wall between them:

- **Core** — the loop, renderer, scene stack, deterministic rules
  (the `BattleEngine` is the exemplar: actions in, typed events out, no
  rendering knowledge), and the *interpreters* for maps, warps, scripts,
  and data. The core must never contain a region-specific literal.
- **Contract** — a versioned, validated spec of the region-folder format.
  The only thing core and content agree on.
- **Content** — a region folder conforming to the contract. Nothing in it
  is privileged; the engine learns everything from data.

## The world contract

**A region is a graph of maps.** Each map carries: a tile grid (`.tmx`,
Tiled-editable), tile flags, an object layer, and map metadata (weather,
music, border tile, and — new — optional edge **connections with
offsets**). The engine supports two topologies *through one data model*,
and a region picks per map:

1. **Warp-linked** discrete maps (towns, interiors, caves) — what we have
   today, transitions via warps.
2. **Seamless** overworld — adjacent maps declare connections+offsets and
   the engine renders/scrolls across them continuously via a recursive
   `tile_at(map, x, y)` that handles neighbours and borders exactly as in
   Gen 1.

This is the concrete answer to "ingest a greatly customised region": the
region declares its own topology, scale, and connectivity; the engine
just walks the graph.

**The interaction vocabulary is fixed and documented.** Tile flags:
`blocked`, `grass` (today) plus `ledge_{up,down,left,right}`,
`water`/`surf`, `cuttable` and friends. Object types: `warp`, `npc`,
`trainer`, `trigger`, `sign`, `spawn`. The engine implements behaviour for
each; content only sets them.

**Everything that changes maps is a warp.** Interiors and floors are maps;
doors and stairs are warps. No special interior system.

**Events are the one controlled extension point.** Bespoke behaviour
(cutscenes, gifts, shops, branching) is expressed in `scripts.json`
through a **fixed command vocabulary** run by the script interpreter —
data, not engine code.

## The decision the video settles for us: fixed vocabulary, not plugins

Last time we flagged an open fork: a fixed, composable vocabulary versus a
plugin system where a region registers custom engine behaviour. The video
argues decisively for the former — its entire expressive range comes from
*combining* tile flags, a warp table, and a few movement modes, and it
explicitly prefers simple systems over extensible ones. We follow suit:

- Terrain/interaction behaviour: a **fixed tile-flag vocabulary**.
- Map topology: a **fixed map/object schema** (with the connections
  addition).
- Bespoke events: the **fixed script command set** (this is our
  data-driven "composition" layer — powerful, but not arbitrary code).
- Custom *content* (species, moves, types, abilities, items, tilesets,
  sprites, maps, music) is wide open; custom *engine code* per region is
  out of scope. Designers get power by composing primitives, not by
  forking the engine.

## Agnosticism rules

- **No region literals in core.** Whiteout destination, starters, rival,
  intro — currently hardcoded (e.g. whiteout warps to `"town"`) — move
  into the manifest/data. The test: grep the engine for a region string;
  every hit is a bug.
- **If it lints, it runs.** `lint` is the contract enforcer: schema-check
  the manifest/scripts, verify referential integrity (every connection,
  warp, script id, and species/move id resolves), confirm spawns are
  walkable, and reject unknown flags. A region that passes is guaranteed
  loadable.
- **The manifest declares an `engine_version`** so content and engine can
  evolve without silent breakage.

## How we proceed (proposed sequence)

1. **De-hardcode the engine.** *(done)* Region specifics now live in the
   manifest: the whiteout return point (`whiteout`, falling back to
   `start`), the starter (absent/null -> empty party), and the start map
   no longer carry engine fallbacks. The engine contains no region
   literal; lint reports a missing entry point instead of the engine
   guessing one. (This also fixed a latent bug where every region's
   whiteout warped to a literal `"town"` that does not exist in Triad.)
2. **Formalise + validate the contract.** *(done)* `pkmn/game/contract.py`
   is now the single source of truth — engine version, tile flags, map
   properties, object types, and script commands — imported by both the
   runtime and the linter, so they cannot drift. The manifest declares an
   `engine_version` the engine checks on load, and `lint` is the gate: it
   rejects unknown flags/objects/commands and bad versions on top of the
   existing referential checks. "If it lints, it runs."
3. **Seamless world primitive.** *(done)* Maps may declare per-edge
   `connect_*` + `offset_*` properties, and a recursive `World.resolve`
   stitches them into one continuous, scrolling overworld — rendering,
   collision, border fill, and seamless boundary crossing all flow through
   that one primitive, exactly as Gen 1's `get_tile` does. Discrete
   warp-linked maps are unchanged, so a region mixes both topologies per
   map. `examples/seamless` is the worked demo.
4. **Expand the tile-flag vocabulary** *(done)* Ledges (one-way two-tile
   hops), surf (water gated by `can_surf`), and cut (clearing `cuttable`
   obstacles, gated by `can_cut`) are engine behaviours keyed off tile
   flags, with capabilities granted like HMs via state flags. All three
   resolve across seamless connections too, and `examples/seamless`
   exercises each. The interaction vocabulary stays fixed and composable —
   content sets flags, the engine implements behaviour.
5. **Open the data layer fully** (region-supplied species/moves/types/
   abilities; type chart and curves as data), so a custom region is not
   tied to the bundled catalog.
6. **Conformance harness** — a "golden region" exercising every contract
   feature, with lint in CI.

Steps 1–4 are done: the backbone (de-hardcoding + a validated contract),
the headline seamless overworld, and the full field-move vocabulary
(ledges, surf, cut). Steps 5–6 (opening the data layer, a conformance
harness) remain, and none requires the Game Boy compression tricks.
