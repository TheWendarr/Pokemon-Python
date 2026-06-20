# Authoring a game

A game is a **folder of content** — no Python required. Point the
engine at it:

    python -m pkmn.game.play --game examples/isleton

Validate it any time (CI-able; exits nonzero on errors):

    python -m pkmn.cli.lint --game path/to/yourgame

The fastest start is copying `examples/isleton/` and editing. The two
generator scripts (`tools/make_assets.py`, `tools/make_example_region.py`)
show how to build content programmatically; Tiled works just as well.

## Folder layout

    yourgame/
      game.json          manifest (required)
      maps/*.tmx         Tiled maps (each needs a "ground" tile layer)
      tiles.tsx/.png     your tileset(s) — any art, any size grid of 16px tiles
      player.png         4-frame 64x16 strip: down, up, left, right
      npc.png            same format
      scripts.json       event scripts (optional)
      encounters.json    wild tables per map (optional)

## game.json

    {
      "engine_version": 1,           // contract version this region targets
      "name": "Isleton (example region)",
      "start": {"map": "isle_town", "tile": [8, 8], "facing": "down"},
      "whiteout": {"map": "isle_town", "facing": "down"},  // optional
      "starter": {"species": "totodile", "level": 14},
      "bag": {"potion": 3, "poke-ball": 5},
      "money": 800,
      "flags": [],
      "dex": ["totodile", "krabby", ...]   // optional: lint enforces it
    }

Omit `start.tile` to use the map's `spawn` object. `whiteout` is where
the player reappears after losing a battle; omit it to reuse the `start`
location (so they restart where they began). `dex` restricts
which species your content may reference — the full 649-species,
559-move, 678-item, 164-ability Gen 5 catalog is always available.
Species form names resolve from base names (`basculin` finds
`basculin-red-striped`). `starter.moves` pins the starter's moveset;
omitting `starter` (or `"starter": null`) begins with an empty party
(walking-sim mode). The engine holds no region defaults of its own: a
map name or starter the manifest does not supply is a content error the
lint reports, never something the engine guesses.

## features and settings (all optional, all default ON)

    "features": {
      "encounters": true,        // wild battles in grass
      "trainers": true,          // line-of-sight battles (off: dialogue only)
      "experience": true,        // EXP, levels, move learning
      "evolution": true,
      "move_replacement": true,  // prompt to forget a move when full
      "running": true,           // hold B to move at double speed
      "menu_party": true, "menu_bag": true, "saving": true
    },
    "settings": {"encounter_chance": 8}   // 1-in-N per grass step

Turn systems off to ship anything from a pure narrative walking sim to
a full RPG. Maps can override per-map values via Tiled *map properties*:
`weather` ("rain"|"sun"|"sandstorm"|"hail" — tints the overworld and
opens every battle there under that weather) and `encounter_chance`.

## Tiles

Tile behaviour comes from tileset properties (set them in Tiled). All are
optional; a tile with none is plain ground.

| flag | effect |
|------|--------|
| blocked | solid — cannot be entered |
| grass | tall grass — rolls a wild encounter on entry |
| surf | water — enterable only while surfing |
| cuttable | obstacle the player can clear with Cut (then walkable) |
| ledge_down / ledge_up / ledge_left / ledge_right | one-way ledge: hop over it in that direction (a two-tile jump); blocked the other way |

## Field moves and capabilities

`surf` and `cuttable` tiles are gated by *capability flags* the engine
reads from game state, granted like HMs from a script
(e.g. an NPC with `{"set_flag": "can_surf"}`) or listed in the manifest's
`flags`:

- **can_surf** — lets the player step onto `surf` water (a mount appears;
  stepping back onto land dismounts). Without it, water is impassable.
- **can_cut** — pressing the action button while facing a `cuttable`
  tile clears it for the session (it makes that tile walkable). Without
  it, the obstacle stays.

Ledges need no capability — they are pure tile behaviour: walking into a
`ledge_<dir>` tile while facing `<dir>` makes the player hop two tiles in
that direction; approached from any other side it blocks. `examples/seamless`
demonstrates all three (a ledge in *meadow*, surf water in *glade*, a
cuttable bush in *dell*).

## Seamless overworld (map connections)

By default each map is its own screen, linked by `warp` objects (doors,
stairs, caves). A map can instead be stitched to its neighbours into one
continuous, scrolling overworld by declaring *map properties* in Tiled:

| property | meaning |
|----------|---------|
| connect_north / south / east / west | neighbour map id on that edge |
| offset_north / south / east / west  | tile shift aligning the maps (Gen 1-style; may be negative) |
| border | gid of the tile filling any unconnected edge (e.g. grass) |

A connection shifts the parallel axis by the crossed map's size and the
perpendicular axis by `offset` (north/south offset moves x; east/west
offset moves y). Connections should be reciprocal — if A connects east
to B, B connects west to A — and the lint warns when they are not. Keep
the seam tiles walkable on both sides so the player can cross. Maps with
no connections stay discrete and warp-linked, so a region can mix both
topologies freely. `examples/seamless` is a worked example; see
docs/ENGINE_PHILOSOPHY.md for the design.

## Map objects (object layer)

| object  | properties |
|---------|------------|
| spawn   | — (default player position) |
| warp    | to_map, to_x, to_y, facing |
| npc     | display, facing, dialog ("line\|next page") or script, heal, visible_unless |
| sign    | dialog or script |
| trigger | script, unless_flag, when ("step" or "enter") |
| trainer | display, facing, sight, party ("krabby:7\|wingull:7@oran-berry" — `@item` equips a held item), prize, flag, before, after |

Trainers spot the player along their facing within `sight` tiles, walk
over, and battle; `flag` is set on defeat and gates rebattles.

## Script commands (scripts.json)

    say, heal, give_item {item, qty}, give_money, take_money,
    set_flag, clear_flag, if_flag {then, else},
    if_money {amount, then, else}, warp {map, x, y, facing},
    move_npc {name, to}, face_npc {name, facing}, hide_npc,
    choice {prompt, options: [{label, then}]},
    shop {items, prices?},          // prices default to catalog cost
    give_pokemon {species, level, moves?, item?},
    battle {trainer, party, prize, flag}, pc

Steps after a `battle` run only on victory. `if_flag`, `if_money`, and
`choice` branches nest arbitrarily. See `examples/triad/scripts.json`
for a flag-gated boss using all of it.

## encounters.json

    {"cove": [{"species": "krabby", "min": 5, "max": 7, "weight": 50}, ...]}

## Sprites

Battlers use real Gen 5 Black/White sprites, fetched by national dex
number and cached on disk the first time each species appears — authors
do nothing. Ship hitch-free play by pre-warming a folder's sprites:

    python -m pkmn.cli.sprites --game path/to/yourgame

Offline, or with `play.py --no-sprite-fetch`, battlers fall back to
placeholder blobs.

Overworld `player.png` / `npc.png` are your own art. The detailed
default format is a grid of 4 rows (down, up, left, right) x N walk
frames, each cell 16 wide x 24 tall (characters stand a head above the
tile and animate as they walk). The legacy 64x16 single-frame strip
still works. `tools/art.py` generates both sheets and every tile from
palette parameters -- copy a `tools/make_*` script as a starting point.

## Battle behavior

Content can reference anything in the catalog. Items/abilities without
battle hooks are inert (never crash). To add behavior, see
`pkmn/battle/passives.py` (held items, abilities),
`pkmn/datagen/mechanics.py` (bag items, balls), and the `@handler`
registry in `pkmn/battle/moves.py` — then check your coverage with
`python -m pkmn.cli.audit` and `python -m pkmn.cli.coverage`.

## Validation (the contract)

`pkmn/game/contract.py` is the single source of truth for what a region
may contain — the engine version, tile flags, map properties, object
types, and script commands. The engine and the linter both read it, so
they never disagree. Validate a region with:

    python -m pkmn.cli.lint --game examples/yourregion

The linter checks referential integrity (warps, connections, scripts,
species, items), flags unknown tile/map/object properties and unknown
commands, and verifies `engine_version`. The goal is simple: **if it
lints, it runs.**
