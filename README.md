# pokemon-python

A Gen 4/5-style Pokémon engine and game-authoring toolkit, written in pure Python.
The goal is reliable parity with **RPG Maker XP + Pokémon Essentials** — build a
complete Pokémon game using only Python and editable content folders, with no RPG
Maker, no Ruby, and no proprietary editor.

> **Status: v0.9 PRERELEASE.** The engine is feature-complete for a playable
> single-region game. See [RELEASE.md](RELEASE.md) for what's in this build and
> what remains before v1.0 is tagged.

---

## Quickstart

```bash
pip install -e ".[dev]"
python -m pkmn.game.play --game examples/triad
```

Arrow keys / WASD — move · Z / Space — confirm · X / Esc — cancel · Enter — menu

> **IP note.** This engine ships zero Nintendo assets. `pkmn-sprites` downloads
> Black/White sprites for personal use only — do not commit or redistribute them.
> See `LICENSE` and [AUTHORING.md § IP](AUTHORING.md#ip-reminder).

---

## What works today

- **Battle engine** — Full Gen 5 damage formula, all statuses, 559/559 moves (100%),
  143/164 abilities (87%), all weathers, entry hazards, screens, held items
- **Overworld** — Tiled maps, grid movement, NPCs, trainers, warps, seamless connections,
  day/night cycle, surf/field moves, Fly / Town Map
- **Event runtime** — Compiled VM with variables, self-switches, multi-page events,
  autorun/parallel triggers, move routes, and a Python authoring API
- **Game systems** — Save/load, EXP + evolution, party / bag / PC, Pokédex, badges
- **Authoring tools** — `game.json` content folders, `pkmn-lint`, `pkmn-audit`,
  `pkmn-coverage`, procedural art + audio generation
- **Data catalog** — 649 species, 559 moves, 164 abilities, 678 items (ships pre-generated)

Six bundled example regions: `triad` (showcase), `isleton`, `kanto`, `kanto_frlg`,
`eventlab`, `seamless`.

---

## Install

```bash
# development (recommended — editable install + test deps)
pip install -e ".[dev]"

# production wheel (once built)
pip install dist/pokemon_python-*.whl
```

Requires Python ≥ 3.11, `pygame-ce ≥ 2.5`, `pytmx ≥ 3.31`.

---

## CLI tools

| Command | Description |
|---------|-------------|
| `pkmn-play --game DIR` | Launch a game folder |
| `pkmn-demo` | Interactive CLI battle demo |
| `pkmn-demo --auto --seed N` | Seeded AI-vs-AI battle |
| `pkmn-lint --game DIR` | Validate a game folder (exits nonzero on errors) |
| `pkmn-audit` | Cross-reference audit across bundled examples |
| `pkmn-coverage` | Report EFFECT_SKIPPED rate across the full move pool |
| `pkmn-sprites --game DIR` | Pre-warm sprite cache for a game |
| `pkmn-fetch-data --out game/data` | Regenerate game data from PokeAPI |

Run `pytest` to execute the full test suite (no network required).

---

## Making your own game

See **[AUTHORING.md](AUTHORING.md)** for the complete content-folder format:
manifest, Tiled maps, tile flags, script commands, encounter tables, audio,
and how to keep IP-sensitive assets in a private repository.

---

## Project documentation

| Document | Contents |
|----------|----------|
| [AUTHORING.md](AUTHORING.md) | Full guide for creating game content |
| [RELEASE.md](RELEASE.md) | Feature list, known gaps, v1.0 gate checklist |
| [ROADMAP.md](ROADMAP.md) | Phase history, planned features, design principles |
| [CHANGELOG.md](CHANGELOG.md) | User-visible changes per release |
| [docs/ItemPlan.md](docs/ItemPlan.md) | Held-item implementation plan |

---

## Repository layout

```
pkmn/
  data/      GameData repository and models
  core/      PokemonState, stat math, experience curves
  battle/    Battle engine, move handlers, ability hooks, AI
  game/      Overworld, event runtime, scene stack, UI
  cli/       Battle demo, lint, audit, coverage, sprite tools
  datagen/   PokeAPI pipeline (REST + CSV)
game/data/   Pre-generated catalog (species, moves, abilities, items)
examples/    Six bundled game folders (hand-authored, no GF assets)
tests/       pytest suite (~337 tests)
tools/       Art generation, RMXP converter
docs/        ItemPlan.md and any supplementary technical notes
```

---

## Design rules

1. **One source of truth.** `PokemonState` owns HP/status/PP/IVs/moves. The battle engine mutates it directly — state persists after battle like on cartridge.
2. **The engine is pure.** No disk I/O, one injected RNG. Inputs are Actions, outputs are typed Events. Seeds reproduce battles exactly.
3. **Moves are data, not code.** A metadata interpreter handles the common cases; a handler registry covers the rest.
4. **Gen 5 numbers, verified.** Exact stage fractions, 85–100% rolls, 2× crits, Gen 5 catch formula — locked in by hand-calculated tests.
5. **If it lints, it runs.** `pkmn/game/contract.py` is the single spec the runtime and linter share. Every new feature is added there first.
6. **Every subsystem ships behind a feature flag.** A game uses as much or as little of the engine as it needs.
