# Authoring a game

> **Where this fits.** The content-folder format documented here is the
> *base* authoring layer: a simple region needs no engine code. The
> project's goal is full RPG Maker XP + Essentials parity authored in pure
> Python (see `docs/ROADMAP.md`), so this format is being extended — a
> richer event model (variables, self-switches, common events, move routes)
> and a Python authoring API for events are the next major track. The format
> below is stable and current; treat it as the foundation, not the ceiling.

A game is a **folder of content** — a simple region needs no engine code.
Point the engine at it:

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

## features and settings (all optional; most default ON)

    "features": {
      "encounters": true,        // wild battles in grass
      "trainers": true,          // line-of-sight battles (off: dialogue only)
      "experience": true,        // EXP, levels, move learning
      "evolution": true,
      "move_replacement": true,  // prompt to forget a move when full
      "running": true,           // hold B to move at double speed
      "menu_party": true, "menu_bag": true, "saving": true,
      "pokedex": true, "controls": true,
      "badges": false,           // Badge display in pause menu (default OFF)
      "fly": false               // Fly/Town Map scene in pause menu (default OFF;
                                 //   requires can_fly flag and fly_name on maps)
    },
    "settings": {
      "encounter_chance": 8,     // 1-in-N per grass step
      "audio_volume": 0.7,       // master (0..1)
      "music_volume": 0.6, "sfx_volume": 0.8,
      "midi": false,             // play external .mid files (see Audio)
      "daynight": "auto"         // "auto" (clock) | "off" | a phase name
    }

Turn systems off to ship anything from a pure narrative walking sim to
a full RPG. Maps can override per-map values via Tiled *map properties*:

| map property | meaning |
|---|---|
| weather | `"rain"`, `"sun"`, `"sandstorm"`, or `"hail"` — tints the overworld and opens every battle under that weather |
| encounter_chance | 1-in-N chance per grass/surf step (overrides the manifest setting) |
| music | track name for this map |
| battle_bg | battle backdrop: `"field"` (default), `"forest"`, `"cave"`, `"water"`, `"sand"`, `"snow"`, `"mountain"`, `"indoor"` |
| border | GID of the tile filling unconnected edges on a seamless map |
| heal_point | JSON `{"map": "id", "tile": [x, y]}` — whiteout respawn for this map (overrides manifest `whiteout`) |
| escape_point | JSON `{"map": "id", "tile": [x, y]}` — Escape Rope destination for this map |
| dark_cave | `true` — renders a pitch-black overlay with a lit radius around the player; `can_flash` lifts it and halves the encounter rate |
| fly_name | display name shown in the Fly / Town Map scene; only maps that declare this appear as Fly destinations |

**Day/night.** Phases — morning / day / evening / night — come from the
system clock and apply a subtle tint to the overworld and the battle
backdrop. The `daynight` setting picks the source: `"auto"` follows the
clock, `"off"` disables tinting (always day), and a phase name pins one
phase. `python -m pkmn.game.play --time auto|off|<phase>|<hour 0-23>`
overrides it at launch. Triggers take an optional `time` property (a
comma-separated phase list) so an event can be day- or night-only.

## Tiles

Tile behaviour comes from tileset properties (set them in Tiled). All are
optional; a tile with none is plain ground.

| flag | effect |
|------|--------|
| blocked | solid — cannot be entered |
| grass | tall grass — rolls a wild encounter on entry |
| surf | water — enterable only while surfing |
| cuttable | obstacle the player can clear with Cut (then walkable) |
| rock_smash | boulder the player can clear with Rock Smash (then walkable) |
| waterfall | surf tile that also blocks upward movement without can_waterfall |
| headbutt_tree | tree that rolls the map's `headbutt` encounter table when pressed with can_headbutt |
| ledge_down / ledge_up / ledge_left / ledge_right | one-way ledge: hop over it in that direction (a two-tile jump); blocked the other way |
| block_down / block_up / block_left / block_right | directional partial passability: blocks movement crossing that edge only |

## Field moves and capabilities

Certain tile types are gated by *capability flags* the engine reads from
game state. Grant them like HMs — from a script (`{"set_flag": "can_surf"}`)
or by listing them in the manifest's `flags` array:

| capability | effect |
|---|---|
| can_surf | lets the player step onto `surf` water tiles; a surf mount renders underneath |
| can_cut | pressing A while facing a `cuttable` tile clears it for the session |
| can_rock_smash | pressing A while facing a `rock_smash` tile clears it for the session |
| can_waterfall | allows upward movement onto `waterfall` tiles while surfing |
| can_headbutt | pressing A while facing a `headbutt_tree` rolls that map's `headbutt` encounter table |
| can_flash | halves the wild encounter rate; also illuminates `dark_cave` maps |
| can_fly | opens the Fly / Town Map scene from the pause menu (requires `"fly": true` in features) |
| can_strength | reserved for push-able `strength_block` boulders (tile type forthcoming) |
| can_dive | reserved for underwater dive tiles (forthcoming) |

Ledges need no capability — they are pure tile behaviour: walking into a
`ledge_<dir>` tile while facing `<dir>` makes the player hop two tiles in
that direction; approached from any other side it blocks. `examples/seamless`
demonstrates surf in *glade*, a ledge in *meadow*, a cuttable bush in *dell*,
and Rock Smash / waterfall / headbutt_tree tiles in *rock*.

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
| trigger | script, unless_flag, when ("step" or "enter"), time (phase list, e.g. "night,evening") |
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

## Audio

The engine **synthesizes all audio procedurally at runtime** (numpy ->
pygame.mixer) — chiptune cries, sound effects, and music — so audio files
are entirely optional. Every species gets a unique cry seeded by its dex
number, the same way the renderer falls back to procedural sprites.

What plays where, automatically: a map's `music` property (default
`route`) sets the field track; wild battles use `battle_wild`, trainer
battles `battle_trainer`, a win plays `victory`; cries fire on send-out,
and SFX cover hits, faints, the catch sequence, healing, level-ups,
bumping into walls, starting and advancing dialogue, menu cursor moves,
and saving. Built-in songs: `title`, `town`, `route`, `battle_wild`,
`battle_trainer`, `victory`, `heal`.

**Bring your own audio.** Drop files in `<game>/audio/music/<name>.<ext>`
and they override the synth for that track. `.ogg`/`.mp3`/`.wav` play
out of the box. `.mid` files play only when you set `"midi": true` in
settings — SDL/pygame MIDI playback depends on a system soft-synth /
soundfont and can fail *silently*, so the robust synth is the default.
To start from the built-in tunes as editable MIDI:

    python -m pkmn.cli.audio --export-midi          # -> game/assets/audio/music
    python -m pkmn.cli.audio --list                 # songs + SFX names
    python -m pkmn.cli.audio --render-wav out/wav    # audition as .wav

Volumes live in `settings` (`audio_volume`, `music_volume`, `sfx_volume`);
`--mute` (or a device-less / headless host) disables audio safely.

## Controls (key bindings)

Input is expressed as logical *actions*, so the physical keys are fully
configurable. The actions are **Up, Down, Left, Right, Confirm, Cancel,
Start, Select**. Defaults: arrows or WASD move; Confirm = Z / Space;
Cancel = X / Backspace / Escape; Start = Enter; Select = right shift.
(F11 toggles fullscreen and is reserved.)

Players remap keys in-game from the pause menu's **CONTROLS** screen —
pick an action, press the new key (Esc aborts), or choose *Reset to
defaults*. Changes save immediately to the bindings file
(`controls.json` by default; `python -m pkmn.game.play --controls PATH`
to relocate it). The file is plain JSON mapping each action to one or
more pygame key names, so it can also be hand-edited:

    {"a": ["z", "space"], "b": ["x", "escape"], "up": ["up", "w"],
     "start": ["return"], "select": ["right shift"]}

(Internally Confirm is `a` and Cancel is `b`.) An action present with an
empty list is left unbound; an omitted action keeps its default.

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

## Event runtime (Phase 8)

Scripts in `scripts.json` (or built with the Python API) are command lists
run by a compiled VM. State has three kinds: **flags** (booleans),
**vars** (integers), and **self-switches** (per-event booleans, the "did
this once" backbone). All three persist in saves.

**Conditions** (used by `if`, `while`, and event pages) are dicts:
`{"flag": n}`, `{"var": n, "op": ">=", "value": k}`, `{"self_switch": "A"}`,
`{"item": id, "qty": k}`, `{"money": k}`, `{"badge": "name"}`,
`{"badge_count": 1, "op": ">=", "value": n}`, `{"visited": "map_id"}`,
`{"not": c}`, `{"all": [..]}`, `{"any": [..]}`.

**Commands.** Dialogue/flow: `say`, `wait` (frames), `choice`, `shop`,
`pc`, `battle`. State: `heal`, `give_item`, `give_money`, `take_money`,
`set_flag`, `clear_flag`, `give_badge`, `set_var`, `add_var`,
`set_self_switch`, `clear_self_switch`, `give_pokemon`. Control flow:
`if`/`then`/`else`, `if_flag`/`if_money`/`if_var`/`if_self_switch`,
`while`/`do`, `label`, `goto`. World/NPC: `warp`, `move_npc`,
`move_route`, `face_npc`, `hide_npc`, `screen`.

`then`/`else` are top-level on `if`/`if_flag` but nested in the payload for
`if_money`/`if_var`/`if_self_switch` (matching legacy content).

**Triggers** (map trigger object `when`): `step`, `enter`, `autorun`
(locks the player; a spawn-map autorun fires once the scene is active),
`parallel` (non-blocking, ticked each frame). Gate one-shot autoruns with
the trigger's `unless_flag`, or set a self-switch inside.

**Multi-page events.** A script id may resolve to
`{"pages": [{"when": <cond>, "do": [...]}, ...]}`; the runtime runs the
**last** page whose `when` holds. Example — a Professor who hands out a
starter exactly once:

```json
{"pages": [
  {"when": {"not": {"self_switch": "A"}},
   "do": [{"say": "Take this!"},
          {"give_pokemon": {"species": "charmander", "level": 5}},
          {"set_self_switch": "A"}]},
  {"when": {"self_switch": "A"}, "do": [{"say": "How is it doing?"}]}
]}
```

**Python authoring** (`pkmn/game/events.py`) builds the same command dicts:

```python
from pkmn.game.events import Event, var, self_switch

prof = Event.pages([
    page(~self_switch("A"),
         Event().say("Take this!")
                .give_pokemon("charmander", level=5)
                .set_self_switch("A")),
    page(self_switch("A"), Event().say("How is it doing?")),
])

puzzle = (Event()
    .set_var("x", 0)
    .while_(var("x") < 3, Event().add_var("x", 1))
    .if_(var("x") >= 3, Event().say("Solved!"))
    .build())
```

**Extending the runtime.** Register a custom command without forking:

```python
from pkmn.game.script import register_command
register_command("quake", lambda runner, payload: runner.ow.shake(payload))
```

See `examples/eventlab` for a small playable map using autorun, a
multi-page NPC, a parallel move-route, and a while/if puzzle.

## Wild encounters (multi-method)

`encounters.json` maps a map id to either a flat list (legacy = the `land`
table) or per-method tables:

```json
{"route_1": {
  "land":      [{"species": "pidgey", "min": 2, "max": 5, "weight": 45}],
  "surf":      [{"species": "tentacool", "min": 5, "max": 40, "weight": 100}],
  "old_rod":   [{"species": "magikarp", "min": 5, "max": 10, "weight": 70}],
  "good_rod":  [{"species": "krabby", "min": 10, "max": 20, "weight": 60}],
  "super_rod": [{"species": "staryu", "min": 15, "max": 25, "weight": 40}]
}}
```

Methods: `land` (walking on grass), `surf` (rolled each step while
surfing), `old_rod`/`good_rod`/`super_rod` (press A facing water holding the
rod item — `old-rod`/`good-rod`/`super-rod` in the bag; the best rod owned
is used), plus `rock_smash`, `headbutt`, and `cave` (schema + importer
support; their field triggers arrive with those moves).

## Rich trainer parties

A `battle` command's (or trainer's) `party` may be the compact string
`"species:level@item|species:level"` or a full per-mon list:

```json
{"battle": {"trainer": "Champion", "party": [
  {"species": "gengar", "level": 58, "nature": "timid", "ability": "levitate",
   "item": "black-sludge",
   "moves": ["shadow-ball", "sludge-bomb", "thunderbolt", "destiny-bond"],
   "ivs": {"speed": 31}}
]}}
```
