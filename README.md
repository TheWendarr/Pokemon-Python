# pokemon-python

A Gen 4/5-style Pokemon engine and game-authoring toolkit, written in
Python. Ground-up rewrite — the original prototype's code was used as
inspiration only.

## Project direction

**The goal is to reliably reproduce the full functionality of RPG Maker XP
+ Pokémon Essentials, delivered as pure Python** — so anyone can build a
complete Pokémon game using only Python and editable content folders, with
no RPG Maker, no Ruby, and no proprietary editor.

Three co-equal goals drive the design:

1. **Parity** — Essentials is the functional target; where it has a
   capability we don't, that's a gap to close.
2. **Modularity** — the engine is a set of independently usable, swappable
   subsystems (data, battle, overworld, event runtime, rendering, audio)
   behind stable interfaces.
3. **Pure-Python authoring** — make games by writing Python and editing
   content folders; events are expressible as data *and* as a Python API.

Simplicity is still a value, but as a standard for *how each module is
built*, not as a cap on what the engine can do. The capability roadmap,
effort estimates, and sequencing live in **`docs/ESSENTIALS_COMPAT.md`**;
the design rationale is in **`docs/ENGINE_PHILOSOPHY.md`**. The sections
below describe what works today.

**Data: the full PokeAPI Gen 1-5 catalog.** `game/data/` now carries
every species (649), every move (559, B2W2 values), every ability (164,
with effect text), and every Gen 1-5 item (678, with categories, flags,
and effect text) — built by `python -m pkmn.datagen.fetch` from either
pokeapi.co (cached REST, the default at home) or PokeAPI's CSV mirror
(`--source csv`). Anything in the catalog can be referenced by maps,
trainers, or scripts with no pipeline work; battle behavior is layered
on top (`pkmn/battle/passives.py` for held items/abilities,
`pkmn/datagen/mechanics.py` for bag items and balls), and
`python -m pkmn.cli.audit` reports exactly what is implemented versus
data-only and cross-validates every reference.

**High-resolution, crisp rendering.** The game renders at a high native
resolution -- a 256x192 design grid scaled 4x to a 1024x768 canvas with
64px tiles -- so text and sprites are drawn with enough real pixels to
stay sharp, and the final scale to the window is gentle (1:1 on a 1080p
screen). Art is authored at 16px and upscaled once at load, and Gen 5
battlers are *upscaled* rather than shrunk, so nothing is blurred by a
lossy downscale. The default window is pixel-perfect (integer scaling,
4:3, centered); `--fill` fills the screen with clean sharp-bilinear
scaling, and `--fullscreen` (or F11) runs at native resolution. To raise
or lower the whole render resolution, change `SCALE` in
`pkmn/game/config.py`.

**Detailed default art + walking animation.** The bundled regions use a
shared procedural art library (`tools/art.py`): shaded, textured 16x16
tiles (grass with blades, rippled water, layered tree canopies, brick
walls, shingled roofs, dunes, reeds) and a 4-direction, 4-frame animated
character walk-cycle that strides as you move. Sprite sheets are a grid
(4 rows of facings x N walk frames, 16x24 cells so characters stand a
head above their tile); the loader still accepts the old 64x16 strips.
Regenerate any region's art with its `tools/make_*` script.

**Sequenced battle animations.** Turns play out beat by beat instead
of all at once: the first mover lunges as its move text shows, the
target's HP bar drains with a hit-flash, any "super effective!" line
follows, then the second mover repeats, and fainted Pokemon sink and
fade away. Text stays aligned with the action and auto-advances after a
readable beat; tap A/B to skip ahead.

**Real Gen 5 sprites, cached.** Species battlers are the authentic
Black/White front (foe) and back (player) sprites, pulled from the
PokeAPI sprite repository on first sight and cached on disk by national
dex number — every later load is a pure disk read. Pre-warm a game's
sprites so play is hitch-free with `python -m pkmn.cli.sprites --game
examples/triad` (or `--all` for the full dex). Fully offline (or with
`--no-sprite-fetch`), the engine falls back to its hashed-hue
placeholder blobs, so it always runs. Overworld characters stay
procedural.

**Showcase: the Triad region.** `python -m pkmn.game.play --game
examples/triad` — three themed cities on a triangle of three distinct
routes: the Canopy Path's bug catchers and hidden items, the rain-soaked
Shoreline Run (per-map weather that carries into every battle), and the
sandstorm-scoured Mirage Crossing with its flag-gated ranger roadblock.
Shops with real catalog prices, a choice-driven gift Frillish, trainers
with held items, and a Sheriff finale locked behind both wardens.
Designers control everything from the manifest: feature toggles strip
the engine down to a walking sim or up to a full RPG, starters come
with chosen movesets, and hold B to run.

**Phase 6 status: authoring toolkit.** Games are content folders: a
`game.json` manifest plus Tiled maps, your own tileset and sprites,
scripts, and encounter tables — a simple region needs no engine code at
all. Run any folder with `python -m pkmn.game.play --game DIR`, validate it
with `python -m pkmn.cli.lint --game DIR`, and see `docs/AUTHORING.md` for
the full format. `examples/isleton` is a complete second region built only
with the toolkit. (Toward the parity goal, this format is the *base* layer;
a Python authoring API and a full event runtime — variables, self-switches,
common events, move routes — are the next major track, see
`docs/ESSENTIALS_COMPAT.md`.)

**Phase 5 status: game systems.** Press Enter for the pause menu:
party (with summaries, order swapping, and giving/taking held items),
bag (use medicine on any member), and save. Your team earns EXP on every knockout, levels up,
learns moves, and evolves after battle; catches beyond six go to the
PC box on the clinic terminal. `python -m pkmn.game.play` now resumes
from `save.json` automatically (`--save` to change the path).
Controls (all rebindable): arrows/WASD move, Z/Space confirm, X/Esc
cancel, Enter for the menu, right-shift select. Remap any key in-game
from the pause menu's CONTROLS screen (saved to `controls.json`; use
`--controls PATH` to relocate it), or hand-edit that JSON.

**Phase 4 status: events & scripting.** Route 1 now has a scripted
rival ambush (Hugh and his Snivy), a line-of-sight trainer in the tall
grass, and the Hexton clinic interior where Nurse Hazel heals via an
event script. Game logic is data: triggers and NPCs in the Tiled maps
reference JSON scripts (`game/assets/scripts.json`) with a small
command set (dialogue, battles, items, money, flags, warps, NPC
movement), and progress flags gate every trigger and dialogue branch.

**Day/night cycle.** A clock-driven cycle tints the overworld and battle
backdrops through morning, day, evening, and night. It is configurable per
region (the `daynight` setting) or at launch with `--time`
(`auto`/`off`/a phase/an hour), and map triggers can be gated to specific
phases — so an event or encounter can be night-only.

**Phase 3 status: playable overworld.** `python -m pkmn.game.play`
opens a Pygame-CE window: walk Hexton town, head north into Route 1's
tall grass, and fight or catch wild Pokemon with a full battle UI.
Arrows/WASD move, Z/Enter confirms, X/Esc cancels. Requires
`pip install pygame-ce pytmx`; regenerate placeholder art and Tiled
maps any time with `python tools/make_assets.py`.

**Phase 2 status: battle completeness.** Everything from Phase 1 (full
Gen 5 damage model, statuses, stages, priority ordering, PP/Struggle,
switching, items, fleeing, catching) plus abilities, held items,
weather, entry hazards, screens, Protect, two-turn/recharge/rampage
moves, trapping, and ~50 special-case move handlers — pure,
deterministic, covered by 91 tests, with a 3.6% unimplemented-effect
rate across the full Gen 5 movepool (`python -m pkmn.cli.coverage`).
See `docs/ROADMAP.md` for what comes next.

## Play this first

**Start here:** the Triad region is the showcase — three themed cities, five
trainer battles, fishing, scripted events, and a flag-gated finale.

```bash
# from a clean clone
pip install -e ".[dev]"
python -m pkmn.game.play --game examples/triad
```

Arrow keys / WASD to move · Z / Space to confirm · X / Esc to cancel ·
Enter for the pause menu (party, bag, save, Pokédex, controls).

> **IP note:** This engine ships zero Nintendo assets. Downloading sprites
> with `pkmn-sprites` or `pkmn-fetch-data --sprites` is for personal use
> only — don't commit or redistribute them. See `LICENSE`.

## Quickstart

```bash
# from the repo root
pip install -e ".[dev]"

# play the showcase region (start here!)
python -m pkmn.game.play --game examples/triad

# watch two AIs fight (seeded => reproducible)
pkmn-demo --auto --seed 42

# play a battle in the terminal
pkmn-demo

# run the test suite (no network or game data needed)
pytest

# validate a game folder
pkmn-lint --game examples/triad

# generate fresh game data from PokeAPI (optional; pre-generated data ships)
pkmn-fetch-data --out game/data                 # REST API (run at home)
pkmn-fetch-data --out game/data --source csv    # GitHub CSV mirror
```

A pre-generated `game/data` folder (649 species with EV yields, 559 moves,
Gen 5 type chart, natures, items) ships in this repo, so demos work
immediately after install.

## Layout

```
pkmn/
  data/      models + GameData repository (the only code that reads the
             game folder; everything else gets data injected)
  core/      stat math, PokemonState (the ONE persistent representation)
  battle/    events, actions, damage formula, move execution, engine, AI
  cli/       terminal battle demo + the event->text formatter that the
             future pygame renderer will reuse
  datagen/   PokeAPI pipeline (REST + CSV sources)
tests/       pytest suite with a hand-written fixture dataset
game/data/   generated game data (output of pkmn-fetch-data)
docs/        architecture notes and roadmap
```

## Design rules

These are the disciplines that keep a growing, Essentials-class engine
modular and safe to author against. They are retained from the original
design because they *enable* the parity goal, not despite it.

1. **One source of truth.** `PokemonState` owns HP/status/PP/IVs/moves.
   The battle engine wraps it with battle-only volatiles and mutates it
   directly — HP, status, and PP persist after battle like on cartridge,
   with no copy-back step to forget. (Extends to flags/money and, as the
   event runtime lands, variables and self-switches.)
2. **The engine is pure.** No disk I/O, no printing, one injected RNG.
   Inputs are `Action`s, outputs are typed `Event`s. Seeds reproduce
   battles exactly; the CLI and pygame UI are just renderers. Multi-active
   battle formats extend the engine from the inside, never by importing
   game state.
3. **Moves are data, not code.** A metadata interpreter executes the
   majority of moves from their PokeAPI-derived effect description; a
   handler registry covers the rest, one named function at a time.
4. **Gen 5 numbers, verified.** 2.0x crits, 85-100% damage rolls, exact
   stage fractions, 1/8 burn, n/16 toxic, Gen 5 catch/flee formulas —
   with hand-calculated damage values locked in by tests.
5. **Modular subsystems behind stable interfaces.** Data, battle,
   overworld, event runtime, rendering, and audio are independently usable
   and replaceable; each ships behind a feature flag so a game uses as much
   or as little of the engine as it wants — a walking sim, a battle-only
   tool, or a full RPG.
6. **If it lints, it runs.** `pkmn/game/contract.py` is the single spec the
   runtime and linter share. Every new tile flag, layer rule, object type,
   event command, and trigger kind is added there first, so the contract
   can grow without the validator and engine drifting.

## Sprites and assets

`pkmn-fetch-data --sprites` downloads B/W sprites for personal use.
Sprite artwork is Nintendo/Game Freak IP — keep it out of any game
folders you share; the authoring toolkit (Phase 6) treats assets as
user-supplied for exactly this reason.
