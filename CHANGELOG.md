# Changelog

All user-visible changes are documented here.

## [Unreleased] — v1.0 candidate

### Engine
- **Wonder Room** implemented: swaps Defense and Sp. Defense for all Pokémon for 5 turns; toggles off early on second use. Eliminates the last `EFFECT_SKIPPED` entry (skip rate now 0.00%).
- **Multi-Z overworld**: tile layers carry an integer `z` property; `_merged` only reads flags from the player's elevation. `z_up` / `z_down` tile flags let maps model bridges, stairs, and underpasses.

### Battle items (held items — all batches now complete)
- **Batch A**: Muscle Band (×1.1 physical), Wise Glasses (×1.1 special), Shell Bell (heal 1/8 damage dealt), Big Root (×1.3 draining), Binding Band (×2 trap damage).
- **Batch B–H**: Full held-item suite — weather rocks, speed/accuracy modifiers, all pinch and status berries, all resist berries, EV-drop berries (Pomeg/Kelpsy/Qualot/Hondew/Grepa/Tamato), type-boosting incenses, lax incense.
- **Bug fix**: Cheri Berry (paralysis cure) was missing from `STATUS_BERRIES` — now correctly heals paralysis.
- **Bug fix**: Five type-boosting incenses (sea, wave, odd, rock, rose) were missing from `TYPE_BOOST_ITEMS` — now grant the correct ×1.2 type boost.
- **EV-drop berries**: Pomeg/Kelpsy/Qualot/Hondew/Grepa/Tamato now usable from the bag; each reduces the corresponding stat's EVs by 10.

### Overworld / UI
- All muted-gray text on dark panels replaced with bright-white / near-white values — text legible on all screens.
- Battle dialog message box (`_draw_msg`) now renders white text on the dark panel background.

### Packaging
- `pyproject.toml` added: `pip install -e ".[dev]"` now works; all seven CLI entry points registered (`pkmn-play`, `pkmn-demo`, `pkmn-lint`, `pkmn-audit`, `pkmn-coverage`, `pkmn-sprites`, `pkmn-fetch-data`).
- `pkmn-play` launched without `--game` defaults to the bundled `examples/triad` region.
- All CLI tools (`pkmn-lint`, `pkmn-audit`, `pkmn-coverage`, `pkmn-sprites`) discover `game/data` relative to the installed package — no longer require running from the repo root.
- Added `__init__.py` to every `pkmn` sub-package for reliable wheel packaging.
- Added `Pillow` to dev test dependencies (required by `tests/test_layers.py`).

### Examples
- `examples/kanto` added to the bundled set (lints 0/0, uses procedurally generated placeholder art).
- `examples/kanto_frlg` excluded from the repo: its tileset is derived from FireRed assets and cannot be redistributed. Added to `.gitignore`.

### Tests
- All 343 tests pass; 1 skipped (full-dataset test only runs when `game/data` is present).
- `tests/__init__.py` added so relative imports work under `pytest` in package mode.

## [0.9] — 2026-01-01 (approximate)

Initial pre-release. See [RELEASE.md](RELEASE.md) for the full feature list.
