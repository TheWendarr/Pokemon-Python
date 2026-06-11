# Roadmap

Each phase has acceptance criteria; a phase isn't done until they pass.

## Phase 0 — Foundations  [DONE]
Repo structure, canonical data models, GameData repository, PokeAPI
pipeline (REST + CSV) generating Gen 1-5 data with Gen 5 values.
*Accepted:* dataset generated and value-checked (Thunderbolt 95, no
Fairy, Steel resists Ghost/Dark).

## Phase 1 — Battle core  [DONE]
Pure seeded engine: Gen 5 damage, statuses, stages, ordering, PP +
Struggle, switching, items, flee/catch, baseline AIs, CLI demo.
*Accepted:* 50 pytest cases incl. hand-verified damage; seeded AI-vs-AI
battle runs to completion on real data.

## Phase 2 — Battle completeness
Abilities (start: Intimidate, Levitate, Static, Guts, Sturdy), held
items (Leftovers, Oran, choice items), weather, entry hazards, two-turn
and rampage moves, Protect, crit-stage modifiers, smarter AI tiers.
*Accept:* a B/W in-game trainer team battles correctly end to end;
EFFECT_SKIPPED rate < 5% across all Gen 5 move usage.

## Phase 3 — Overworld v1
Pygame-CE renderer, Tiled (.tmx via pytmx) maps, player movement +
collision, NPCs, map transitions, grass encounters wired to the engine,
battle UI consuming the existing Event stream.
*Accept:* walk a test town, enter grass, fight and catch a wild Pokemon.

## Phase 4 — Events & scripting
Flag/variable store, trigger system (step-on, interact, auto), a small
script command set (dialogue, move NPC, give item, start battle, warp),
trainer line-of-sight battles.
*Accept:* scripted rival battle with pre/post dialogue gated by flags.

## Phase 5 — Game systems
Save/load (whole-game serialization), party management UI, bag, PC
boxes, experience/leveling/evolution/move-learning, Pokemon Centers.
*Accept:* full loop — catch, train, evolve, save, reload, continue.

## Phase 6 — Authoring toolkit
"Game folder" format (maps, trainers, scripts, encounters, dex subset)
+ validation CLI; example mini-region built only with the toolkit;
asset-agnostic (users supply their own tilesets/sprites).
*Accept:* the example region plays start to finish from a folder that
contains no engine code.
