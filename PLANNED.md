# Planned Features

This document tracks post-1.0 planned content. See [ROADMAP.md](ROADMAP.md) for the full vision and versioning policy.

Items marked **[1.x]** are backward-compatible additions: games authored for 1.0 will continue to work after the update.
Items marked **[2.0]** require a major-version increment because they change existing engine behavior.

---

## [1.x] Near-term

### Strength boulders (persistent)
Push-able boulders that stay cleared per map across sessions. Adds `can_strength` as an active capability (currently reserved). Requires save schema addition for boulder state.

### Promoted RMXP / PBS importer
Elevate `tools/rmxp2kanto.py` to a first-class `pkmn-import` CLI tool:
- Full PBS species, move, item, and ability ingestion with ID normalization
- RMXP map + event parsing to `.tmx` / `scripts.json`
- Tileset terrain / passage mapping to tile flags
- Acceptance: a clean Essentials project imports and plays without hand-editing

### Bicycle
Speed-doubling overworld transport. Adds `can_bike` capability flag and `bike_blocked` tile flag. Toggles via a menu action or item use.

### Dive
Underwater map pairs. Adds `can_dive` capability flag and `dive` tile flag (surf tile subtype). A Dive action descends to a paired underwater map; surfacing returns to the overworld.

---

## [1.x] Medium-term

### Per-move battle animations
Sequenced sprite animations keyed to move category or move ID. Hit-flash is the current placeholder. The event queue already carries the move identity; the renderer just needs animation tables.

### Move relearner
An NPC that charges a Heart Scale to teach any previously known level-up move. Requires a Heart Scale item and a `remember_move` script command.

### Seasonal system
Time-of-year mapping (month → season) with per-season overworld tints and optional encounter table variants. Seasons declared in `game.json` `settings`.

### Overworld weather effects
Visual rain/snow/sandstorm particle effects in the overworld scene, driven by the map's `weather` property.

---

## [1.x] Long-term

### Breeding and Day Care
- Day Care NPC accepts two Pokémon and produces an Egg after steps
- Egg move inheritance (father's moves flagged `egg_move` in learnset)
- No gender system currently — breeding will either require it or use a simplified rule

### Reusable TMs (Gen 5 style)
TMs currently consumed on use. A `"reusable_tms": true` setting will make them reusable (Gen 5 default behavior). The current behavior becomes opt-in.

### Multi-box PC
Expand PC storage from one box to many. Save schema addition. Requires a new PC UI scene.

### Full title / new-game-or-continue shell
Richer intro: animated title logo, player name entry, gender select, rival name. Currently the title screen goes straight to New Game / Continue.

### Panorama and fog layers
Scrolling background layers for caves and special interiors. Declared in map properties; cosmetic only with no collision effect.

### Audio loop-point metadata
`.ogg` files can declare loop start/end points via Vorbis comments. The audio system would honor them for seamless music looping.

---

## [2.0] XL project — multi-active battles

Double, triple, and rotation battles require generalizing `active_idx[side]` from one slot to a list. This changes `_do_move` semantics in ways that could affect existing single-battle content, making it a 2.0 project.

Full scope:
1. `active_idx[side]` → active-slot list (singles = length 1; all current tests unchanged)
2. Parameterize target/defender through `_do_move` and the damage path
3. Add target selection, spread-move iteration (×0.75), ally/redirection
4. Per-slot faints and forced replacements
5. Doubles battle UI and AI
6. `tests/test_doubles.py` acceptance suite

A 1.x engine cannot run a game folder that requires 2.0 features (e.g., one declaring `"engine_version": "2.0"` with double-battle trainer parties).
</content>
</invoke>