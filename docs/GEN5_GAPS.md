# Gen 5 Feature-Gap Tracker

A running list of polish and systems that mainline Generation 5 (Black/White,
Black 2/White 2) shipped, measured against this engine. The battle **core** is
already deep (natures, IVs/EVs in the stat math, abilities, the physical/special
split, STAB, Gen 4/5 crits, weather-aware accuracy & damage, two-turn/charge
moves, Protect/Rest/leech-seed/traps/force-switch, priority+speed turn order, and
a real held-item suite). The gaps below are mostly in **meta, overworld, and
presentation** — exactly where Gen 5 added its flavor.

Effort key: **S** = small (hours), **M** = medium (a focused session),
**L** = large (multi-session / architectural). "BLOCKED" notes a hard
dependency that must be cleared first.

---

## Done (this pass)

- **Gen 5 scaled EXP** — `battle_exp` now uses the level-difference formula
  `((b·L)/(5·s))·a·(2L+10)^2.5 / (L+Lp+10)^2.5 + 1`, so beating higher-level
  foes pays more and tapers as you out-level them. Falls back to the flat award
  when the winner's level isn't supplied (keeps callers/tests working).
- **Gender / shiny / friendship** per Pokémon — derived at generation
  (gender from `gender_rate`, shiny at 1/4096, friendship 70), persisted in
  saves, and shown on the Summary screen.
- **Pokédex** — `seen`/`caught` tracking (foes registered on battle start, owned
  species on catch/new-game), a scrolling viewer (region roster in national-dex
  order, OWN / seen-name / dashes, Seen+Caught totals), and a PAUSE-menu entry.
- **Repel / Super Repel / Max Repel** — used from the bag; counts down each step
  and suppresses wild encounters while active (100 / 200 / 250 steps).
- **Escape Rope** — used from the bag; warps to the last heal point.
- **Poké Mart selling** — the shop now has BUY / SELL / EXIT; items sell for half
  their catalog cost.
- **Critical capture** — Gen 5's dex-count-scaled critical capture (a single
  decisive shake); the catch count is fed to the pure engine via `dex_caught`.
- **Return / Frustration** scale with friendship (also fixes them doing ~0
  damage, since their base power is `null` in the data).
- **Weather-tinted battle backdrop** — sky-over-ground replaces the flat fill,
  tinted for rain / sun / sandstorm / hail.
- **Held items give/take** — a party-menu ITEM action equips a holdable bag
  item to a Pokemon (swapping any current one) or takes it back; the held
  item shows on the party list and summary. This unlocks the held-item
  *effects* the battle engine already implements (Leftovers, Choice items,
  Life Orb, Focus Sash, berries, ...).
- **Audio** — a full procedural chiptune system (no asset files required):
  per-species cries seeded by dex number, 18 sound effects, and 7 looping
  songs (title / town / route / wild & trainer battle / victory / heal),
  wired to send-outs, hits, faints, the catch sequence, healing, level-ups,
  wall bumps, NPC/sign dialogue (start + advance), menu navigation, and
  saving; map `music` property; external OGG/MP3/WAV/MIDI
  override; a MIDI exporter + `pkmn.cli.audio` CLI; volume settings + `--mute`.

---

- **Day/night cycle** — phases (morning / day / evening / night) derived from
  the system clock tint the overworld and the battle backdrop. Configurable
  per region via the `daynight` setting ("auto" / "off" / a pinned phase) and
  overridable at launch with `--time` (`auto`/`off`/phase/hour). Triggers gain
  a `time` property so events can be day- or night-only; `Game.time_phase()`
  exposes the current phase to the rest of the engine.

- **Location/terrain battle backdrops** — a `battle_bg` map property selects
  the backdrop palette (field / forest / cave / water / sand / snow / mountain
  / indoor); weather recolours the sky over it and the day/night tint blends
  on top. The overworld sets it per map and `Game.battle_bg` carries it into
  both wild and trainer battles (the Triad's Shoreline Run uses `water`).

## TODO — Battle mechanics & presentation

- [ ] **EV yield from battle** — award a foe's effort values to the victors,
      capped 252/stat & 510 total. **BLOCKED**: species JSON has no
      `effort`/`ev_yield`; needs a PokeAPI regen through `datagen` (pokeapi.co is
      unreachable in this sandbox). Wiring is **S** once the data exists.
- [ ] **Animated battle sprites** — Gen 5 signature; the current battler is one
      frame. Needs multi-frame sprite data + a sheet pipeline. **M**.
- [ ] **Per-move animations / particle effects** and **stat-change / status
      flashes**. **M** / **S–M**.
- [ ] **Trainer VS intro** — trainer sprite slide-in and ball-throw at battle
      start. **M**.
- [ ] **PP Up / PP Max** items and a few remaining battle items
      (verify Dire Hit / Guard Spec coverage). **S**.

## TODO — Pokémon data & progression

- [ ] **Full shiny sprite recolor** (palette swap) — currently shiny is tracked
      and tagged but not recolored. **M**.
- [ ] **Friendship growth** (level-ups, walking, vitamins, faint penalty) and
      **friendship-based evolutions**. **M**.
- [ ] **Hidden / Dream World abilities** — data + assignment rules. **M**.
- [ ] **Breeding** — Daycare, Eggs, hatching, IV/nature/egg-move inheritance.
      **L**.
- [ ] **Move relearner (Heart Scale), Move Deleter, Move Tutors** — scriptable
      service NPCs + a teach/forget UI. **M**.
- [ ] **TMs / HMs as reusable teaching items** (Gen 5 made TMs reusable) —
      item→move map + teach UI + HM field gating. **M**.
- [ ] **Nicknaming UI** (at catch and via Name Rater) — needs an on-screen
      text-entry widget (none exists yet). **M**.
- [ ] **Characteristics** (flavor from highest IV). **S**.

## TODO — Overworld systems

- [ ] **Seasons** (spring / summer / autumn / winter) — *the* Gen 5 signature.
      Affects encounter tables, tile appearance, and some forms/evolutions. Needs
      a time system + season-keyed region data. **M–L**.
- [ ] **Overworld weather + particles** — weather already feeds battles but isn't
      drawn in the field (rain/snow/sand). **M**.
- [ ] **Hidden items** (Dowsing Machine). **S–M**.
- [ ] **Rare-encounter hotspots** — rustling grass, dust clouds, rippling water,
      a flying Pokémon's shadow. **M**.
- [ ] **Hidden Grottoes**. **M**.
- [ ] **Fishing** — rod items + water encounter tables. **M**.
- [ ] **Bicycle** — faster movement + bike-only terrain. **S–M**.
- [ ] **Remaining HMs** — Fly, Strength, Waterfall, Dive, Rock Smash, Rock Climb,
      Flash (only Surf + Cut exist today). ~**M** each.
- [ ] **Field-move v1 shortcuts** — cut trees should regrow on re-entry; add a
      dedicated surf sprite. **S**.
- [ ] **Berry planting / growth over time**; **Sweet Scent / Honey** forced
      encounters. **M** / **S**.

## TODO — Items, bag & shops

- [ ] **Bag pockets** (Items / Medicine / Poké Balls / Berries / TMs / Key Items)
      + sorting + a quick-use registration slot. **S–M**.

## TODO — NPCs, services & progression gating

- [ ] **Badges + obedience + HM field-use gating**. **M**.
- [ ] **Trainer rematches / Vs Seeker**. **M**.
- [ ] **Trainer card**. **S**.
- [ ] **PC box** — naming, wallpaper, sorting, search, multiple boxes (a single
      box exists). **M**.

---

## TODO — Game shell

- [ ] **Configurable title screen** — a start screen shown before the
      overworld (logo/art, a "Press Start" prompt, New Game / Continue),
      with the region manifest supplying the title art, text, and music.
      The game currently boots straight into the overworld. **M**.

## Out of scope (online / heavily post-game)

Battle Subway, Entralink, Dream World, Pokémon Musical, C-Gear / wireless,
Global Link, Xtransceiver video calls, Pokéstar Studios (Pokéwood), Join Avenue.

Multi-Pokemon battle formats — **double, triple, and rotation battles** — are
intentionally excluded by project decision. The engine stays single-active.
These depend on networking or large post-game subsystems outside this engine's
single-player, region-as-data scope.

---

### Notes for whoever picks this up

- The contract in `pkmn/game/contract.py` is the single source of truth shared by
  the runtime and the linter — extend flags/objects/commands there first so
  "if it lints, it runs" stays true.
- The battle engine is intentionally pure (actions in, typed events out; it never
  imports game state). Features that need outside data (like critical capture's
  catch count) should pass it in as a constructor argument, as `dex_caught` does.
- Clearing the **EV-yield** and **animated-sprite** blockers both come down to a
  richer data pull in `pkmn/datagen` — worth doing together.
