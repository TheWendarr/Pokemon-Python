# Release Notes

## v1.0

First stable release. All bundled examples lint 0/0, test suite is 343 passed / 1 skipped / 0 failures, move coverage is 0 EFFECT_SKIPPED.

---

## What ships in v1.0

### Battle engine
- Full Gen 5 damage formula (2× crits, 85–100% rolls, exact stage fractions)
- All Gen 5 statuses: burn, freeze, paralysis, sleep, poison, toxic
- Priority ordering, Speed ties broken by RNG, Trick Room reverses sort
- PP tracking, Struggle fallback
- **559 / 559 Gen 5 moves (100%)** — including Substitute, Trick Room, Wonder Room, Gravity, Magic Room, Wish / Lunar Dance, Disable, Sleep Talk, Foresight / Miracle Eye, Skill Swap, Heart Swap, Power Trick, Conversion / Soak type overrides, Mirror Move, Magic Coat, Assist, Sketch, Recycle, and more
- **143 / 164 Gen 5 abilities (87%)** — remaining 21 are doubles-only, cosmetic, or unreachable in singles
- Entry hazards: Stealth Rock, Spikes (1–3 layers), Toxic Spikes (1–2 layers), Rapid Spin
- Screens: Reflect, Light Screen, Safeguard, Mist, Lucky Chant, Tailwind
- All four weather types with setters and triggered abilities
- Protect / Endure with consecutive-use decay
- Two-turn charging, recharge, and rampage move families
- Partial trapping (Wrap family), Leech Seed, Ingrain, Aqua Ring
- Full held-item suite:
  - Muscle Band, Wise Glasses, Shell Bell, Big Root, Binding Band
  - Choice items (Band / Specs / Scarf), Life Orb, Expert Belt
  - Focus Sash, Eviolite, Assault Vest, Rocky Helmet
  - All 17 type Gems, all 16 Plates, 20+ type-enhancement items
  - All 9 status berries (Cheri, Chesto, Pecha, Rawst, Aspear, Persim, Lum, Oran, Sitrus)
  - All pinch berries, all resist berries, EV-drop berries (Pomeg/Kelpsy/Qualot/Hondew/Grepa/Tamato)
  - Type-boosting incenses (Sea, Wave, Odd, Rock, Rose), Lax Incense
  - Weather rocks, speed/accuracy modifiers, Flame Orb / Toxic Orb, Leftovers, Scope Lens / Razor Claw
- Gen 5 catch formula; wild flee formula
- KO-aware Greedy AI

### Overworld and game systems
- Pygame-CE window: grid movement, NPC interaction, tall-grass wild encounters
- Full battle UI: Fight / Bag / Pokémon / Run, party menu, forced replacements, catching, whiteout
- EXP gain, all six growth curves, level-up stat recalculation, level-up move learning
- Post-battle evolution with data-driven evolution chains
- Save / load (JSON): party, PC box, bag, money, flags, vars, self-switches, location
- Pause menu: party (summary, order swap, held items), bag, save, Pokédex, controls
- PC box via in-game terminal; in-game cheat console (open with `~`, enable with `--cheat=T`)
- Title screen with New Game / Continue
- Badges: `give_badge` command, badge-count conditions, Badges screen in pause menu
- Fly / Town Map: FlyScene lists `fly_name` maps, warps to chosen destination
- Field moves: Surf, Cut, Rock Smash, Waterfall, Headbutt, Flash — gated by `can_*` flags
- Map metadata: `heal_point`, `escape_point`, `dark_cave`, `fly_name`
- Visited maps set serialized in saves
- Day/night cycle: clock-driven morning/day/evening/night tint; configurable per region
- Seamless scrolling overworld via map connections

### Event runtime
- Compiled IP-based VM: `if/while/label/goto/wait`, integer variables, self-switches
- Multi-page conditional events (last-active-page logic)
- Autorun and parallel triggers; move routes
- Python authoring API (`pkmn/game/events.py`); `register_command` extension seam

### Rendering
- 256×192 design grid at 4× scale (1024×768 canvas, 64 px tiles)
- Pixel-perfect integer scaling (default) or sharp-bilinear fill (`--fill`)
- Fullscreen via `--fullscreen` or F11
- Multiple tile layers with draw priority (`over` layer renders above sprites)
- Directional / partial passability; ledge tiles
- Tile animation (autotile frames)
- Multi-Z overworld: tile layers carry a `z` property for bridges and underpasses

### Authoring and tooling
- Content-folder format: `game.json` manifest, Tiled maps, sprites, scripts, encounters
- `pkmn-lint` — validates manifest, maps, warps, scripts, species/item/move references
- `pkmn-audit` — cross-validates all references against the data catalog
- `pkmn-coverage` — reports implemented vs. EFFECT_SKIPPED move handlers
- `pkmn-sprites` — pre-warms sprite cache for a game folder
- `pkmn-fetch-data` — (re)generates the game data catalog from PokeAPI
- `pkmn-demo` — headless CLI battle demo

### Data catalog

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
| `examples/eventlab` | Demonstrates autorun, multi-page NPCs, parallel routes, puzzles |
| `examples/seamless` | Demonstrates surf, ledges, Cut, Rock Smash, waterfall, headbutt |

> `examples/kanto_frlg` is excluded from this repository: its tileset is derived from FireRed assets which cannot be redistributed. Use the engine's converter tools to build your own region from custom art.

---

## Known limitations

| Feature | Status |
|---------|--------|
| Autotile edge-blending | Basic animation works; full 47-piece edge blending deferred (cosmetic) |
| Panorama / fog layers | Not implemented (cosmetic) |
| Animated battle sprites | Static sprite with hit-flash only; no per-move animations |
| Breeding / move relearner / reusable TMs | Not implemented |
| Bike | Not implemented |
| Strength boulders (persistent) | Per-session clear works; per-map persistence not yet implemented |
| Dive (underwater maps) | Not implemented |
| Multi-active battles (doubles/triples) | Engine is singles-only |
| Full RMXP/PBS importer | Converter exists for RMXP maps; full PBS pipeline is post-1.0 |

See [PLANNED.md](PLANNED.md) for the post-1.0 roadmap.

---

## CLI reference

| Command | Description |
|---------|-------------|
| `pkmn-play --game DIR` | Launch the game |
| `pkmn-play --game DIR --cheat=T` | Launch with cheat console (`~` to open in-game) |
| `pkmn-demo` | Interactive CLI battle |
| `pkmn-demo --auto --seed N` | Seeded AI-vs-AI battle |
| `pkmn-lint --game DIR` | Validate a game folder |
| `pkmn-audit` | Cross-reference check across the data catalog |
| `pkmn-coverage` | Report EFFECT_SKIPPED rate across the move pool |
| `pkmn-sprites --game DIR` | Pre-warm sprite cache |
| `pkmn-sprites --all` | Pre-warm full 649-species sprite cache |
| `pkmn-fetch-data --out game/data` | Regenerate game data from PokeAPI |
| `pkmn-fetch-data --out game/data --source csv` | Regenerate from GitHub CSV mirror |

**Launch flags**

| Flag | Default | Notes |
|------|---------|-------|
| `--game DIR` | bundled `examples/triad` | Content folder to run |
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
</content>
</invoke>