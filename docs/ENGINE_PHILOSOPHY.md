# Engine philosophy: an Essentials-class engine you author in Python

This document sets the design philosophy for the project. It supersedes
the earlier version, which framed the engine as a deliberately *minimal*
set of primitives and treated simplicity as a hard ceiling — explicitly
ruling out an eventing VM, per-region extension, layered maps, and
multi-active battles. That ceiling is gone. The thesis now is:

> **Reliably reproduce the full functionality of RPG Maker XP + Pokémon
> Essentials, delivered as pure Python. Anything you can build in
> Essentials, you can build here — without RPG Maker, without Ruby,
> without a proprietary editor. The engine is a set of modular,
> independently usable subsystems over an editable content contract, and
> it is designed to be extended.**

Three goals, co-equal:

1. **Parity.** Essentials is the functional target. When it has a
   capability we do not, that is a gap to close, not a feature to decline.
   The migration converter doubles as the parity oracle: parity is reached
   when a real Essentials project round-trips and plays faithfully (see
   `docs/ROADMAP.md`).
2. **Modularity.** The engine is composed of subsystems — data, battle,
   overworld, event runtime, rendering, audio — each with a clean seam and
   a stable interface, each usable on its own and replaceable without
   touching the others. A person should be able to take the battle engine
   alone, or swap the renderer, or register their own systems.
3. **Pure-Python authoring.** Making a Pokémon game here means writing
   Python and editing content folders — not learning Ruby or a GUI editor.
   Events are expressible as data *and* as a documented Python API.

## What changed, and why

The old doc drew a sharp line: "a game engine is a small set of composable
primitives over a simple data contract," "fixed vocabulary, not plugins,"
"custom engine code per region is out of scope," "designers get power by
composing primitives, not by forking the engine." That philosophy produced
a clean, well-tested core — and it is exactly why the engine cannot yet run
real Essentials content without a converter that throws most of it away.

We are choosing capability. "Scalable games" in the Pokémon-fan sense — the
kind people actually build in Essentials — require integer variables,
self-switches, common events, autorun/parallel triggers, move routes, and
control flow. Those are not optional flourishes; they are the substrate of
gym puzzles, cutscenes, and progression. So we build them.

**Simplicity is not abandoned — it is relocated.** It stops being a cap on
*what the engine can do* and becomes a standard for *how each module is
built*: small, readable, deterministic where possible, data-driven where it
helps, and behind a clean interface. A larger engine made of disciplined,
well-bounded modules is the goal — not a small engine with a small feature
set.

## What we keep (these are good modularity, not minimalism)

Several disciplines from the original design directly serve the new goals
and are retained without change:

- **The pure battle engine.** Actions in, typed `Event`s out, one injected
  RNG, no I/O, no rendering knowledge. This is the model module: a
  subsystem with a hard interface that anyone can drive. Multi-active
  battle formats will extend it *from the inside*, never by making it
  import game state.
- **One source of truth for state.** `PokemonState` owns the persistent
  Pokémon; the world owns flags/money and (soon) variables and
  self-switches. No parallel copies to drift.
- **The content contract + "if it lints, it runs."** `pkmn/game/contract.py`
  is the single spec both the runtime and the linter read. Every new tile
  flag, layer rule, object type, event command, and trigger kind is added
  there first. This is how a growing feature set stays safe to author
  against.
- **An agnostic core.** No region literals in engine code; everything is
  learned from the content folder. The test still holds: grep the engine
  for a region string and every hit is a bug.
- **Uniform world primitives.** Every transition is a warp; interiors are
  just maps; the seamless overworld is one recursive `World.resolve`
  (Gen 1's `get_tile`); terrain behavior keys off a documented tile-flag
  vocabulary. We *expand* these vocabularies; we do not abandon the idea of
  having them.

## What we reverse

The "fixed vocabulary, not plugins" fork is resolved the other way:

- **The script layer becomes a real event runtime** — variables,
  self-switches, common events, multi-page conditional events,
  autorun/parallel triggers, move routes, control flow — exposed in both
  data and Python. (Compat Tier 2; see `docs/Features.md`.)
- **Per-game extension is supported, not forbidden.** A content folder may
  register custom commands and custom systems against stable engine
  interfaces. Composition is still preferred *within* a module, but the
  engine is now explicitly built to be extended rather than forked.
- **Map richness expands** to Essentials' model: multiple layers with draw
  priority, configurable tile size, autotiles, directional passability,
  panorama/fog. (Tier 1.)
- **Multi-active battles (double/triple/rotation) move into scope.**
  Previously a permanent exclusion; Essentials supports them, so they are a
  large, in-scope battle-module project.

## The model we commit to

Still three layers with a hard wall between them — the wall is what makes
the system modular even as it grows:

- **Core** — the loop, renderer, scene stack, deterministic rules, and the
  *interpreters/runtimes* for maps, warps, events, and data. The event
  runtime joins the battle engine as a first-class, pure-where-possible
  subsystem. No region-specific literal lives here.
- **Contract** — the versioned, validated spec of the content-folder
  format. It grows; the linter grows with it; they never diverge.
- **Content** — a game folder conforming to the contract, plus optional
  Python extension modules registered through documented seams. Nothing in
  it is privileged; the engine learns everything from it.

## Lessons we still take from Gen 1 (reframed)

The Lazy Devs teardown of Gen 1 Kanto remains instructive for *structure* —
a clean atomic→composite hierarchy with maximal reuse, connections+offsets
for a seamless world, a uniform warp table, and tile flags as an
interaction vocabulary. We keep all of that. What we explicitly **do not**
take is its constraint-driven minimalism as a design ceiling: the Game Boy
packed data and refused features because of tiny RAM and cartridge limits.
We run Python on modern machines and our north star is Essentials, not a
1996 cartridge. Copy the architecture of ideas; do not inherit the
limitations they were working around.

## Agnosticism & safety rules (unchanged, and now load-bearing)

- **No region literals in core.** Entry point, starter, rival, whiteout,
  intro — all manifest/data.
- **If it lints, it runs.** Extend `contract.py` first; the linter is the
  gate that keeps a bigger contract authorable.
- **`engine_version` in the manifest** so content and a fast-moving engine
  evolve without silent breakage.
- **Every subsystem ships behind a feature flag and a stable interface**,
  so a game uses as much or as little of the engine as it wants — a pure
  walking sim, a battle-only tool, or a full Essentials-class RPG.

See `docs/ROADMAP.md` for the phased project history and future milestones,
`docs/Features.md` for feature status, and `docs/PhaseProgress.md` for
current progress and acceptance criteria.
