# Architecture

## Why a rewrite

The autopsy of the original prototype found structural problems that
patching couldn't fix:

* **Two parallel battle engines** (`Battle.py` and `engine.py`) and two
  orchestrators, one of which had a literal `pass` where battles should
  run. Neither was authoritative.
* **Three sources of truth** for a Pokemon's state: roster JSON dicts,
  `Pokemon` instances, and the engine's deep copies (which silently
  reset HP to full). Display, persistence, and simulation disagreed.
* **Key-format drift**: species data normalized stats to underscores
  while the engines indexed `'special-attack'` — a guaranteed KeyError
  on the first special move. Party files used a third format.
* **Wrong-generation constants**: Gen 6 crit multiplier (1.5x) and
  damage roll (90-100%), Gen 1 approximate stage multipliers.

## The replacement model

```
GameData (pkmn/data)          PokemonState (pkmn/core)
  reads the game folder         the ONE persistent Pokemon:
  once, caches, normalizes      species/level/IVs/EVs/nature,
  keys at the boundary          move slots w/ PP, HP, status
        |                                 |
        v                                 v
BattleEngine (pkmn/battle) -- wraps each PokemonState in a
  BattlePokemon (stages + volatiles), consumes Actions, emits Events.
  Pure: injected RNG, no I/O. HP/PP/status mutations go straight to
  PokemonState, so post-battle persistence is automatic.
        |
        v
Renderers (pkmn/cli today, pygame in Phase 3)
  translate the Event stream to text/animation. format_event() in
  cli/battle_demo.py is the canonical translator.
```

### Phase machine

`WAITING_ACTIONS -> submit_turn(a1, a2) -> [WAITING_REPLACEMENT ->
submit_replacement(side, idx)]* -> ... -> OVER`. The engine never blocks
on input, which makes it equally driveable by a CLI loop, a pygame event
loop, or an AI-vs-AI test harness.

### Move execution

`MoveEffect` mirrors PokeAPI's move meta (ailment, chances, stat
changes, drain/recoil, hit counts, healing). A single interpreter in
`battle/moves.py` executes any move from that metadata; special cases
register named handlers (`@handler("rest")`). Unknown effects emit
`EFFECT_SKIPPED` events rather than misbehaving silently — grep the
event log to measure coverage.

One data quirk worth knowing: PokeAPI's `damage+raise` category means
the stat changes apply to the **user** (this includes Superpower's and
Overheat's self-drops, which are negative "raises"), while
`damage+lower` applies to the **target**. The interpreter encodes this.

### Gen 5 fidelity notes

Implemented to Gen 5 values: 2.0x crits at 1/16 base (ignoring helpful
stages), 85-100% damage roll, integer-floor damage pipeline, exact stage
fractions, paralysis speed/4 + 25% block, sleep 1-3 turns (re-rolled on
re-entry), 20% thaw + defrost flag + fire-move thaw, 1/8 burn and
poison, ramping n/16 toxic with counter reset on switch, Gen 5 flee and
capture formulas, Thunder Wave's type-immunity check, Gen 2-5 status
type immunities (Electric CAN be paralyzed pre-Gen 6), Struggle with
1/4 max-HP recoil, Gen 5 2-5 multi-hit distribution.

Known simplifications (documented so they're decisions, not surprises):

* Modifier rounding uses plain floors rather than the games'
  round-half-down at every step; damage can differ by 1 in rare rolls.
* Sleep counter semantics: counter = failed turns; Rest = exactly 2.
* Capture uses 4 shake checks, no critical-capture mechanic.
* Run/item/switch ordering uses fixed category priorities (run > item >
  switch > moves) rather than per-gen edge cases like Pursuit.

## Phase 2 hook points

* `BattleEngine.crit_chance_for` — Focus Energy, Scope Lens, Super Luck.
* `_end_of_turn` — weather, Leftovers, hazard bookkeeping.
* `HANDLERS` registry — two-turn moves, counters, field effects.
* `BattlePokemon` — held-item slot and ability triggers.
* `MoveData.flags` already carries PokeAPI flags (`contact`, `protect`,
  `defrost`, ...) for ability/item interactions.

## Phase 2 additions

* **`pkmn/battle/passives.py`** — every ability and held-item hook in
  one place (stat/power/speed modifiers, immunities and absorbs,
  contact punishment, switch-in effects, end-of-turn residuals,
  survive-lethal). Adding an ability usually touches only this file.
* **`pkmn/battle/field.py`** — `SideState`: hazards (Spikes layers,
  Toxic Spikes layers, Stealth Rock) and timed side conditions
  (Reflect, Light Screen, Safeguard, Mist, Lucky Chant, Tailwind,
  Healing Wish). Weather lives on the engine (whole-field).
* **Two-turn flow** — charge/semi-invulnerable state, recharge turns,
  and rampage locks are engine concerns (`_do_move`); `legal_actions`
  reflects every lock (charging, recharging, rampaging, choice items,
  Encore, Torment, Taunt, Imprison, trapping).
* **Handler registry** — ~50 moves with bespoke behavior register via
  `@handler("move-id")` in `moves.py`. Unknown effects still emit
  `EFFECT_SKIPPED`, and `pkmn/cli/coverage.py` measures the honest gap.

### Documented simplifications
* Attract ignores gender (genders aren't modeled yet) and always takes.
* Baton Pass sends a random able bench member (a client will prompt in
  Phase 3); stages and passable volatiles carry over, hazards apply.
* Mud/Water Sport last 5 turns instead of "while the user is active".
* Weather moves ignore the duration-extending rocks (Damp Rock etc.).
* Sleep counters tick on failed move attempts, not elapsed turns.

## Phase 3 additions (`pkmn/game/`)

* **`scene.py`** — `Game` shell + scene stack + an `Input` abstraction.
  The pygame event pump only *feeds* Input, so tests drive the real
  game frame by frame with SDL's dummy drivers — every client test runs
  headless in CI.
* **`tilemap.py`** — pytmx wrapper exposing the gameplay queries
  (blocked / tall grass via tile properties; warps, NPCs, signs, spawn
  via the object layer). Maps remain ordinary Tiled files.
* **`overworld.py`** — grid movement with pixel interpolation, NPC
  collision + interaction, warp handling, encounter rolls.
* **`battle_scene.py`** — a state machine (msg/menu/moves/bag/party)
  over the pure engine. Battle text comes from the same `format_event`
  as the CLI demo; HP bars animate toward engine truth each frame. The
  engine still never imports the client.
* **`tools/make_assets.py`** — procedurally draws the tileset and
  character strips and writes the .tmx maps, so the repo ships no
  third-party art.
