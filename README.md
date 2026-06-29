# pokemon-python

A Gen 4/5-style Pokémon engine and game-authoring toolkit, written in pure Python.
Build a complete Pokémon game using only Python and editable content folders — no RPG Maker, no Ruby, no proprietary editor.

> **IP note.** This engine ships zero Nintendo assets. `pkmn-sprites` downloads
> Black/White sprites for personal use only — do not commit or redistribute them.
> See `LICENSE` and [AUTHORING.md § IP](AUTHORING.md#keeping-private-content-out-of-this-repository).

---

## Quickstart

```bash
pip install -e ".[dev]"
pkmn-play
```

Launches the bundled `examples/triad` region. Arrow keys / WASD — move · Z / Space — confirm · X / Esc — cancel · Enter — menu.

To run your own game folder:

```bash
pkmn-play --game path/to/yourgame
```

---

## Install

**Editable (development):**
```bash
pip install -e ".[dev]"
```

**From wheel:**
```bash
pip install dist/pokemon_python-*.whl
```

Requires Python ≥ 3.11, `pygame-ce ≥ 2.5`, `pytmx ≥ 3.31`.

Run tests: `pytest`

---

## What's included

### Battle engine
- Full Gen 5 damage formula (85–100% rolls, 2× crits, exact stage fractions)
- All statuses: burn, freeze, paralysis, sleep, poison, toxic
- **559 / 559 Gen 5 moves (100%)** — including Substitute, Trick Room, Wonder Room, Gravity, Magic Room, Wish / Lunar Dance, Disable, Sleep Talk, Foresight, Miracle Eye, Skill Swap, Heart Swap, Power Trick, Conversion, Soak, Mirror Move, Magic Coat, Assist, Sketch, Recycle, and more
- **143 / 164 Gen 5 abilities (87%)** — remaining 21 are doubles-only, cosmetic, or unreachable in singles
- All four weathers with their setters and weather-triggered abilities
- Entry hazards: Stealth Rock, Spikes (1–3 layers), Toxic Spikes (1–2 layers), Rapid Spin
- Screens: Reflect, Light Screen, Safeguard, Mist, Lucky Chant, Tailwind
- Protect / Endure with consecutive-use decay; two-turn moves; recharge moves; rampage locks
- Full held-item suite: all pinch berries, all status berries, all resist berries, EV-drop berries, type-boosting incenses, weather rocks, Muscle Band, Wise Glasses, Shell Bell, Big Root, Binding Band, Choice items, Life Orb, Expert Belt, Focus Sash, all Plates and Gems, and more
- Gen 5 catch formula; wild flee formula; KO-aware Greedy AI

### Overworld and game systems
- Pygame-CE window: grid movement, NPC interaction, trainers with line-of-sight
- Full battle UI: Fight / Bag / Pokémon / Run, forced replacements, catching, whiteout
- EXP gain, all six growth curves, level-up move learning, post-battle evolution
- Save / load (JSON): party, PC box, bag, money, flags, vars, self-switches, location
- Pause menu: party summary, order swap, held items, bag, save, Pokédex, controls, badges
- PC box via in-game terminal; in-game cheat console (`--cheat=T`, open with `~`)
- Title screen: New Game / Continue
- Badges: `give_badge` script command, badge-count conditions, Badges screen
- Fly / Town Map: `fly_name` maps become Fly destinations
- Field moves: Surf, Cut, Rock Smash, Waterfall, Headbutt, Flash — all HM-gated
- Day/night cycle: clock-driven morning/day/evening/night tint; configurable per region
- Seamless scrolling overworld via map connections (Gen 1 style)

### Event runtime
- Compiled IP-based VM: `if/while/label/goto/wait`, integer variables, self-switches
- Multi-page conditional events (last-active-page logic)
- Autorun and parallel triggers; move routes
- Python authoring API (`pkmn/game/events.py`); `register_command` extension seam

### Data catalog (ships pre-generated)

| Catalog | Count |
|---------|-------|
| Species | 649 (with EV yields, learnsets, evolution chains) |
| Moves | 559 (Gen 5 / B2W2 values) |
| Abilities | 164 |
| Items | 678 (category, pocket, flags, effect text) |
| Natures | 25 |

### Bundled example regions

| Region | What it demonstrates |
|--------|----------------------|
| `examples/triad` | Showcase: 3 cities, 3 routes, trainers, shops, scripted events, flag-gated finale |
| `examples/isleton` | Minimal island — recommended copy-paste starting point |
| `examples/kanto` | Multi-route region with Fly and badge gating |
| `examples/eventlab` | Autorun, multi-page NPCs, parallel move-routes, puzzles |
| `examples/seamless` | Seamless scrolling maps: surf, ledges, Cut, Rock Smash, waterfall, headbutt |

---

## CLI tools

| Command | Description |
|---------|-------------|
| `pkmn-play --game DIR` | Launch a game folder |
| `pkmn-demo` | Interactive CLI battle demo |
| `pkmn-demo --auto --seed N` | Seeded AI-vs-AI battle |
| `pkmn-lint --game DIR` | Validate a game folder (exits nonzero on errors) |
| `pkmn-audit` | Cross-reference audit across the data catalog |
| `pkmn-coverage` | Report move implementation rate (0 skipped required for release) |
| `pkmn-sprites --game DIR` | Pre-warm sprite cache for a game |
| `pkmn-fetch-data --out game/data` | Regenerate the data catalog from PokeAPI |

**Launch flags** (`pkmn-play`):

| Flag | Default | Notes |
|------|---------|-------|
| `--game DIR` | bundled `examples/triad` | Content folder to run |
| `--save FILE` | `save.json` | Save file path |
| `--seed N` | random | RNG seed |
| `--cheat T\|F` | `F` | Enable cheat console (`~` to open in-game) |
| `--headless` | off | Dummy video driver (CI / testing) |
| `--mute` | off | Disable all audio |
| `--fullscreen` | off | Fullscreen at native resolution |
| `--fill` | off | Sharp-bilinear fill instead of pixel-perfect |
| `--time PHASE\|auto\|off` | manifest | Override day/night phase |

---

## Making your own game

See **[AUTHORING.md](AUTHORING.md)** for the complete guide: game.json manifest, Tiled maps, tile flags, script commands, encounter tables, NPC objects, audio, controls, and how to keep your IP-sensitive content in a private repository.

The fastest start is copying `examples/isleton/` and editing from there.

---

## Documentation

| Document | Contents |
|----------|----------|
| [AUTHORING.md](AUTHORING.md) | Full authoring guide: manifest, maps, scripts, encounters, audio |
| [PLANNED.md](PLANNED.md) | Post-1.0 planned features |
| [CHANGELOG.md](CHANGELOG.md) | User-visible changes per release |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Internal engine architecture reference |

---

## Repository layout

```
pkmn/
  data/       GameData repository and models
  core/       PokemonState, stat math, experience curves
  battle/     Battle engine, move handlers, ability hooks, AI
  game/       Overworld, event runtime, scene stack, UI
  cli/        Battle demo, lint, audit, coverage, sprite tools
  datagen/    PokeAPI pipeline (REST + CSV)
game/data/    Pre-generated catalog (species, moves, abilities, items)
examples/     Five bundled game folders (hand-authored, no Nintendo assets)
tests/        pytest suite
tools/        Art generation, RMXP converter
docs/         Architecture reference
```

---

## Design principles

1. **One source of truth.** `PokemonState` owns HP/status/PP/IVs/moves. The engine mutates it directly — state persists after battle like on cartridge.
2. **The engine is pure.** No disk I/O, one injected RNG. Inputs are Actions, outputs are typed Events. Seeds reproduce battles exactly.
3. **Moves are data, not code.** A metadata interpreter handles the common cases; a handler registry covers the rest.
4. **Gen 5 numbers, verified.** Exact stage fractions, 85–100% rolls, 2× crits, Gen 5 catch formula — locked in by hand-calculated tests.
5. **If it lints, it runs.** `pkmn/game/contract.py` is the single spec the runtime and linter share. Every new feature is added there first.
6. **Every subsystem ships behind a feature flag.** A game uses as much or as little of the engine as it needs.
</content>
</invoke>