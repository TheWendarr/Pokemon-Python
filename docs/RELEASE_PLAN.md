# Release Plan

A phased path from the current build to a tagged **v1.0**, then the
post-1.0 **parity program**. This sits above `ROADMAP.md` (milestones) and
`ESSENTIALS_COMPAT.md` (the parity tier breakdown); where they overlap,
the scoping and sequencing here govern what blocks the **release tag**.

## The scoping decision

"Completed and ready for release" has two referents in this repo, and they
are not the same thing:

1. **v1.0** — a finished, trustworthy *product*: a stranger can install it,
   launch to a title screen, play the showcase end to end, author their own
   region against validated docs, and believe the battle/balance claims.
2. **Essentials parity** — the north star (`ESSENTIALS_COMPAT.md` Tiers
   3–4): multi-active battles, a first-class importer, badges/HMs,
   breeding, the long tail. This is open-ended by nature.

Only (1) is a releasable milestone. (2) is a *program*, not a release —
gating the tag on it means never shipping. **This plan ships v1.0 on the
strength of what already works, parks parity as the 1.x program, and is
explicit about which gaps are release-blockers versus post-tag work.**

## Baseline (updated after Phase D)

| Signal | Value | Tool |
|---|---|---|
| Test suite | 343 passed, 1 skipped | `pytest -q` |
| Example regions linting clean | 6/6 with 0 errors, 0 warnings | `pkmn.cli.lint` |
| `kanto_frlg` warnings | 0 (fixed in Phase A) | `pkmn.cli.lint` |
| Battle effect-skip rate | 4.20% (200 battles) | `pkmn.cli.coverage` |
| Abilities battle-implemented | 85 / 164 used (~52%) | `pkmn.cli.audit` |
| Held-item battle effects | 11 / 678 items | `pkmn.cli.audit` |
| Battle active slots | 1 (single-active) | `pkmn/battle/engine.py` |
| Title / new-game shell | ✅ `TitleScene` (Phase A) | — |
| EV-yield data | ✅ all 649 species (Phase A) | `datagen` |

---

# Phase A — Release hardening (the road to the v1.0 tag)

Close the gaps that make the project feel unfinished or untrustworthy to a
newcomer. Nothing here is architecturally hard; all of it is visible.

### A1. Title / new-game-or-continue shell  *(M — release-blocker)*
The game boots into the middle of a map. Add a `TitleScene` pushed before
`OverworldScene`: logo/text/music from the manifest, "Press Start," and
**New Game / Continue** (Continue enabled only when the save path exists).
Manifest keys: `title.{art,text,music}`. Add them to `MAP_PROPS`/manifest
validation so the linter knows them.
*Accept:* a headless test boots to the title, picks New Game, lands in the
start map; with a save present, Continue resumes location + party.

### A2. `kanto_frlg` cleanup — make the flagship importer demo clean  *(S–M — release-blocker)*
17 warnings on the one converted region undercuts the importer story. Add
spawn objects to the 12 maps that lack them and resolve the 5 one-way
connections (either reciprocate or intentionally mark them). Prefer fixing
the **converter** (`tools/rmxp2kanto.py`) to emit spawns + reciprocal
connections so the fix survives a re-run, not just hand-patching output.
*Accept:* `pkmn.cli.lint --game examples/kanto_frlg` → 0 errors, 0 warnings;
region is BFS-reachable with warp reciprocity verified.

### A3. EV-yield — clear the stale blocker  *(S — quick win)*
The data is reachable here via the GitHub CSV mirror (`pokemon_stats.csv`
carries `effort`). Pull it in `datagen` (CSV path), persist `ev_yield` per
species, and award capped EVs (252/stat, 510 total) on knockout in the
battle/exp path. Re-run the dataset so all 649 species carry it.
*Accept:* a test confirms a known yield (e.g. Bulbasaur → 1 Sp.Atk) flows
from data → battle → `PokemonState` EVs and respects both caps.

### A4. Feature-toggle contract validation  *(S — quick win)*
Manifests carry a `features:` block (`encounters`, `trainers`, `experience`,
…) but the contract doesn't enumerate it, so the linter can't catch a typo'd
toggle — a hole in "if it lints, it runs." Add a `FEATURES`/`SETTINGS` set
to `contract.py` and validate manifest keys against it.
*Accept:* lint rejects an unknown feature key; all examples still lint clean.

### A5. CI smoke harness — boot every example  *(S — insurance)*
A single test that, for each `examples/*/game.json`, boots the region
headless and ticks N frames (catches a region that lints but crashes on
load). Folds the per-region checks into one gate.
*Accept:* `test_examples_boot.py` boots all 6 regions headless; green in the
suite.

### A6. Newcomer on-ramp + packaging  *(S — release-blocker)*
A reviewer can't tell which of 6 regions to run. Add a short "Play this
first" block (point at `triad`), a `CHANGELOG.md`, a LICENSE decision, and
verify `pip install -e ".[dev]"` + the `pkmn-*` console scripts work from a
clean checkout. Confirm the IP boundary note (no shipped Nintendo sprites)
is prominent.
*Accept:* clean-clone → install → `pkmn-demo --auto --seed 42` and
`python -m pkmn.game.play --game examples/triad` both run from the README
verbatim.

**Phase A exit = the v1.0-rc tag.** Suite green, 6/6 regions lint
**0/0**, title→play→save→continue works headless, install path verified.

---

# Phase B — Battle credibility (1.0 quality bar)

The headline is "Gen 5 battle engine," but 24% ability coverage and missing
common moves are what a knowledgeable reviewer finds first. This phase
makes the headline true. Can overlap Phase A; **B1 should land before the
tag**, B2–B3 can be a fast-follow 1.0.1 if needed.

### B1. Ability coverage push  *(M — partial release-blocker)*
40/164 → target **~80 (≈50%)**, prioritized by competitive frequency
(weather/terrain setters, contact effects, stat-on-switch, immunity/absorb
families already have patterns to copy in `passives.py`). Track the number
in `audit` each batch.
*Accept:* `audit` shows the new count; each added ability has a unit test;
skip-rate non-regressed.

### B2. Top skipped move handlers  *(M)*
Knock out the high-frequency skips from `coverage`: destiny-bond, perish-song,
yawn, transform, metronome, snatch, the *-guard family, magnet-rise,
guard-swap. Note **quick/wide-guard are spread-protection** — they only
matter once B/Phase C multi-active exists, so defer those two.
*Accept:* effect-skip rate from 4.20% toward **<3%**; new handlers tested.

### B3. Held-item effects breadth  *(S–M)*
11 effects is thin for 678 items. Add the common competitive set with
existing hooks (more berries, type-boost plates/gems, Eviolite, Assault
Vest, Rocky Helmet, status orbs).
*Accept:* `audit` held-item count rises; each effect has a test.

---

# Phase C — Multi-active battles (the parity centerpiece, XL)

The single largest piece of the parity goal and the one true architectural
project. Pure-engine work only; UI/AI last. Sequenced per
`ESSENTIALS_COMPAT.md`:

1. Generalize `active_idx[side]` → an **active-slot list** (singles = length
   1, preserving every current test and behavior).
2. Parameterize defender/target through `_do_move` and the `moves.py`
   damage path (remove the `active(other(side))` assumption).
3. **Target selection + spread iteration** (0.75× spread multiplier),
   ally/redirection (Follow Me/Lightning Rod), then the deferred
   quick/wide-guard from B2.
4. Turn ordering across all actors; per-slot faint/replacement.
5. Doubles **UI + AI** in `battle_scene.py`.

*Accept:* a double battle resolves through the pure engine under test;
**every existing single-active test still passes unchanged** (the
non-regression contract is the whole point).

---

# Phase D — Importer to product + the parity long tail (1.x)

Post-1.0, open-ended; ship incrementally. From `ESSENTIALS_COMPAT.md`
Tiers 3–4 and `GEN5_GAPS.md`, in dependency order:

- ✅ **Badges + HM field gating** — `give_badge` command, `{"badge": …}`
  conditions, `BadgesScene`, `visited_maps` tracking, all capability flags.
- ✅ **Field moves** — Rock Smash, Waterfall, Headbutt, Flash, dark-cave
  rendering; Fly / Town Map (`FlyScene`).
- ✅ **Richer map metadata** — `heal_point`, `escape_point`, `dark_cave`,
  `fly_name` in `MAP_PROPS`.
- **Strength** *(M)* — push-able `strength_block` boulders; needs
  per-session per-map boulder-position state (deferred).
- **Dive** *(M)* — underwater tiles and map-pair linking (deferred; needs
  map-model support for depth layers).
- **Importer promotion** *(L)* — `.rxdata` map+event parsing, tileset
  terrain/passage mapping, full PBS ingestion with ID normalization.
  This is the parity oracle: when a clean full Essentials project
  round-trips and plays, parity is reached.
- **Long tail** — breeding, move relearner/deleter/tutors, reusable TMs,
  nicknaming UI (needs a text-entry widget), bag pockets, multi-box PC,
  seasons, overworld weather particles. *(M–L each, independent.)*

---

## Sequencing summary

```
A (hardening) ──┬─→ v1.0-rc ──→ v1.0 tag ──→ D (parity long tail, 1.x)
B1 (abilities) ─┘                    │
B2/B3 ───────────────(fast-follow)───┘
C (multi-active) ──── parallel program, lands across 1.x ────────────→
```

A and B1 gate the tag. B2/B3 are fast-follows. C is a self-contained
program that can run in parallel since it lives entirely in the battle
module. D is the open-ended 1.x tail.

## Invariants (unchanged, enforced every phase)

- Battle engine stays **pure** (actions in, typed events out, injected RNG).
- **One source of truth** for persistent state (now incl. variables /
  self-switches / EVs).
- **"If it lints, it runs"** — every new flag/object/command/trigger/feature
  key goes into `contract.py` first.
- **No region literals in core.**
- Each new subsystem ships behind a stable interface + feature flag.
- Iterative live-verification per change: generate → lint → BFS/reciprocity
  → headless render/boot → full suite. No step skipped.
