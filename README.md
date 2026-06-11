# pokemon-python

A Gen 4/5-style Pokemon engine and (eventually) game-authoring toolkit,
written in Python. Ground-up rewrite — the original prototype's code was
used as inspiration only.

**Phase 1 status: battle engine, done right.** Full Gen 5 damage model,
statuses, stat stages, priority/speed ordering, PP and Struggle, switching,
items, fleeing and catching in wild battles — pure, deterministic, and
covered by 50 tests. See `docs/ROADMAP.md` for what comes next.

## Quickstart

```bash
# from the repo root
pip install -e ".[dev]"

# generate game data from PokeAPI (Gen 1-5, with correct Gen 5 values)
pkmn-fetch-data --out game/data                 # REST API (run at home)
pkmn-fetch-data --out game/data --source csv    # GitHub CSV mirror

# watch two AIs fight (seeded => reproducible)
pkmn-demo --auto --seed 42

# play a battle yourself in the terminal
pkmn-demo

# run the test suite (no network or game data needed)
pytest
```

A pre-generated `game/data` folder (649 species, 556 moves, Gen 5 type
chart, natures, starter items) ships in this repo, so the demo works
immediately.

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

1. **One source of truth.** `PokemonState` owns HP/status/PP/IVs/moves.
   The battle engine wraps it with battle-only volatiles and mutates it
   directly — HP, status, and PP persist after battle like on cartridge,
   with no copy-back step to forget.
2. **The engine is pure.** No disk I/O, no printing, one injected RNG.
   Inputs are `Action`s, outputs are typed `Event`s. Seeds reproduce
   battles exactly; the CLI and the future pygame UI are just renderers.
3. **Moves are data, not code.** A metadata interpreter executes the
   majority of moves from their PokeAPI-derived effect description; a
   handler registry covers the rest, one named function at a time.
4. **Gen 5 numbers, verified.** 2.0x crits, 85-100% damage rolls, exact
   stage fractions, 1/8 burn, n/16 toxic, Gen 5 catch/flee formulas —
   with hand-calculated damage values locked in by tests.

## Sprites and assets

`pkmn-fetch-data --sprites` downloads B/W sprites for personal use.
Sprite artwork is Nintendo/Game Freak IP — keep it out of any game
folders you share; the authoring toolkit (Phase 6) treats assets as
user-supplied for exactly this reason.
