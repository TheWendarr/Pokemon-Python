# Item Implementation Plan — Gen 5 (BW / B2W2)

**Data source:** `game/data/items.json` — 678 items across 8 pockets.
**Scope:** Mechanically relevant items only. Contest, mail, Pokéathlon, baking,
and plot-key items are omitted — they have no engine effect.

---

## Already Implemented

### Held items — damage (passives.py)
| Item | Effect | Hook |
|------|--------|------|
| Choice Band | ×1.5 Attack | `atk_mod` |
| Choice Specs | ×1.5 Sp.Atk | `atk_mod` |
| Choice Scarf | ×1.5 Speed | `speed_mod` + choice lock |
| Life Orb | ×1.3 damage, −10% HP recoil | `atk_mod` + `on_damage_dealt` |
| Expert Belt | ×1.2 on super-effective | `effectiveness_mod` |
| All 17 Gems | ×1.5 matching type, consume | `atk_mod` (TYPE_GEMS dict) |
| All Plates (16) | ×1.2 matching type | `atk_mod` (TYPE_BOOST_ITEMS dict) |
| Type enhancers (20) | ×1.2 matching type | `atk_mod` (TYPE_BOOST_ITEMS dict) |

*Type enhancers:* charcoal, mystic-water, magnet, miracle-seed, never-melt-ice,
hard-stone, silk-scarf, twisted-spoon, black-belt, sharp-beak, poison-barb,
soft-sand, spell-tag, metal-coat, black-glasses, silver-powder, dragon-fang,
sea-incense, odd-incense, rock-incense, wave-incense, rose-incense.

### Held items — defense / survival (passives.py)
| Item | Effect | Hook |
|------|--------|------|
| Focus Sash | Survive any single hit at full HP → 1 HP, consume | `on_pre_damage` |
| Eviolite | ×1.5 Def + Sp.Def if not fully evolved | `def_mod` |
| Assault Vest | ×1.5 Sp.Def; blocks status moves | `def_mod` + `legal_actions` |
| Rocky Helmet | −1/6 foe HP on contact hit received | `on_damage_received` |

### Held items — end-of-turn (passives.py)
| Item | Effect | Hook |
|------|--------|------|
| Leftovers | +1/16 max HP | `end_of_turn` |
| Flame Orb | Inflict burn if no status | `end_of_turn` |
| Toxic Orb | Inflict toxic if no status | `end_of_turn` |

### Held items — crit (passives.py)
| Item | Effect | Hook |
|------|--------|------|
| Scope Lens | +1 crit stage | `crit_stage` |
| Razor Claw | +1 crit stage | `crit_stage` |

### Held berries (passives.py)
| Item | Trigger | Effect |
|------|---------|--------|
| Oran Berry | ≤50% HP | +10 HP, consume |
| Sitrus Berry | ≤50% HP | +25% max HP, consume |
| Lum Berry | Any status/confusion | Cure all, consume |
| Cheri Berry | Paralysis | Cure, consume |
| Chesto Berry | Sleep | Cure, consume |
| Pecha Berry | Poison/Toxic | Cure, consume |
| Rawst Berry | Burn | Cure, consume |
| Aspear Berry | Freeze | Cure, consume |
| Persim Berry | Confusion | Cure confusion, consume |

### Bag-use items — engine._do_item() (structured fields)
| Category | Items | Field |
|----------|-------|-------|
| Healing | Potion, Super Potion, Hyper Potion, Max Potion, Full Restore, Fresh Water, Soda Pop, Lemonade, Moomoo Milk, Energy Powder, Energy Root, Berry Juice, Sweet Heart | `heal` |
| Status cures | Antidote, Burn Heal, Ice Heal, Awakening, Paralyze Heal, Full Heal, Heal Powder, Lava Cookie, Old Gateau, Casteliacone | `cures` |
| Full Restore | Both heal and cures | `heal` + `cures` |
| Revives | Revive (50%), Max Revive (100%), Revival Herb (100%), Sacred Ash (all) | `revive` |
| Stat boosts | X-Attack, X-Defense, X-Speed, X-Sp.Atk, X-Sp.Def, X-Accuracy | `stages` |
| Crit boost | Dire Hit | `crit` |
| Mist effect | Guard Spec. | `guard` |

---

## Not Yet Implemented — Grouped by Batch

### Batch A — Damage passives (easy, pre/post-damage hooks)

**Target:** `passives.py` — `atk_mod` / `on_damage_dealt`

| Item | Effect | Notes |
|------|--------|-------|
| Muscle Band | ×1.1 physical moves | Attacker pre-damage |
| Wise Glasses | ×1.1 special moves | Attacker pre-damage |
| Shell Bell | Heal 1/8 HP dealt after attacking | Post-damage; check for sub hit |
| Big Root | ×1.3 HP from draining moves, Ingrain, Aqua Ring | Drain multiplier in passives |
| Binding Band | ×2 per-turn trap damage | Applied in trap EOT |

---

### Batch B — End-of-turn held items

**Target:** `passives.py` — `end_of_turn` (called once per mon per EOT)

| Item | Effect | Notes |
|------|--------|-------|
| Black Sludge | Poison-type: +1/16 HP. Non-Poison: −1/8 HP | Check holder's type |
| Sticky Barb | −1/8 HP EOT; on contact hit received, passes to attacker | EOT + contact hook |
| White Herb | Reset all lowered stages to 0, consume | Fire when any stage < 0 |
| Mental Herb | Gen 5: cure infatuation, Taunt, Encore, Torment, Disable, Heal Block; consume | Fire when any applies |
| Weather rocks | Extend weather set by this mon to 8 turns instead of 5 | Hook in weather-set handler |
| Heat Rock | Sun → 8 turns | — |
| Damp Rock | Rain → 8 turns | — |
| Smooth Rock | Sandstorm → 8 turns | — |
| Icy Rock | Hail → 8 turns | — |
| Light Clay | Reflect/Light Screen last 8 turns instead of 5 | Hook in screen-set handler |

---

### Batch C — Accuracy / Speed / Priority modifiers

**Target:** `passives.py` — `accuracy_mod`, `speed_mod`, `priority_mod`

| Item | Effect | Notes |
|------|--------|-------|
| Bright Powder | +11.1% evasion to holder | Defender evasion hook |
| Wide Lens | +10% accuracy | Attacker accuracy hook |
| Zoom Lens | +20% accuracy if holder moves after target | Check turn order |
| Quick Claw | 18.75% chance to move first within bracket | Pre-sort hook; random check |
| Lagging Tail | Always last in priority bracket | Sort modifier = −999 |
| Full Incense | Always last in priority bracket | Same as Lagging Tail |
| Iron Ball | Halve speed; negate Flying immunity to Ground; negate Levitate | `speed_mod` + grounded check |
| Metronome (item) | Consecutive same-move bonus ×10% per use, cap ×100% | Track streak in vol; reset on move change |
| Kings Rock | +10% flinch chance on damaging moves | Secondary effect hook |
| Razor Fang | +10% flinch chance on damaging moves | Same as Kings Rock |

---

### Batch D — Trigger-on-hit held items

**Target:** `passives.py` — `on_damage_received` (after damage resolution)

| Item | Effect | Notes |
|------|--------|-------|
| Air Balloon | Ground immunity; pop (consumed) on any damaging hit | Immunity in type-check; pop in damage hook |
| Red Card | When holder takes damage: force attacker to switch; consume | Force-switch event; needs engine support |
| Eject Button | When holder takes damage: holder switches out; consume | Needs pending-replacement hook |
| Ring Target | Removes all type immunities (inc. Levitate-like) | Type-effectiveness check |
| Absorb Bulb | When hit by Water move: +1 Sp.Atk, consume | Type-trigger in damage received |
| Cell Battery | When hit by Electric move: +1 Atk, consume | Type-trigger in damage received |
| Destiny Knot | When holder is infatuated: also infatuate attacker | Infatuation applied hook |
| Shed Shell | Can switch out even when trapped | Filter in `legal_actions` |
| Grip Claw | Trap always lasts exactly 5 turns (not random 4–5) | Set trap_turns = 5 |

---

### Batch E — Berries (held, consume on trigger)

**Target:** `passives.py` — existing berry-check hooks + new ones

#### Pinch berries (activate at ≤25% max HP, after damage)
| Item | Effect |
|------|--------|
| Liechi Berry | +1 Attack |
| Ganlon Berry | +1 Defense |
| Salac Berry | +1 Speed |
| Petaya Berry | +1 Sp.Atk |
| Apicot Berry | +1 Sp.Def |
| Starf Berry | +2 random stat |
| Lansat Berry | +2 crit stage |
| Micle Berry | Next move +20% accuracy |
| Custap Berry | Go first within priority bracket (like Quick Claw but guaranteed) |

#### Type-protection berries (halve super-effective damage, consume)
All 17: Occa (Fire), Passho (Water), Wacan (Electric), Rindo (Grass),
Yache (Ice), Chople (Fighting), Kebia (Poison), Shuca (Ground),
Coba (Flying), Payapa (Psychic), Tanga (Bug), Charti (Rock),
Kasib (Ghost), Haban (Dragon), Colbur (Dark), Babiri (Steel),
Chilan (Normal — halves even neutral Normal hits)

**Implementation:** single map `RESIST_BERRY: {item_id: type}` checked in
`on_damage_received` when `effectiveness >= 2.0`.

#### Flavor berries (heal at ≤50% HP, may confuse)
| Item | Likes stat | Effect |
|------|-----------|--------|
| Figy Berry | Atk | +1/8 max HP; confuse if nature dislikes Spicy |
| Wiki Berry | Sp.Atk | +1/8 max HP; confuse if nature dislikes Dry |
| Mago Berry | Spd | +1/8 max HP; confuse if nature dislikes Sweet |
| Aguav Berry | Sp.Def | +1/8 max HP; confuse if nature dislikes Bitter |
| Iapapa Berry | Def | +1/8 max HP; confuse if nature dislikes Sour |

#### Retaliatory berries (consume on specific damage type)
| Item | Trigger | Effect |
|------|---------|--------|
| Enigma Berry | Hit by super-effective move | Heal 1/4 max HP |
| Jaboca Berry | Hit by physical move | Deal 1/8 attacker's max HP to attacker |
| Rowap Berry | Hit by special move | Deal 1/8 attacker's max HP to attacker |

#### PP berry
| Item | Trigger | Effect |
|------|---------|--------|
| Leppa Berry | A move slot hits 0 PP | Restore that move's PP by 10 |

---

### Batch F — Species-specific held items

**Target:** `passives.py` — `atk_mod` / `def_mod` / `crit_stage` checks gated by species

| Item | Holder | Effect |
|------|--------|--------|
| Light Ball | Pikachu | ×2 Atk + Sp.Atk |
| Thick Club | Cubone, Marowak | ×2 Atk |
| Lucky Punch | Chansey | +2 crit stage |
| Stick | Farfetch'd | +2 crit stage |
| Deep Sea Tooth | Clamperl | ×2 Sp.Atk |
| Deep Sea Scale | Clamperl | ×2 Sp.Def |
| Soul Dew | Latias, Latios | ×1.5 Sp.Atk + Sp.Def |
| Adamant Orb | Dialga | ×1.2 Dragon and Steel moves |
| Lustrous Orb | Palkia | ×1.2 Dragon and Water moves |
| Griseous Orb | Giratina | ×1.2 Dragon and Ghost moves |
| Quick Powder | Ditto (untransformed) | ×2 Speed |
| Metal Powder | Ditto (untransformed) | ×2 Def + Sp.Def |
| Douse Drive | Genesect | Techno Blast → Water |
| Shock Drive | Genesect | Techno Blast → Electric |
| Burn Drive | Genesect | Techno Blast → Fire |
| Chill Drive | Genesect | Techno Blast → Ice |

---

### Batch G — Bag-use items (overworld + in-battle use from bag)

**Target:** `engine._do_item()` — new field support or targeted UI

| Item | Missing piece |
|------|--------------|
| Ether | Target a move slot; restore 10 PP. Needs `target_move` on ItemAction |
| Max Ether | Same; restore to full |
| Elixir | Restore 10 PP to all moves |
| Max Elixir | Restore all moves to full PP |
| PP Up | Increase a move's max PP by 1/5 (out-of-battle only) |
| PP Max | Raise a move's max PP to full (out-of-battle only) |
| HP Up | +10 HP EVs (cap 100 per stat, 510 total) |
| Protein | +10 Atk EVs |
| Iron | +10 Def EVs |
| Calcium | +10 Sp.Atk EVs |
| Zinc | +10 Sp.Def EVs |
| Carbos | +10 Spd EVs |
| EV-drop berries | −10 EVs to target stat (Pomeg/Kelpsy/Qualot/Hondew/Grepa/Tamato) |

---

### Batch H — Overworld-only items (no battle hook needed)

| Item | Overworld effect | Status |
|------|-----------------|--------|
| Poké Balls (all) | Already wired via CatchAction | ✅ |
| Repel, Super Repel, Max Repel | Reduce encounter rate for N steps | Not yet |
| Escape Rope | Warp to dungeon entrance / last heal point | Not yet |
| TMs / HMs (103) | Teach move to compatible Pokémon | Not yet (overworld menu) |
| Evolution stones | Trigger evolution in party menu | Not yet |
| Fossils | Revive at specific NPC | Not yet (NPC-driven) |
| Bicycle | Speed up overworld movement | Not yet |

---

## Overworld Bag — UI Gaps

The current bag UI (`battle_scene.py`, `menus.py`) lists items flat. Gen 5 splits
the bag into 6 pockets. Recommended mapping to existing pocket field:

| Pocket (data) | Gen 5 UI label | Contents |
|---------------|---------------|----------|
| `medicine` | Items | Potions, status cures, PP items, vitamins |
| `pokeballs` | Poké Balls | All ball variants |
| `machines` | TMs & HMs | All 103 machines |
| `berries` | Berries | All berry items |
| `battle` | Battle Items | X-items, Flutes, Dire Hit, Guard Spec. |
| `key` | Key Items | All plot/field/HM-gate items |
| `misc` | Free Space / Misc | Held items, gems, evolution stones, loot |

**Gaps in the overworld bag:**
1. **Pocket tabs** — UI only shows a flat list; add left/right navigation between pockets.
2. **PP recovery targeting** — Ether/Elixir need a sub-menu to pick a move slot on a party member.
3. **Vitamin application** — HP Up etc. need EV tracking on `PokemonState` (field exists via `pkmn/datagen`; just needs the bag-use hook).
4. **Held item assignment** — no UI exists to give a held item to a party Pokémon; needed for non-scripted item distribution.
5. **TM teaching** — pick a TM, pick a compatible party member, replace a move slot.
6. **Repel step counter** — `GameState` needs a `repel_steps: int` field; overworld checks it before rolling encounters.
7. **Evolution stone trigger** — party menu item → check species `evolution_items` list → evolve.

---

## Implementation Priority

| Priority | Batch | Rationale |
|----------|-------|-----------|
| 1 | A (damage passives) | High tournament impact; 5-line each |
| 2 | B (EOT held) | Completes competitive item set |
| 3 | E – pinch + resist berries | Used in virtually every serious team |
| 4 | C (accuracy/speed/priority) | Needed for accurate turn-order simulation |
| 5 | D (trigger-on-hit) | Red Card / Eject Button need switch hooks |
| 6 | E – flavor + retaliatory berries | Niche; easy once berry framework done |
| 7 | F (species-specific) | Narrow scope; straightforward |
| 8 | G (PP + vitamins in bag) | UI work; out-of-battle only |
| 9 | H (overworld bag UI) | UX polish |

---

## Implementation Notes

- **`on_damage_dealt` hook** — add to `passives.py`; called from `moves.py` after
  damage is applied to the *real* Pokémon (not the substitute). Shell Bell, Big Root
  multiplier, and Life Orb recoil all belong here.
- **`on_damage_received` hook** — already implied by Rocky Helmet; formalize it so
  Absorb Bulb, Cell Battery, Air Balloon pop, Jaboca/Rowap all share one call site.
- **Pinch berry check** — add a single `check_pinch_berry(bp, eng, events)` helper
  called after each damage event; checks `current_hp <= max_hp // 4` for all pinch
  and resist berries.
- **Weather rock hook** — weather setters in `moves.py` already set `eng.weather_turns`.
  If the setter's held item matches a rock, multiply by `8 / 5`.
- **Metronome vol field** — add `vol.metronome_streak: int = 0` +
  `vol.metronome_move: str = ""` to `Volatiles`; reset on any move change.
- **Quick Claw / Custap Berry** — resolved in `submit_turn` speed sort: sample a
  uniform float per actor; if Quick Claw triggers, sort key gets +∞ within bracket.
- **Air Balloon immunity** — add `air_balloon_active: bool` to Volatiles (set on
  switch-in if item == air-balloon); grounded-check already reads `levitate`.
  Popped in `on_damage_received` by any damaging move (not sub).
