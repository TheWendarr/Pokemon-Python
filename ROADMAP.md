# Roadmap

## Vision

**Reliably reproduce the full functionality of RPG Maker XP + Pokémon Essentials, delivered as pure Python.**
Anything you can build in Essentials should be buildable here — without RPG Maker, without Ruby, without a proprietary editor.
The engine is a set of modular subsystems over an editable content contract, designed to be extended.

Three co-equal goals:

1. **Parity** — Essentials is the functional target. A gap in capability is a gap to close, not a feature to decline.
2. **Modularity** — subsystems (data, battle, overworld, event runtime, rendering, audio) are independently usable and replaceable behind stable interfaces.
3. **Pure-Python authoring** — making a game means writing Python and editing content folders, not learning Ruby or a GUI editor.

---

## Versioning and compatibility

Game folders declare the engine version they were authored for in `game.json` (`"engine_version": "1.0"`).
Compatibility is determined by **major version only**:

- A game targeting major **N** runs on any engine whose major is **≥ N**.
- A game targeting major **N** cannot run on an engine whose major is **< N**.

In practice: **all 1.x games run on every 1.x engine and on any future 2.x+ engine.** A game authored for engine 2.0 will not run on a 1.x engine — it may use features that 1.x cannot handle.

The minor component is incremented for additive, backward-compatible additions (new optional fields, new script commands, new tile flags). The major component is only incremented when existing game content could break on the new engine.

---

## Planned for 1.x

These are additive features that fit within the 1.x contract — game folders authored for 1.0 will continue to work after any 1.x update.

### Near-term
- **Strength boulder persistence** — boulders cleared per map, not per session
- **Promoted RMXP / PBS importer** — full map + event parsing, tileset terrain mapping, full PBS species/move/item ingestion
- **Bicycle** — speed-doubling overworld transport; `can_bike` capability flag
- **Dive** — underwater map pairs; `can_dive` capability flag + `dive` tile flag

### Medium-term
- **Per-move battle animations** — hit-flash is the current placeholder; sequenced sprite animations per move category
- **Move relearner** — NPC that teaches forgotten level-up moves for a Heart Scale
- **Seasonal system** — time-of-year tint + encounter table variants
- **Overworld weather effects** — visual rain/snow/sandstorm effects in the overworld scene

### Long-term (within 1.x)
- **Breeding / Day Care** — egg production, egg move inheritance
- **Reusable TMs (Gen 5 style)** — TMs consumed on use by default; a settings toggle makes them reusable
- **Multi-box PC** — expandable PC storage beyond box 1
- **Full title / new-game-or-continue shell** — richer intro sequence, name entry, gender select
- **Panorama / fog layers** — cosmetic background scroll layers for caves and interiors

---

## The XL project — multi-active battles (2.x)

Double / triple / rotation battles require a deep architectural change to the battle module, not a bolt-on. This is scoped as the 2.0 major-version project because it changes `_do_move` semantics in ways that may affect existing single-battle content.

Planned approach:
1. Generalize `active_idx[side]` → an active-slot list (singles = length 1, preserving all current tests)
2. Parameterize target / defender through `_do_move` and the damage path
3. Add target selection, spread-move iteration (×0.75 spread), and ally/redirection
4. Order all actors per turn; handle per-slot faints and forced replacements
5. Doubles battle UI and AI in `battle_scene.py`

Acceptance: a double battle resolves through the pure engine under test with `tests/test_doubles.py` passing; all existing single-battle tests unchanged.

---

## Design principles

These disciplines keep the engine modular as it grows toward parity.

- **No region literals in core.** Everything is learned from the content folder.
- **If it lints, it runs.** `contract.py` is the single spec the runtime and linter share. Every new feature is added there first.
- **The battle engine stays pure.** Actions in, typed Events out, one injected RNG, no I/O. Multi-active will extend it from the inside.
- **One source of truth for state.** `PokemonState` owns all persistent Pokémon data. The engine mutates it directly — HP, PP, and status persist after battle with no copy-back step.
- **Every subsystem ships behind a feature flag.** A game uses as much or as little of the engine as it wants — walking sim, battle tool, or full RPG.
</content>
</invoke>