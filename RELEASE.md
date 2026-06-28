# Release Notes

## v0.9 — PRERELEASE

> **Status: pre-release. v1.0 has not been tagged.** All features listed
> below are implemented and tested, but the packaging smoke-test, CI
> pipeline, and held-item Batch A minimum have not been signed off.
> See the [v1.0 gate](#v10-release-gate) below.

---

## What's included in v0.9

### Battle engine
- Full Gen 5 damage formula (2× crits, 85–100% rolls, exact stage fractions)
- All Gen 5 statuses: burn, freeze, paralysis, sleep, poison, toxic
- Priority ordering, Speed ties broken by RNG, Trick Room reverses sort
- PP tracking, Struggle fallback
- **559/559 Gen 5 moves handled** (100% coverage, 0 EFFECT_SKIPPED)
  — including Substitute with absorption, Trick Room, Gravity, Magic Room,
  Wish/Lunar Dance delayed healing, Disable, Sleep Talk, Foresight/Miracle Eye,
  Skill Swap, Heart Swap, Power Trick, Conversion/Soak type overrides,
  Mirror Move, Magic Coat, Assist, Sketch, Recycle, and more
- **143/164 Gen 5 abilities (87%)** implemented in `pkmn/battle/passives.py`.
  The remaining 21 are doubles-only, cosmetic, or unreachable in singles.
- Entry hazards: Stealth Rock, Spikes (1–3 layers), Toxic Spikes (1–2 layers), Rapid Spin
- Screens: Reflect, Light Screen, Safeguard, Mist, Lucky Chant, Tailwind
- All four weather types: rain, sun, sandstorm, hail — with weather setters and abilities
- Protect / Endure with consecutive-use decay
- Two-turn charging, recharge, and rampage move families
- Partial trapping (Wrap family)
- Leech Seed, Ingrain, Aqua Ring
- Choice item lock, Focus Sash, Life Orb, Expert Belt
- All 17 type Gems, all 16 Plates, 20+ type-enhancement items (×1.2 boost)
- All 9 held status berries (Cheri, Chesto, Pecha, Rawst, Aspear, Persim, Lum, Oran, Sitrus)
- Flame Orb / Toxic Orb auto-inflict
- Leftovers end-of-turn heal
- Scope Lens / Razor Claw crit boost
- Focus Sash / Eviolite / Assault Vest / Rocky Helmet
- Gen 5 catch formula; wild flee formula
- KO-aware GreedyAI

### Overworld and game systems
- Pygame-CE window: grid movement, NPC interaction, tall-grass wild encounters
- Full battle UI: Fight / Bag / Pokémon / Run, party menu, forced replacements, catching, whiteout
- EXP gain, all six growth curves, level-up stat recalculation, level-up move learning
- Post-battle evolution with data-driven evolution chains
- Save / load (JSON): party, PC box, bag, money, flags, vars, self-switches, location
- Pause menu: party (summary, order swap, held items), bag, save, Pokédex, controls
- PC box via in-game terminal
- Title screen with New Game / Continue
- Badges: `give_badge` command, badge-count conditions, BadgesScene in pause menu
- Fly / Town Map: FlyScene lists `fly_name` maps, warps to chosen destination
- Field moves: Rock Smash, Waterfall, Headbutt, Flash — gated by `can_*` flags
- Map metadata: `heal_point`, `escape_point`, `dark_cave`, `fly_name`
- Visited maps set serialized in saves
- Day/night cycle: clock-driven morning/day/evening/night tint; configurable per region

### Event runtime
- Compiled IP-based VM: `if/while/label/goto/wait`, integer variables, self-switches
- Multi-page conditional events (last-active-page logic)
- Autorun and parallel triggers
- Move routes
- Python authoring API (`pkmn/game/events.py`)
- `register_command` extension seam

### Rendering
- 256×192 design grid at 4× scale (1024×768 native canvas, 64 px tiles)
- Pixel-perfect integer scaling (default) or sharp-bilinear fill (`--fill`)
- Fullscreen via `--fullscreen` or F11
- Multiple tile layers with draw priority (`over` layer renders above sprites)
- Directional / partial passability
- Tile animation (autotile frames)
- Configurable tile size
- Seamless scrolling overworld via map connections

### Authoring and tooling
- Content-folder format: `game.json` manifest, Tiled maps, sprites, scripts, encounters
- `pkmn-lint` — validates manifest, maps, warps, scripts, species/item/move references
- `pkmn-audit` — cross-validates all references against the data catalog
- `pkmn-coverage` — reports implemented vs. EFFECT_SKIPPED move handlers
- `pkmn-sprites` — pre-warms sprite cache for a game folder
- `pkmn-fetch-data` — (re)generates the game data catalog from PokeAPI
- `pkmn-demo` — headless CLI battle demo

### Data catalog (ships pre-generated)
| Catalog | Count |
|---------|-------|
| Species | 649 (with EV yields, learnsets, evolution chains) |
| Moves | 559 (B2W2 values) |
| Abilities | 164 |
| Items | 678 (categories, pocket, flags, effect text) |
| Natures | 25 |

### Bundled example regions
| Region | Notes |
|--------|-------|
| `examples/triad` | Showcase: 3 cities, 3 routes, scripted events, flag-gated finale |
| `examples/isleton` | Minimal island region — recommended copy-paste starting point |
| `examples/kanto` | Simplified Kanto layout using hand-authored content |
| `examples/kanto_frlg` | Converted from a FireRed bootleg via `tools/rmxp2kanto.py` |
| `examples/eventlab` | Demonstrates autorun, multi-page NPCs, parallel routes, puzzles |
| `examples/seamless` | Demonstrates surf, ledges, Cut, Rock Smash, waterfall, headbutt |

---

## Partially implemented (known gaps)

| Feature | Status |
|---------|--------|
| Held-item breadth | Infrastructure complete; Batch A (Muscle Band, Wise Glasses, Shell Bell, Big Root, Binding Band) needed for v1.0; Batches B–H are post-1.0. See `docs/ItemPlan.md`. |
| Autotile edge-blending | Basic animation works; full 47-piece edge blending deferred (cosmetic) |
| Panorama / fog layers | Not implemented (cosmetic; not required for importer) |
| Animated battle sprites | No per-move animations; static sprite with hit-flash only |
| Breeding / move relearner / reusable TMs | Not implemented (post-1.0 long tail) |
| Bike | Not implemented |
| Strength boulders (persistent) | Per-session clear works; per-map persistence forthcoming |
| Dive (underwater maps) | Not implemented |
| Multi-active battles (doubles/triples) | Engine is singles-only; architectural XL project |
| Full RMXP/PBS importer | Converter exists for kanto_frlg; full PBS pipeline is post-1.0 |

---

## Post-1.0 / 1.x program

- Full Essentials parity: breeding, PC multi-box, seasons, overworld weather, full title/config UI
- Double / triple / rotation battles
- Promoted RMXP + PBS importer (map parsing, tileset terrain mapping, event import)
- Held-item Batches B–H (resist berries, pinch berries, accuracy modifiers, Red Card, Eject Button, etc.)
- Strength persistence, Dive, full HM gating
- Per-move battle animations

---

## v1.0 Release Gate

The v1.0 tag will not be cut until all items below are checked.

| # | Criterion | Done? |
|---|-----------|-------|
| 1 | Clean wheel install works outside repo root (`pip install dist/*.whl` in a fresh venv; `pkmn-play --help` succeeds) | ☐ |
| 2 | `pkmn-play` starts with bundled default/example content (no `--game` argument needed for the included region) | ☐ |
| 3 | `pyproject.toml` dependency list matches actual runtime imports (`pip check` in a clean venv passes) | ☐ |
| 4 | `pytest` fully green — 0 failures, 0 errors | ☐ |
| 5 | `pkmn-lint` exits 0/0 for all six bundled examples | ☐ |
| 6 | `pkmn-audit` has no broken cross-references across all bundled examples | ☐ |
| 7 | `pkmn-coverage` reports 0 unexpected EFFECT_SKIPPED entries | ☐ |
| 8 | Held-item Batch A implemented: Muscle Band, Wise Glasses, Shell Bell, Big Root, Binding Band | ☐ |
| 9 | README, ROADMAP, RELEASE, and AUTHORING are internally consistent (version, phase status, feature list agree) | ☐ |
| 10 | `CHANGELOG.md` documents all user-visible changes since last tag | ☐ |
| 11 | No `__pycache__/` or `.pyc` files in the built wheel or sdist | ☐ |
| 12 | CI pipeline runs: tests → lint (all examples) → audit → coverage → wheel build → package smoke test | ☐ |
| 13 | IP / distribution note is explicit: `LICENSE` is MIT; README and LICENSE clearly state Game Freak / Nintendo assets are not included and must not be redistributed | ☐ |

---

## CLI reference

| Command | Description |
|---------|-------------|
| `pkmn-play --game DIR` | Launch the game |
| `pkmn-play --game DIR --cheat=T` | Launch with cheat console (`~` to open in-game) |
| `pkmn-demo` | Interactive CLI battle |
| `pkmn-demo --auto --seed N` | Seeded AI-vs-AI battle |
| `pkmn-lint --game DIR` | Validate a game folder |
| `pkmn-audit` | Cross-reference check across all examples |
| `pkmn-coverage` | Report EFFECT_SKIPPED rate across the move pool |
| `pkmn-sprites --game DIR` | Pre-warm sprite cache |
| `pkmn-sprites --all` | Pre-warm full 649-species sprite cache |
| `pkmn-fetch-data --out game/data` | Regenerate game data from PokeAPI |
| `pkmn-fetch-data --out game/data --source csv` | Regenerate from GitHub CSV mirror |

**Launch flags**

| Flag | Default | Notes |
|------|---------|-------|
| `--game DIR` | `game/assets` | Content folder to run |
| `--save FILE` | `save.json` | Save file path |
| `--seed N` | random | RNG seed (for reproducibility) |
| `--cheat T\|F` | `F` | Enable cheat console (`~` opens it in-game) |
| `--headless` | off | Dummy video driver (CI / testing) |
| `--mute` | off | Disable all audio |
| `--fullscreen` | off | Fullscreen at native resolution |
| `--fill` | off | Sharp-bilinear fill instead of pixel-perfect |
| `--time PHASE\|auto\|off` | manifest | Override day/night phase |
| `--controls FILE` | `controls.json` | Key-binding file path |
| `--no-sprite-fetch` | off | Never download sprites; cache + blobs only |
