# Architecture

## High-level model

```
GameData (pkmn/data)          PokemonState (pkmn/core)
  reads the game folder         the ONE persistent Pokémon:
  once, caches, normalizes      species/level/IVs/EVs/nature,
  keys at the boundary          move slots with PP, HP, status
        |                                 |
        v                                 v
BattleEngine (pkmn/battle) -- wraps each PokemonState in a
  BattlePokemon (stages + volatiles), consumes Actions, emits Events.
  Pure: injected RNG, no I/O. HP/PP/status mutations go straight to
  PokemonState, so post-battle persistence is automatic.
        |
        v
Renderers (pkmn/cli, pkmn/game)
  translate the Event stream to text/animation.
```

The engine never calls back into the renderer. The renderer drives the engine by submitting `Action` objects and reading the returned `Event` list.

---

## Battle engine (`pkmn/battle/`)

### Engine state machine

`WAITING_ACTIONS → submit_turn(a1, a2) → [WAITING_REPLACEMENT → submit_replacement(side, idx)]* → ... → OVER`

The engine never blocks on input — it is equally driveable by a CLI loop, a pygame event loop, or an AI-vs-AI test harness. `legal_actions()` always reflects the current lock (charging, recharging, rampaging, choice items, Encore, Torment, Taunt, Imprison, trapping).

### Move execution

`MoveEffect` mirrors PokeAPI's move meta (ailment, chances, stat changes, drain/recoil, hit counts, healing). A single interpreter in `battle/moves.py` handles the common cases from metadata alone; special-case moves register named handlers (`@handler("rest")`). Unknown effects emit `EFFECT_SKIPPED` rather than failing silently — `pkmn-coverage` measures the gap.

### Abilities and held items (`pkmn/battle/passives.py`)

Every ability and held-item hook lives in one place: stat/power/speed modifiers, immunities and absorbs, contact punishment, switch-in effects, end-of-turn residuals, lethal-survive. `IMPLEMENTED_ABILITIES` and `IMPLEMENTED_HELD` are explicit registries — any item or ability not in these sets is inert and cannot crash the engine.

### Side and field state (`pkmn/battle/field.py`)

`SideState` holds hazards (Spikes layers, Toxic Spikes layers, Stealth Rock) and timed side conditions (Reflect, Light Screen, Safeguard, Mist, Lucky Chant, Tailwind). Whole-field conditions (Trick Room, Gravity, Magic Room, Wonder Room) live on the engine itself with countdown timers.

### Gen 5 fidelity

Implemented to Gen 5 values: 2.0× crits at 1/16 base, 85–100% damage roll, integer-floor pipeline, exact stage fractions, paralysis speed÷4 + 25% block, sleep 1–3 turns (re-rolled on re-entry), 20% thaw + defrost on fire moves, 1/8 burn and poison, ramping n/16 toxic with counter reset on switch, Gen 5 flee and capture formulas, Struggle with 1/4 max-HP recoil, Gen 5 2–5 multi-hit distribution.

Known simplifications (documented as decisions, not surprises):
- Modifier rounding uses plain floors rather than round-half-down; damage can differ by 1 in rare rolls.
- Sleep counter semantics: counter = failed turns; Rest = exactly 2.
- Capture uses 4 shake checks; no critical-capture mechanic.
- Attract ignores gender (not modeled) and always takes.
- Baton Pass sends a random able bench member; stages and passable volatiles carry over.

---

## Data pipeline (`pkmn/datagen/`, `pkmn/data/`)

`pkmn/datagen/fetch.py` builds `game/data/` from PokeAPI with two interchangeable sources:
- **REST API** (`pokeapi.co/api/v2`): each response cached in `.pokeapi_cache/`
- **CSV mirror** (`--source csv`): PokeAPI's own CSV database on GitHub — much faster for full builds

Both emit identical normalized JSON. The dataset is the complete Gen 1–5 catalog: `abilities.json` (164), `items.json` (678), per-move JSON files, and species back-dated to Gen 5 (`pokemon_types_past` restores pre-Fairy typings for 22 species; post-Gen-5 abilities are filtered out).

`pkmn/datagen/mechanics.py` merges structured bag mechanics (medicine heal/cure/revive amounts, X-item stages, ball multipliers) into `items.json` at build time — PokeAPI stores these as prose.

`GameData` (`pkmn/data/`) reads `game/data/` once, caches, and normalizes all keys at the repository boundary. `GameData.species()` resolves base names to the default form (e.g. `basculin → basculin-red-striped`), so content authors never need PokeAPI form suffixes. Anything without a registered battle effect is inert: visible, holdable, listable, but safe to ignore.

---

## Overworld and rendering (`pkmn/game/`)

### Scene stack (`pkmn/game/scene.py`)

`Game` is a shell holding a scene stack. Scenes push/pop: `OverworldScene` → `DialogScene` → `BattleScene`, etc. Input is expressed as logical actions (`a`, `b`, `up`, ...) — the pygame event pump only feeds `Input`; scenes drive themselves on `update()` and render on `draw()`. CI runs the real scene loop headless via SDL's dummy driver.

### Tilemap and world (`pkmn/game/tilemap.py`)

`TileMap` is a pytmx wrapper. All tile layers are composited in order; layers flagged `over` draw above sprites. Per-tile properties (set in the Tiled tileset) drive gameplay: `blocked`, `grass`, `surf`, `ledge_<dir>`, `block_<dir>`, `headbutt_tree`, etc. Tile size is read from the `.tmx` (`tilewidth`) rather than hard-coded.

`World` stitches seamlessly connected maps via a single recursive primitive: `World.resolve(x, y)` returns the tile at any absolute coordinate by recursing through map edges. Rendering, collision, and boundary crossing all call through `resolve` — the stitch is defined in exactly one place. Maps without connections use a simple single-map path; both topologies coexist freely.

Multi-Z layers: tile layers carry an integer `z` property. `_merged(x, y, player_z)` filters collision flags by elevation, enabling bridges and underpasses where the player's Z determines which layer they interact with.

### Overworld scene (`pkmn/game/overworld.py`)

Grid movement with pixel interpolation (so motion looks smooth at any frame rate). NPC collision + interaction, warp handling, encounter rolls, trainer line-of-sight. The surf mount, Cut clearing, Rock Smash clearing, Waterfall blocking, dark-cave overlay, day/night tinting, and seamless edge crossing all live here.

### Battle scene (`pkmn/game/battle_scene.py`)

A state machine (msg / menu / moves / bag / party) over the pure engine. The engine resolves a whole turn and returns an ordered Event list; `_enqueue` translates events into timed steps:
- `text` — message page, auto-advances; A/B skips
- `hp` — eases `disp_hp[side]` toward the event's `remaining_hp`, with hit-flash on damage
- `faint` — sinks and fades the sprite
- `send` — snaps a freshly sent-in Pokémon's bar

`disp_hp` tracks display targets independently of the engine's already-final HP values, so HP bars settle at correct intermediate values between sequential faints. Battle text comes from the same `format_event` as the CLI demo.

### Menus and game systems (`pkmn/game/menus.py`, `pkmn/game/save.py`)

Pause menu (party summary, order swap, held items, bag, Pokédex, Badges, Controls) runs as stacked scenes on top of the overworld. PC refuses to deposit your last able Pokémon. Save is atomic via `os.replace`. `GameState.to_dict()` / `from_dict()` round-trips party, PC box, bag, money, flags, vars, self-switches, badges, visited maps, and location.

### Event VM (`pkmn/game/script.py`, `pkmn/game/events.py`)

Scripts compile to an instruction list. The runner holds an instruction pointer that yields to scenes and resumes when they pop. Variables, self-switches, and flags are first-class state types; all three persist in saves. Multi-page events activate the last page whose `when` condition holds. Autorun locks the player and fires once; parallel ticks each frame without blocking input. `register_command` lets a content folder add custom commands without forking the engine.

---

## Rendering resolution and scaling

`config.py` defines `SCALE = 4` over a 256×192 design grid: `BASE_TILE = 16` is the art grid, `TILE = 64` is the on-screen tile, `LOGICAL_W/H = 1024×768` is the canvas. All geometry and font sizes derive from these constants so changing `SCALE` rescales the whole UI uniformly.

Art is authored at 16 px on disk (no regeneration when `SCALE` changes). `TileMap` upscales each tile to `TILE` at load with nearest-neighbour (cached). Gen 5 battlers (96 px) are upscaled to `SPRITE_PX` (192) via a crisp integer scale, never downscaled.

`Game._present` scales the 1024×768 canvas to the window. Default: largest integer 4:3 factor, centred. `--fill`: integer pre-scale then one gentle `smoothscale` to the exact window size. Headless mode renders 1:1.

---

## Content contract (`pkmn/game/contract.py`)

`contract.py` is the single authority for what a region may contain: `ENGINE_VERSION`, tile flags, per-map properties, object types, script commands, weather names, capability flags, and the `FEATURES` / `SETTINGS` key sets. Both the runtime and the linter import these constants — they can never drift. `compatible(version)` implements the major-version compatibility rule. `Game` checks `engine_version` on load; `pkmn-lint` rejects unknown flags, objects, and commands in addition to referential checks. "If it lints, it runs" is a real guarantee because the validator and the engine share the same spec.

---

## Default art and tooling (`tools/`)

`tools/art.py` is the shared art library all bundled regions draw from. It provides shaded tile painters (grass, path, water, sand, tree, rock, flower, sign, fence, roof, floor, cave wall, and more) parameterized by palette, and `character_sheet(...)` which renders a 4-direction × 4-frame walk cycle (outline, 3-tone shading, swinging arms, striding legs, head-bob, ground shadow). Character sheets are 4 rows (down, up, left, right) × N columns, cells 16×24; the engine auto-detects this format against the legacy 64×16 single-frame strip.

`tools/make_assets.py`, `tools/make_example_region.py` — procedurally generate tilesets and maps; the repo ships no third-party art.

`tools/rmxp2kanto.py` — converts RMXP/Essentials PBS + TMX data to the engine's format, emitting autotile frames, per-method encounter tables, and directional flags. A promoted version of this tool is planned for 1.x (see [PLANNED.md](../PLANNED.md)).

---

## Sprite cache (`pkmn/game/sprites.py`)

`pkmn/game/sprites.py` resolves a species' national dex number to a Gen 5 Black/White sprite from `github.com/PokeAPI/sprites`, caching under `.sprite_cache/gen5/{front,back}/{dex}.png`. `Assets.battler(species_id, name, dex=, back=)` loads the cached sprite, scales to `SPRITE_PX` (192), memoizes per `(species, back)`, and falls back to a procedural blob when unavailable.

Fetching is opt-in (`sprites.FETCH_ENABLED`, on by `play.py` and the sprites CLI, force-off via `PKMN_NO_SPRITE_FETCH`). The test suite never touches the network. `.sprite_cache/` is in `.gitignore` — the repo ships no third-party sprites.
</content>
</invoke>