# Authoring Guide

A game is a **folder of content** — a simple region needs no engine code.
Point the engine at it and it runs; validate it any time with the linter.

```bash
python -m pkmn.game.play --game path/to/yourgame
python -m pkmn.cli.lint --game path/to/yourgame   # exits nonzero on errors
```

The fastest start is copying `examples/isleton/` and editing from there.
`tools/make_assets.py` and `tools/make_example_region.py` show how to
generate content programmatically; Tiled works just as well for maps.

---

## Folder layout

```
yourgame/
  game.json          manifest (required)
  maps/*.tmx         Tiled maps (each needs a "ground" tile layer)
  tiles.tsx/.png     your tileset(s) — any art, 16px tile grid
  player.png         4-row × N-frame walk sheet (down, up, left, right; 16×24 cells)
  npc.png            same format; any number of named NPC sheets
  scripts.json       event scripts (optional)
  encounters.json    wild tables per map (optional)
  audio/music/       .ogg/.mp3/.wav files override the procedural synth tracks
```

---

## game.json — manifest

```json
{
  "engine_version": "0.9",
  "name": "Isleton (example region)",
  "start":    {"map": "isle_town", "tile": [8, 8], "facing": "down"},
  "whiteout": {"map": "isle_town", "facing": "down"},
  "starter":  {"species": "totodile", "level": 14, "moves": ["water-gun", "scratch"]},
  "bag":      {"potion": 3, "poke-ball": 5},
  "money":    800,
  "flags":    [],
  "dex":      ["totodile", "krabby", "wingull"]
}
```

| Key | Notes |
|-----|-------|
| `engine_version` | Pin to the engine release you target (e.g. `"0.9"`). A mismatch is a hard error at startup. |
| `start.tile` | Omit to use the map's `spawn` object. |
| `whiteout` | Respawn after loss. Omit to reuse `start`. |
| `starter` | Omit `moves` for last-four level-up moves. `null` → empty party (walking-sim mode). |
| `dex` | Restricts which species your content may reference. Omit to allow the full 649-species catalog. |

---

## features and settings

All optional. Most features default `true`; most settings have sensible defaults.

```json
"features": {
  "encounters":       true,
  "trainers":         true,
  "experience":       true,
  "evolution":        true,
  "move_replacement": true,
  "running":          true,
  "menu_party":       true,
  "menu_bag":         true,
  "saving":           true,
  "pokedex":          true,
  "controls":         true,
  "badges":           false,
  "fly":              false
},
"settings": {
  "encounter_chance": 8,
  "audio_volume":     0.7,
  "music_volume":     0.6,
  "sfx_volume":       0.8,
  "midi":             false,
  "daynight":         "auto"
}
```

`badges: true` adds a Badge screen to the pause menu.
`fly: true` adds the Fly / Town Map scene (requires `can_fly` flag and `fly_name` on maps).
`daynight`: `"auto"` follows the system clock, `"off"` disables tinting, a phase name pins one phase.
Override `daynight` at launch: `--time auto|off|morning|day|evening|night|<hour 0-23>`.

---

## Map properties (set in Tiled)

| Property | Meaning |
|----------|---------|
| `weather` | `"rain"`, `"sun"`, `"sandstorm"`, or `"hail"` — tints the overworld and opens battles under that weather |
| `encounter_chance` | 1-in-N per grass/surf step (overrides manifest setting) |
| `music` | track name for this map |
| `battle_bg` | battle backdrop: `"field"` (default), `"forest"`, `"cave"`, `"water"`, `"sand"`, `"snow"`, `"mountain"`, `"indoor"` |
| `border` | GID of the tile filling unconnected edges on a seamless map |
| `heal_point` | JSON `{"map": "id", "tile": [x, y]}` — whiteout respawn for this map |
| `escape_point` | JSON `{"map": "id", "tile": [x, y]}` — Escape Rope destination |
| `dark_cave` | `true` — pitch-black overlay with lit radius; `can_flash` lifts it and halves encounter rate |
| `fly_name` | Display name in the Fly / Town Map scene. Only maps with this appear as Fly destinations. |

---

## Tile flags (set in Tiled per-tile)

A tile with no flags is plain walkable ground.

| Flag | Effect |
|------|--------|
| `blocked` | Solid — cannot be entered |
| `grass` | Tall grass — rolls a wild encounter on entry |
| `surf` | Water — enterable only while surfing |
| `cuttable` | Cleared by Cut (`can_cut`), then walkable for the session |
| `rock_smash` | Cleared by Rock Smash (`can_rock_smash`), then walkable |
| `waterfall` | Surf tile that blocks upward movement without `can_waterfall` |
| `headbutt_tree` | Rolls the map's `headbutt` encounter table when A is pressed with `can_headbutt` |
| `ledge_down / _up / _left / _right` | One-way ledge: hop two tiles in that direction; blocked from any other side |
| `block_down / _up / _left / _right` | Directional partial passability: blocks only the edge on that side |

---

## Field move capabilities

Grant via script (`{"set_flag": "can_surf"}`) or in the manifest's `flags` array.

| Capability | Effect |
|------------|--------|
| `can_surf` | Lets the player step onto `surf` tiles; a surf mount renders underneath |
| `can_cut` | A while facing a `cuttable` tile clears it for the session |
| `can_rock_smash` | A while facing a `rock_smash` tile clears it for the session |
| `can_waterfall` | Allows upward movement onto `waterfall` tiles while surfing |
| `can_headbutt` | A while facing a `headbutt_tree` rolls the map's `headbutt` encounter table |
| `can_flash` | Halves encounter rate; illuminates `dark_cave` maps |
| `can_fly` | Opens the Fly / Town Map scene from the pause menu (`"fly": true` in features required) |
| `can_strength` | Reserved — push-able `strength_block` boulders (forthcoming) |
| `can_dive` | Reserved — underwater dive tiles (forthcoming) |

Ledges need no capability — they are pure tile behavior.

---

## Map objects (object layer)

| Object | Required properties |
|--------|---------------------|
| `spawn` | — (default player start position) |
| `warp` | `to_map`, `to_x`, `to_y`, `facing` |
| `npc` | `display`, `facing`; one of `dialog` (`"line\|next page"`) or `script`; optional: `heal`, `visible_unless` |
| `sign` | `dialog` or `script` |
| `trigger` | `script`, optional: `unless_flag`, `when` (`"step"` or `"enter"`), `time` (phase list e.g. `"night,evening"`) |
| `trainer` | `display`, `facing`, `sight`, `party` (`"krabby:7\|wingull:7@oran-berry"`), `prize`, `flag`, optional: `before`, `after` |

Trainers spot the player along their facing within `sight` tiles, walk over, and battle.
`flag` is set on defeat to gate rematches.

---

## Seamless overworld (map connections)

Maps can be stitched into a continuous scrolling overworld using Tiled map properties:

| Property | Meaning |
|----------|---------|
| `connect_north / south / east / west` | Neighbour map id on that edge |
| `offset_north / south / east / west` | Tile shift aligning the maps (may be negative) |
| `border` | Tile GID filling any unconnected edge |

Connections should be reciprocal — the linter warns if they are not.
Maps with no connections stay discrete and warp-linked. Both topologies coexist freely.
See `examples/seamless` for a worked example.

---

## Script commands (scripts.json)

Scripts are command lists run by a compiled VM. All state persists in saves.

**Dialogue / UI**
`say`, `choice {prompt, options: [{label, then}]}`, `shop {items, prices?}`, `pc`, `wait`

**State mutation**
`heal`, `give_item {item, qty}`, `give_money`, `take_money`, `give_pokemon {species, level, moves?, item?}`,
`set_flag`, `clear_flag`, `give_badge`, `set_var`, `add_var`, `set_self_switch`, `clear_self_switch`

**Control flow**
`if / then / else`, `if_flag`, `if_money`, `if_var`, `if_self_switch`,
`while / do`, `label`, `goto`

**World / NPC**
`warp {map, x, y, facing}`, `move_npc {name, to}`, `face_npc {name, facing}`, `hide_npc`,
`move_route`, `screen`, `battle {trainer, party, prize, flag}`

Steps after a `battle` command run only on victory.

---

## Conditions (used by `if`, `while`, and multi-page events)

```json
{"flag": "name"}
{"var": "x", "op": ">=", "value": 3}
{"self_switch": "A"}
{"item": "potion", "qty": 1}
{"money": 500}
{"badge": "boulder"}
{"badge_count": 1, "op": ">=", "value": 4}
{"visited": "map_id"}
{"not": {"flag": "x"}}
{"all": [...]}
{"any": [...]}
```

---

## Event triggers (map trigger object `when`)

| When | Behavior |
|------|----------|
| `step` | Fires each time the player steps on the tile |
| `enter` | Fires once on map entry |
| `autorun` | Locks the player; fires once when the scene is active |
| `parallel` | Non-blocking; ticked each frame in the background |

Gate one-shot autoruns with the trigger's `unless_flag`, or set a self-switch inside.

---

## Multi-page events

A script id may resolve to a page list. The runtime runs the **last** page whose `when` holds:

```json
{"pages": [
  {"when": {"not": {"self_switch": "A"}},
   "do": [{"say": "Take this!"},
          {"give_pokemon": {"species": "charmander", "level": 5}},
          {"set_self_switch": "A"}]},
  {"when": {"self_switch": "A"}, "do": [{"say": "How is it doing?"}]}
]}
```

---

## Python authoring API

```python
from pkmn.game.events import Event, var, self_switch, page

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

Register custom commands without forking:

```python
from pkmn.game.script import register_command
register_command("quake", lambda runner, payload: runner.ow.shake(payload))
```

See `examples/eventlab` for autorun, multi-page NPCs, parallel move-routes, and puzzles.

---

## Wild encounters (encounters.json)

```json
{"route_1": {
  "land":      [{"species": "pidgey",    "min": 2,  "max": 5,  "weight": 45}],
  "surf":      [{"species": "tentacool", "min": 5,  "max": 40, "weight": 100}],
  "old_rod":   [{"species": "magikarp",  "min": 5,  "max": 10, "weight": 70}],
  "good_rod":  [{"species": "krabby",    "min": 10, "max": 20, "weight": 60}],
  "super_rod": [{"species": "staryu",    "min": 15, "max": 25, "weight": 40}]
}}
```

Methods: `land` (walking on grass), `surf` (each step while surfing),
`old_rod` / `good_rod` / `super_rod` (press A facing water with the rod item),
plus `rock_smash`, `headbutt`, and `cave`.
A flat list (no method keys) is treated as `land`.

---

## Rich trainer parties

The `party` field accepts a compact string or a full per-Pokémon list:

```json
{"battle": {"trainer": "Champion", "party": [
  {"species": "gengar", "level": 58, "nature": "timid", "ability": "levitate",
   "item": "black-sludge",
   "moves": ["shadow-ball", "sludge-bomb", "thunderbolt", "destiny-bond"],
   "ivs": {"speed": 31}}
]}}
```

Compact: `"krabby:7|wingull:7@oran-berry"` — `species:level@held-item`, `|` separates slots.

---

## Sprites and art

Battle sprites are real Gen 5 Black/White front/back sprites, fetched on first sight
and cached locally. Pre-warm a folder's sprites before distributing:

```bash
python -m pkmn.cli.sprites --game path/to/yourgame
```

Offline or with `--no-sprite-fetch`, the engine falls back to procedural placeholder blobs.

Overworld sprites (`player.png`, `npc-*.png`) are your own art. Format: a grid of
4 rows (down, up, left, right) × N walk-frames, cells 16 wide × 24 tall. The legacy
single-row 64×16 strip still works. `tools/art.py` generates both sheets from palette
parameters — copy a `tools/make_*` script as a starting point.

---

## Audio

All audio is synthesized procedurally at runtime (numpy → pygame.mixer), so no audio
files are required. Drop files in `<game>/audio/music/<name>.<ext>` to override any
built-in track for that game. `.ogg`, `.mp3`, and `.wav` play out of the box. `.mid`
plays only with `"midi": true` in settings (requires a system soft-synth).

Built-in songs: `title`, `town`, `route`, `battle_wild`, `battle_trainer`, `victory`, `heal`.

```bash
python -m pkmn.cli.audio --export-midi          # export MIDI versions to edit
python -m pkmn.cli.audio --list                 # list all song and SFX names
python -m pkmn.cli.audio --render-wav out/wav   # audition as .wav
```

---

## Controls

Input is expressed as logical actions — fully rebindable in-game from the CONTROLS
screen in the pause menu, or by editing `controls.json`.

Defaults: arrows / WASD move; Z / Space confirm; X / Backspace / Escape cancel;
Enter = Start; Right Shift = Select. F11 toggles fullscreen (reserved).

```json
{"a": ["z", "space"], "b": ["x", "escape"], "up": ["up", "w"],
 "down": ["down", "s"], "left": ["left", "a"], "right": ["right", "d"],
 "start": ["return"], "select": ["right shift"]}
```

Override the bindings file path: `--controls PATH`.

---

## Validation

`pkmn/game/contract.py` is the single source of truth for what a region may contain.
The linter and runtime both read it — they can never disagree.

```bash
pkmn-lint --game path/to/yourgame
```

The linter checks referential integrity (warps, connections, scripts, species, items,
moves), flags unknown tile/map/object properties and commands, and verifies
`engine_version`. **If it lints, it runs.**

---

## Keeping private content out of this repository

The engine is open-source; your game content (especially anything derived from
Game Freak / Nintendo IP) must be kept in a separate private repository.

**Recommended structure:**

```
~/code/
  pokemon-python/        ← this repo (public, MIT-licensed)
  my-game/               ← your content (private git repo)
    game.json
    maps/
    sprites/
    tiles/
    audio/
    scripts.json
    encounters.json
```

Run from source: `python -m pkmn.game.play --game ../my-game`
Run from installed package: `pkmn-play --game /path/to/my-game`

**Add a launcher to your content repo** so you don't type the path every time:

```python
# my-game/play.py
import subprocess, sys, pathlib
here = pathlib.Path(__file__).parent
subprocess.run([sys.executable, "-m", "pkmn.game.play",
                "--game", str(here), "--save", str(here / "save.json"),
                *sys.argv[1:]])
```

**Pin the engine version** in `game.json` (`"engine_version": "0.9"`) and review
`CHANGELOG.md` when you update the engine.

**`local/` safety net.** The engine's `.gitignore` excludes `local/`. You may place
a content folder at `pokemon-python/local/my-game/` for quick experiments — it will
never be staged or committed. A separate repo is recommended for long-term work.

**Never:**
- Add your private content folder as a git submodule of this repo
- Symlink content into `examples/` (CI runs the linter over that directory)
- Commit sprite downloads (`game/data/sprites/`) — they are in `.gitignore`

**IP reminder.** The MIT license governs the engine source only. Game Freak /
Nintendo artwork, music, map data, and other assets are their respective owners'
IP and must not be redistributed. Fan-game distribution operates in a legal grey
area; no commercial use, and remove promptly if requested.
