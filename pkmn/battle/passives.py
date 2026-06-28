"""Passive effects: abilities and held items.

Pure hook functions consumed by damage.py, moves.py, and engine.py.
Adding an ability or item usually means touching only this file.
"""
from __future__ import annotations

from .events import E, Event

CHOICE_ITEMS = ("choice-band", "choice-specs", "choice-scarf")
PINCH_ABILITIES = {"blaze": "fire", "torrent": "water",
                   "overgrow": "grass", "swarm": "bug"}
STATUS_BLOCK = {"limber": "paralysis", "immunity": "poison",
                "insomnia": "sleep", "vital-spirit": "sleep",
                "water-veil": "burn", "magma-armor": "freeze",
                "sweet-veil": "sleep"}
CONTACT_STATUS = {"static": "paralysis", "poison-point": "poison",
                  "flame-body": "burn"}
WEATHER_SETTERS = {"drizzle": "rain", "drought": "sun",
                   "sand-stream": "sandstorm", "snow-warning": "hail"}
WEATHER_SPEED = {"swift-swim": "rain", "chlorophyll": "sun",
                 "sand-rush": "sandstorm"}
SAND_IMMUNE_ABILITIES = ("sand-rush", "sand-veil", "sand-force", "overcoat")

# Sound moves: blocked by Soundproof
SOUND_MOVES = {
    "growl", "roar", "sing", "supersonic", "screech", "snore",
    "bug-buzz", "chatter", "echoed-voice", "round", "hyper-voice",
    "uproar", "perish-song", "grasswhistle", "heal-bell",
    "noble-roar", "relic-song", "boomburst", "sonic-boom",
}

# Powder moves: blocked by Overcoat and Grass types (Gen 6+; here just Overcoat)
POWDER_MOVES = {
    "stun-spore", "sleep-powder", "poison-powder", "cotton-spore",
    "spore", "powder", "rage-powder", "magic-powder",
}

# Absorb-and-raise family: type immunity + raise on hit
ABSORB_RAISE = {
    # ability: (immune_type, stat_to_raise, raise_amount)
    "motor-drive": ("electric", "speed", 1),
    "lightning-rod": ("electric", "special_attack", 1),
    "sap-sipper": ("grass", "attack", 1),
    "storm-drain": ("water", "special_attack", 1),
}

TYPE_BOOST_ITEMS = {
    "draco-plate": "dragon", "dread-plate": "dark", "earth-plate": "ground",
    "fist-plate": "fighting", "flame-plate": "fire", "icicle-plate": "ice",
    "insect-plate": "bug", "iron-plate": "steel", "meadow-plate": "grass",
    "mind-plate": "psychic", "pixie-plate": "fairy", "sky-plate": "flying",
    "splash-plate": "water", "spooky-plate": "ghost", "stone-plate": "rock",
    "toxic-plate": "poison", "zap-plate": "electric",
    "charcoal": "fire", "mystic-water": "water", "magnet": "electric",
    "miracle-seed": "grass", "never-melt-ice": "ice", "hard-stone": "rock",
    "silk-scarf": "normal", "twisted-spoon": "psychic", "black-belt": "fighting",
    "sharp-beak": "flying", "poison-barb": "poison", "soft-sand": "ground",
    "spell-tag": "ghost", "metal-coat": "steel", "black-glasses": "dark",
    "silver-powder": "bug", "dragon-fang": "dragon",
}

TYPE_GEMS = {
    "fire-gem": "fire", "water-gem": "water", "electric-gem": "electric",
    "grass-gem": "grass", "ice-gem": "ice", "fighting-gem": "fighting",
    "poison-gem": "poison", "ground-gem": "ground", "flying-gem": "flying",
    "psychic-gem": "psychic", "bug-gem": "bug", "rock-gem": "rock",
    "ghost-gem": "ghost", "dragon-gem": "dragon", "dark-gem": "dark",
    "steel-gem": "steel", "normal-gem": "normal",
}

# Every ability id the battle hooks below act on. The audit CLI compares
# this against the full abilities.json catalog; anything not listed is
# inert in battle (data-only) until a hook is added.
IMPLEMENTED_ABILITIES = frozenset({
    "huge-power", "pure-power", "guts", "technician", "blaze", "torrent",
    "overgrow", "swarm", "thick-fat", "super-luck", "limber", "immunity",
    "insomnia", "vital-spirit", "water-veil", "magma-armor", "own-tempo",
    "levitate", "volt-absorb", "water-absorb", "shield-dust",
    "serene-grace", "sturdy", "rough-skin", "iron-barbs", "static",
    "poison-point", "flame-body", "intimidate", "drizzle", "drought",
    "sand-stream", "snow-warning", "swift-swim", "chlorophyll",
    "sand-rush", "sand-veil", "sand-force", "natural-cure", "speed-boost",
    # Phase B abilities
    "flash-fire", "motor-drive", "lightning-rod", "sap-sipper", "storm-drain",
    "dry-skin", "iron-fist", "reckless", "sheer-force", "adaptability",
    "tinted-lens", "filter", "solid-rock", "multiscale", "shadow-shield",
    "hustle", "marvel-scale", "compound-eyes", "no-guard", "wonder-skin",
    "scrappy", "download", "trace", "ice-body", "rain-dish", "solar-power",
    "poison-heal", "effect-spore", "mummy", "defiant", "competitive",
    "justified", "steadfast", "weak-armor", "synchronize", "early-bird",
    "magic-guard", "sweet-veil", "pressure", "unburden", "contrary",
    "eviolite", "assault-vest",
    # Additional Gen 5 catalog abilities
    "battle-armor", "shell-armor",   # immune to crits
    "clear-body", "hyper-cutter", "white-smoke",  # stat-lower immunity
    "big-pecks",    # Defense cannot be lowered
    "damp",         # explosion/selfdestruct fail
    # Batch: 58 newly implemented / registered abilities
    "inner-focus",      # prevents flinching
    "keen-eye",         # blocks accuracy drops; ignores foe evasion
    "run-away",         # wild-battle escape (trainer battles: no effect)
    "oblivious",        # blocks infatuation / attract
    "hydration",        # cures status in rain each turn
    "gluttony",         # registered (pinch berries not yet implemented)
    "rock-head",        # no self-recoil from recoil moves
    "unnerve",          # foe cannot eat berries
    "overcoat",         # immune to weather chip + powder moves
    "regenerator",      # heal 1/3 HP on switch-out
    "rivalry",          # registered (genders not modeled)
    "shed-skin",        # 33% chance to cure status each turn
    "frisk",            # reveals foe's held item on entry
    "leaf-guard",       # blocks status in sun
    "telepathy",        # doubles-only; registered
    "infiltrator",      # bypasses screens
    "soundproof",       # immune to sound moves
    "sniper",           # crits do 2.25× instead of 2×
    "mold-breaker",     # moves ignore target's abilities
    "analytic",         # +30% power if moving last
    "cute-charm",       # 30% infatuate on contact
    "rattled",          # +1 Speed hit by Dark/Ghost/Bug
    "prankster",        # status moves gain +1 priority
    "moxie",            # +1 Attack after KO
    "pickup",           # overworld only; registered
    "snow-cloak",       # +evasion in hail
    "stench",           # 10% flinch on contact
    "quick-feet",       # +50% Speed when statused; ignores paralysis penalty
    "sticky-hold",      # held item cannot be stolen
    "aftermath",        # 25% damage to attacker when holder faints from contact
    "plus",             # doubles-only; registered
    "klutz",            # cannot use held item in battle
    "anticipation",     # reveals dangerous moves on entry
    "unaware",          # ignores foe's stat stages
    "moody",            # +2 random stat, -1 another, each turn
    "anger-point",      # maxes Attack on critical hit taken
    "tangled-feet",     # evasion boost when confused
    "skill-link",       # always hits max times on multi-hit moves
    "cloud-nine",       # suppresses weather effects
    "cursed-body",      # 30% disable on contact
    "illuminate",       # overworld only; registered
    "forewarn",         # reveals foe's highest-power move on entry
    "minus",            # doubles-only; registered
    "heavy-metal",      # doubles weight (weight-based moves)
    "healer",           # doubles-only; registered
    "light-metal",      # halves weight
    "simple",           # doubles stat-stage changes
    "friend-guard",     # doubles-only; registered
    "poison-touch",     # 30% poison on contact
    "shadow-tag",       # prevents foe from switching
    "magnet-pull",      # prevents Steel-type foe from switching
    "pickpocket",       # steals attacker's item on contact
    "liquid-ooze",      # drain moves damage instead of heal
    "suction-cups",     # resists forced switching
    "arena-trap",       # traps non-Flying/Levitate foes
    "truant",           # can only act every other turn
    "magic-bounce",     # reflects status moves
    "harvest",          # registered (pinch berries not yet implemented)
})

# Held items with battle behavior in this module / deal_damage.
IMPLEMENTED_HELD = frozenset({
    "choice-band", "choice-specs", "choice-scarf", "leftovers",
    "oran-berry", "sitrus-berry", "lum-berry", "life-orb", "focus-sash",
    "scope-lens", "razor-claw",
    # Phase B items
    "rocky-helmet", "assault-vest", "eviolite", "flame-orb", "toxic-orb",
    "expert-belt", "charcoal", "fire-gem",
    "chesto-berry", "pecha-berry", "rawst-berry", "aspear-berry", "persim-berry",
    # Type boost plates / items (all keys in TYPE_BOOST_ITEMS)
    "draco-plate", "dread-plate", "earth-plate", "fist-plate", "flame-plate",
    "icicle-plate", "insect-plate", "iron-plate", "meadow-plate", "mind-plate",
    "pixie-plate", "sky-plate", "splash-plate", "spooky-plate", "stone-plate",
    "toxic-plate", "zap-plate", "mystic-water", "magnet", "miracle-seed",
    "never-melt-ice", "hard-stone", "silk-scarf", "twisted-spoon", "black-belt",
    "sharp-beak", "poison-barb", "soft-sand", "spell-tag", "metal-coat",
    "black-glasses", "silver-powder", "dragon-fang",
    # All gems
    "water-gem", "electric-gem", "grass-gem", "ice-gem", "fighting-gem",
    "poison-gem", "ground-gem", "flying-gem", "psychic-gem", "bug-gem",
    "rock-gem", "ghost-gem", "dragon-gem", "dark-gem", "steel-gem",
    "normal-gem",
})


# Mold Breaker: set of id()s whose ability is suppressed for the current move
_mb_targets: set = set()


def abil(bp) -> str:
    v = getattr(bp, "vol", None)
    if v is not None:
        if v.ability_suppressed or id(bp) in _mb_targets:
            return ""
        if v.ability_override:
            return v.ability_override
    return (bp.state.ability or "").lower()


def mb_suppress(target) -> None:
    _mb_targets.add(id(target))


def mb_clear(target) -> None:
    _mb_targets.discard(id(target))


def held(bp) -> str:
    v = getattr(bp, "vol", None)
    if v is not None and v.embargo_turns > 0:
        return ""
    if abil(bp) == "klutz":
        return ""
    return bp.state.held_item or ""


def suppress_weather(eng) -> bool:
    """True if Cloud Nine or Air Lock suppresses weather effects."""
    for side in ("p1", "p2"):
        try:
            if abil(eng.active(side)) in ("cloud-nine", "air-lock"):
                return True
        except Exception:
            pass
    return False


def powder_immune(bp) -> bool:
    """True if the Pokemon is immune to powder / spore moves."""
    return abil(bp) == "overcoat"


def soundproof_immune(bp) -> bool:
    """True if the Pokemon is immune to sound-based moves."""
    return abil(bp) == "soundproof"


def liquid_ooze_reverses(defender) -> bool:
    """True if drain moves deal damage to the drainer instead of healing."""
    return abil(defender) == "liquid-ooze"


def on_item_consumed(bp, item_id: str | None = None) -> None:
    """Call after any held item is consumed. Records item for Recycle, activates Unburden."""
    if item_id:
        bp.vol.last_used_item = item_id
    if abil(bp) == "unburden":
        bp.vol.unburden_active = True


# ── damage-formula hooks ─────────────────────────────────────────────

def attack_stat_mod(attacker, move) -> float:
    m, a = 1.0, abil(attacker)
    if move.category == "physical":
        if a in ("huge-power", "pure-power"):
            m *= 2.0
        if a == "guts" and attacker.status:
            m *= 1.5
        if held(attacker) == "choice-band":
            m *= 1.5
        if a == "hustle":
            m *= 1.5
    else:
        if held(attacker) == "choice-specs":
            m *= 1.5
        if a == "solar-power" and getattr(attacker, "_weather_ref", None) == "sun":
            m *= 1.5
    return m


def power_mod(attacker, defender, move, weather) -> float:
    m, a = 1.0, abil(attacker)
    if a == "technician" and (move.power or 0) <= 60:
        m *= 1.5
    if a in PINCH_ABILITIES and move.type == PINCH_ABILITIES[a] \
            and attacker.current_hp * 3 <= attacker.max_hp:
        m *= 1.5
    if abil(defender) == "thick-fat" and move.type in ("fire", "ice"):
        m *= 0.5
    if weather == "sun":
        if move.type == "fire":
            m *= 1.5
        elif move.type == "water":
            m *= 0.5
    elif weather == "rain":
        if move.type == "water":
            m *= 1.5
        elif move.type == "fire":
            m *= 0.5
    if move.id == "solar-beam" and weather in ("rain", "sandstorm", "hail"):
        m *= 0.5

    # Flash Fire: fire power x1.5 when active
    if a == "flash-fire" and move.type == "fire" and attacker.vol.flash_fire_active:
        m *= 1.5

    # Iron Fist: punch moves x1.2
    if a == "iron-fist" and "punch" in move.flags:
        m *= 1.2

    # Reckless: recoil moves x1.2
    if a == "reckless" and move.effect.drain < 0:
        m *= 1.2

    # Sand Force: Rock/Ground/Steel in sandstorm x1.3
    if a == "sand-force" and weather == "sandstorm" \
            and move.type in ("rock", "ground", "steel"):
        m *= 1.3

    # Analytic: +30% power when moving last (flag set by engine)
    if a == "analytic" and getattr(attacker.vol, "analytic_active", False):
        m *= 1.3

    # Sheer Force: secondary effect moves x1.3 (secondaries are skipped in execute_move)
    if a == "sheer-force" and _has_secondary(move):
        m *= 1.3

    # Type boost items x1.2
    item = held(attacker)
    boost_type = TYPE_BOOST_ITEMS.get(item)
    if boost_type and move.type == boost_type:
        m *= 1.2

    # Type gems x1.5 then consume
    gem_type = TYPE_GEMS.get(item)
    if gem_type and move.type == gem_type:
        m *= 1.5
        attacker.state.held_item = None
        on_item_consumed(attacker, item)

    return m


def _has_secondary(move) -> bool:
    """True if a move has secondary effects that Sheer Force would remove."""
    eff = move.effect
    return (eff.ailment_chance > 0 or eff.flinch_chance > 0
            or (eff.stat_chance > 0 and eff.stat_chance < 100))


def def_mod(defender, move) -> float:
    """Multiplier on physical Defense stat."""
    m = 1.0
    a = abil(defender)
    if a == "marvel-scale" and defender.status:
        m *= 1.5
    if held(defender) == "eviolite" and defender.species.evolves_to:
        m *= 1.5
    return m


def spdef_mod(defender, move, weather) -> float:
    m = 1.0
    if weather == "sandstorm" and move.category == "special" \
            and "rock" in defender.types:
        m *= 1.5
    if held(defender) == "assault-vest" and move.category == "special":
        m *= 1.5
    if held(defender) == "eviolite" and defender.species.evolves_to:
        m *= 1.5
    return m


def defender_damage_mod(defender, eff: float) -> float:
    """Multiplier applied after effectiveness in calc_damage."""
    m = 1.0
    a = abil(defender)
    if eff > 1.0:
        if a in ("filter", "solid-rock"):
            m *= 0.75
        if held(defender) == "expert-belt":
            pass  # expert-belt is an attacker bonus; handled in attacker side
    if a in ("multiscale", "shadow-shield") \
            and defender.current_hp == defender.max_hp:
        m *= 0.5
    return m


def attacker_eff_bonus(attacker, eff: float) -> float:
    """Attacker-side multiplier based on effectiveness (expert-belt)."""
    m = 1.0
    if eff > 1.0 and held(attacker) == "expert-belt":
        m *= 1.2
    return m


def final_mod(attacker, crit: bool, screened: bool) -> float:
    m = 1.0
    if screened and not crit:
        m *= 0.5
    if held(attacker) == "life-orb":
        m *= 1.3
    return m


def burn_ignored(attacker) -> bool:
    return abil(attacker) == "guts"


def speed_mod(bp, weather) -> float:
    m = 1.0
    if held(bp) == "choice-scarf":
        m *= 1.5
    if weather and WEATHER_SPEED.get(abil(bp)) == weather:
        m *= 2.0
    if getattr(bp.vol, "unburden_active", False):
        m *= 2.0
    if abil(bp) == "quick-feet" and bp.status:
        m *= 1.5
    return m


def crit_bonus(bp) -> int:
    b = bp.vol.crit_bonus
    if abil(bp) == "super-luck":
        b += 1
    if held(bp) in ("scope-lens", "razor-claw"):
        b += 1
    return b


# ── STAB modifier ────────────────────────────────────────────────────

def stab_mod(attacker, move) -> float:
    """Returns the STAB multiplier (1.5 normally, 2.0 with Adaptability)."""
    if move.type not in attacker.types:
        return 1.0
    if abil(attacker) == "adaptability":
        return 2.0
    return 1.5


# ── status / immunity hooks ──────────────────────────────────────────

def status_blocked(bp, status: str) -> bool:
    base = "poison" if status == "toxic" else status
    return STATUS_BLOCK.get(abil(bp)) == base


def confusion_blocked(bp) -> bool:
    return abil(bp) == "own-tempo"


def immunity_or_absorb(defender, move):
    """'immune' | 'absorb' | None, for ability-based type interactions."""
    a = abil(defender)
    if a == "levitate" and move.type == "ground":
        return "immune"
    if getattr(defender.vol, "magnet_rise_turns", 0) > 0 and move.type == "ground":
        return "immune"
    if a == "volt-absorb" and move.type == "electric":
        return "absorb"
    if a == "water-absorb" and move.type == "water":
        return "absorb"
    # Flash Fire: immune to fire
    if a == "flash-fire" and move.type == "fire":
        return "flash-fire"
    # Absorb-and-raise family type immunities
    if a in ABSORB_RAISE:
        immune_type, stat, amt = ABSORB_RAISE[a]
        if move.type == immune_type:
            return "absorb-raise"
    # Storm Drain: water immune + SpAtk raise
    if a == "storm-drain" and move.type == "water":
        return "absorb-raise"
    # Dry Skin: water heals 25%
    if a == "dry-skin" and move.type == "water":
        return "absorb"
    return None


def secondary_mult(attacker, defender_is_target: bool, defender) -> float:
    """Multiplier on secondary-effect chances (Serene Grace doubles;
    Shield Dust on the target blocks; Sheer Force removes secondaries)."""
    if abil(attacker) == "sheer-force":
        return 0.0
    if defender_is_target and abil(defender) == "shield-dust":
        return 0.0
    return 2.0 if abil(attacker) == "serene-grace" else 1.0


def survives_lethal(bp):
    """('ability'|'item', name) if a full-HP survival effect applies."""
    if bp.current_hp == bp.max_hp:
        if abil(bp) == "sturdy":
            return ("ability", "sturdy")
        if held(bp) == "focus-sash":
            return ("item", "focus-sash")
    return None


def sand_immune(bp) -> bool:
    return (any(t in ("rock", "ground", "steel") for t in bp.types)
            or abil(bp) in SAND_IMMUNE_ABILITIES
            or abil(bp) == "magic-guard")


def magic_guard(bp) -> bool:
    """True if bp is immune to all indirect damage."""
    return abil(bp) == "magic-guard"


# ── event-driven hooks ───────────────────────────────────────────────

def on_contact(eng, attacker, defender, events) -> None:
    """Defender's contact abilities/items punish the attacker."""
    a = abil(defender)
    if a in ("rough-skin", "iron-barbs") and not attacker.fainted:
        dmg = max(1, attacker.max_hp // 8)
        attacker.take_damage(dmg)
        events.append(Event(E.ABILITY, eng.side_of(defender),
                            {"ability": a, "pokemon": defender.name}))
        events.append(Event(E.DAMAGE, eng.side_of(attacker),
                            {"pokemon": attacker.name, "amount": dmg,
                             "remaining_hp": attacker.current_hp,
                             "max_hp": attacker.max_hp,
                             "crit": False, "effectiveness": 1.0}))
        eng.announce_faint(attacker, events)
    # Rocky Helmet: attacker takes 1/6 max HP
    if held(defender) == "rocky-helmet" and not attacker.fainted:
        dmg = max(1, attacker.max_hp // 6)
        attacker.take_damage(dmg)
        events.append(Event(E.ITEM_HELD, eng.side_of(defender),
                            {"item": "rocky-helmet", "pokemon": defender.name}))
        events.append(Event(E.DAMAGE, eng.side_of(attacker),
                            {"pokemon": attacker.name, "amount": dmg,
                             "remaining_hp": attacker.current_hp,
                             "max_hp": attacker.max_hp,
                             "crit": False, "effectiveness": 1.0}))
        eng.announce_faint(attacker, events)
    if a in CONTACT_STATUS and not attacker.fainted \
            and eng.rng.randint(1, 100) <= 30:
        from .moves import apply_status
        if apply_status(eng, attacker, CONTACT_STATUS[a], events):
            events.insert(-1, Event(E.ABILITY, eng.side_of(defender),
                                    {"ability": a, "pokemon": defender.name}))
    # Effect Spore: 30% total chance of random status (11%/10%/9%)
    if a == "effect-spore" and not attacker.fainted:
        roll = eng.rng.randint(1, 100)
        if roll <= 11:
            from .moves import apply_status
            if apply_status(eng, attacker, "sleep", events):
                events.insert(-1, Event(E.ABILITY, eng.side_of(defender),
                                        {"ability": "effect-spore", "pokemon": defender.name}))
        elif roll <= 21:
            from .moves import apply_status
            if apply_status(eng, attacker, "paralysis", events):
                events.insert(-1, Event(E.ABILITY, eng.side_of(defender),
                                        {"ability": "effect-spore", "pokemon": defender.name}))
        elif roll <= 30:
            from .moves import apply_status
            if apply_status(eng, attacker, "poison", events):
                events.insert(-1, Event(E.ABILITY, eng.side_of(defender),
                                        {"ability": "effect-spore", "pokemon": defender.name}))
    # Mummy: attacker's ability becomes "mummy"
    if a == "mummy" and not attacker.fainted:
        if abil(attacker) != "mummy":
            attacker.vol.ability_override = "mummy"
            events.append(Event(E.ABILITY, eng.side_of(defender),
                                {"ability": "mummy", "pokemon": defender.name}))
            events.append(Event(E.ABILITY, eng.side_of(attacker),
                                {"ability": "mummy", "pokemon": attacker.name,
                                 "overridden": True}))
    # Stench: 10% chance to flinch the attacker (if they haven't moved yet)
    if a == "stench" and not attacker.fainted and not attacker.vol.has_moved:
        if eng.rng.randint(1, 100) <= 10:
            if abil(attacker) != "inner-focus":
                attacker.vol.flinched = True
                events.append(Event(E.ABILITY, eng.side_of(defender),
                                    {"ability": "stench", "pokemon": defender.name}))
    # Cute Charm: 30% chance to infatuate the attacker
    if a == "cute-charm" and not attacker.fainted \
            and not attacker.vol.infatuated and abil(attacker) != "oblivious":
        if eng.rng.randint(1, 100) <= 30:
            attacker.vol.infatuated = True
            events.append(Event(E.ABILITY, eng.side_of(defender),
                                {"ability": "cute-charm", "pokemon": defender.name}))
            events.append(Event(E.CONFUSED, eng.side_of(attacker),
                                {"pokemon": attacker.name, "start": True,
                                 "infatuated": True}))
    # Aftermath: if the defender fainted from this contact hit, deal 25% to attacker
    if a == "aftermath" and defender.fainted and not attacker.fainted:
        dmg = max(1, attacker.max_hp // 4)
        attacker.take_damage(dmg)
        events.append(Event(E.ABILITY, eng.side_of(defender),
                            {"ability": "aftermath", "pokemon": defender.name}))
        events.append(Event(E.DAMAGE, eng.side_of(attacker),
                            {"pokemon": attacker.name, "amount": dmg,
                             "remaining_hp": attacker.current_hp,
                             "max_hp": attacker.max_hp,
                             "crit": False, "effectiveness": 1.0}))
        eng.announce_faint(attacker, events)
    # Poison Touch: 30% chance to poison the attacker
    if a == "poison-touch" and not attacker.fainted and not attacker.status:
        if eng.rng.randint(1, 100) <= 30:
            from .moves import apply_status
            if apply_status(eng, attacker, "poison", events):
                events.insert(-1, Event(E.ABILITY, eng.side_of(defender),
                                        {"ability": "poison-touch", "pokemon": defender.name}))
    # Pickpocket: steal attacker's item if defender has no item
    if a == "pickpocket" and not attacker.fainted \
            and not defender.state.held_item and attacker.state.held_item:
        if abil(attacker) != "sticky-hold":
            stolen = attacker.state.held_item
            attacker.state.held_item = None
            defender.state.held_item = stolen
            events.append(Event(E.ABILITY, eng.side_of(defender),
                                {"ability": "pickpocket", "pokemon": defender.name,
                                 "stolen_item": stolen}))
    # Cursed Body: 30% chance to disable the move the attacker just used
    if a == "cursed-body" and not attacker.fainted and attacker.vol.last_move:
        if eng.rng.randint(1, 100) <= 30:
            move_id = attacker.vol.last_move
            slot = attacker.state.move_slot(move_id)
            if slot is not None and slot.pp > 0:
                attacker.vol.choice_lock = move_id  # reuse choice_lock as disable
                events.append(Event(E.ABILITY, eng.side_of(defender),
                                    {"ability": "cursed-body", "pokemon": defender.name,
                                     "disabled_move": move_id}))


def switch_in(eng, side: str, bp, events) -> None:
    a = abil(bp)
    foe_side = "p2" if side == "p1" else "p1"
    if a == "intimidate":
        foe = eng.active(foe_side)
        if not foe.fainted:
            events.append(Event(E.ABILITY, side,
                                {"ability": "intimidate", "pokemon": bp.name}))
            applied = foe.modify_stage("attack", -1)
            if applied:
                events.append(Event(E.STAT_CHANGE, eng.side_of(foe),
                                    {"pokemon": foe.name, "stat": "attack",
                                     "change": applied,
                                     "stage": foe.stages["attack"]}))
            else:
                events.append(Event(E.STAT_CHANGE_FAILED, eng.side_of(foe),
                                    {"pokemon": foe.name, "stat": "attack",
                                     "direction": "lower"}))
    w = WEATHER_SETTERS.get(a)
    if w and eng.weather != w:
        events.append(Event(E.ABILITY, side, {"ability": a, "pokemon": bp.name}))
        eng.set_weather(w, -1, events)
    # Download: raises Atk if foe Def < SpDef, else SpAtk
    if a == "download":
        foe = eng.active(foe_side)
        if not foe.fainted:
            events.append(Event(E.ABILITY, side,
                                {"ability": "download", "pokemon": bp.name}))
            if foe.stats["defense"] < foe.stats["special_defense"]:
                stat = "attack"
            else:
                stat = "special_attack"
            applied = bp.modify_stage(stat, 1)
            if applied:
                events.append(Event(E.STAT_CHANGE, side,
                                    {"pokemon": bp.name, "stat": stat,
                                     "change": applied,
                                     "stage": bp.stages[stat]}))
    # Trace: copy foe's ability
    if a == "trace":
        foe = eng.active(foe_side)
        if not foe.fainted:
            foe_abil = abil(foe)
            if foe_abil and foe_abil != "trace":
                bp.vol.ability_override = foe_abil
                events.append(Event(E.ABILITY, side,
                                    {"ability": "trace", "pokemon": bp.name,
                                     "traced": foe_abil}))
    # Frisk: reveal foe's held item
    if a == "frisk":
        foe = eng.active(foe_side)
        if not foe.fainted and foe.state.held_item:
            events.append(Event(E.ABILITY, side,
                                {"ability": "frisk", "pokemon": bp.name,
                                 "revealed_item": foe.state.held_item,
                                 "revealed_for": foe.name}))
    # Forewarn: reveal foe's highest-power move
    if a == "forewarn":
        foe = eng.active(foe_side)
        if not foe.fainted:
            best_move = None
            best_power = -1
            for slot in foe.state.moves:
                try:
                    mv = eng.data.move(slot.move_id)
                    p = mv.power or 0
                    if p > best_power:
                        best_power = p
                        best_move = mv.name
                except Exception:
                    pass
            if best_move:
                events.append(Event(E.ABILITY, side,
                                    {"ability": "forewarn", "pokemon": bp.name,
                                     "warned_move": best_move,
                                     "warned_from": foe.name}))
    # Anticipation: warn if foe has SE or OHKO moves
    if a == "anticipation":
        foe = eng.active(foe_side)
        if not foe.fainted:
            found_threat = False
            for slot in foe.state.moves:
                try:
                    mv = eng.data.move(slot.move_id)
                    if mv.effect.kind == "ohko":
                        found_threat = True
                        break
                    eff = eng.data.effectiveness(mv.type, bp.types)
                    if eff > 1.0 and mv.is_damaging:
                        found_threat = True
                        break
                except Exception:
                    pass
            if found_threat:
                events.append(Event(E.ABILITY, side,
                                    {"ability": "anticipation", "pokemon": bp.name}))
    # Unnerve: announce that foe cannot eat berries
    if a == "unnerve":
        foe = eng.active(foe_side)
        if not foe.fainted:
            events.append(Event(E.ABILITY, side,
                                {"ability": "unnerve", "pokemon": bp.name}))


def on_switch_out(bp, events, side) -> None:
    if abil(bp) == "natural-cure" and bp.status:
        cured = bp.status
        bp.status = None
        events.append(Event(E.STATUS_CURED, side,
                            {"pokemon": bp.name, "status": cured,
                             "ability": "natural-cure"}))
    if abil(bp) == "regenerator" and not bp.fainted:
        healed = bp.heal(max(1, bp.max_hp // 3))
        if healed:
            events.append(Event(E.ABILITY, side,
                                {"ability": "regenerator", "pokemon": bp.name}))
            events.append(Event(E.HEAL, side,
                                {"pokemon": bp.name, "amount": healed,
                                 "remaining_hp": bp.current_hp}))


def _unnerved(eng, bp) -> bool:
    """True if a foe with Unnerve is on the field, suppressing berry use."""
    for side in ("p1", "p2"):
        try:
            foe = eng.active(side)
            if foe is not bp and not foe.fainted and abil(foe) == "unnerve":
                return True
        except Exception:
            pass
    return False


def check_hp_berry(eng, bp, events) -> None:
    if _unnerved(eng, bp):
        return
    it = held(bp)
    if bp.fainted or it not in ("oran-berry", "sitrus-berry"):
        return
    if bp.current_hp * 2 <= bp.max_hp:
        bp.state.held_item = None
        on_item_consumed(bp, it)
        amount = 10 if it == "oran-berry" else max(1, bp.max_hp // 4)
        healed = bp.heal(amount)
        events.append(Event(E.ITEM_HELD, eng.side_of(bp),
                            {"item": it, "pokemon": bp.name}))
        events.append(Event(E.HEAL, eng.side_of(bp),
                            {"pokemon": bp.name, "amount": healed,
                             "remaining_hp": bp.current_hp}))


def check_lum(eng, bp, events) -> None:
    if held(bp) != "lum-berry" or bp.fainted:
        return
    if bp.status or bp.vol.confusion_turns > 0:
        cured = bp.status or "confusion"
        bp.status = None
        bp.vol.confusion_turns = 0
        bp.vol.toxic_counter = 0
        bp.state.held_item = None
        on_item_consumed(bp, "lum-berry")
        events.append(Event(E.ITEM_HELD, eng.side_of(bp),
                            {"item": "lum-berry", "pokemon": bp.name}))
        events.append(Event(E.STATUS_CURED, eng.side_of(bp),
                            {"pokemon": bp.name, "status": cured}))


# Status berries: cure specific status on infliction
STATUS_BERRIES = {
    "chesto-berry": "sleep",
    "pecha-berry": "poison",
    "rawst-berry": "burn",
    "aspear-berry": "freeze",
}


def check_status_berry(eng, bp, events) -> None:
    """Called after a non-volatile status is applied or confusion set.
    Cures specific status berries."""
    if bp.fainted or _unnerved(eng, bp):
        return
    it = held(bp)
    # Non-volatile status berries
    cures = STATUS_BERRIES.get(it)
    if cures and bp.status == cures:
        bp.status = None
        if cures == "toxic":
            bp.vol.toxic_counter = 0
        bp.state.held_item = None
        on_item_consumed(bp, it)
        events.append(Event(E.ITEM_HELD, eng.side_of(bp),
                            {"item": it, "pokemon": bp.name}))
        events.append(Event(E.STATUS_CURED, eng.side_of(bp),
                            {"pokemon": bp.name, "status": cures}))
        return
    # Persim Berry: cure confusion
    if it == "persim-berry" and bp.vol.confusion_turns > 0:
        bp.vol.confusion_turns = 0
        bp.state.held_item = None
        on_item_consumed(bp, "persim-berry")
        events.append(Event(E.ITEM_HELD, eng.side_of(bp),
                            {"item": "persim-berry", "pokemon": bp.name}))
        events.append(Event(E.STATUS_CURED, eng.side_of(bp),
                            {"pokemon": bp.name, "status": "confusion"}))


def end_of_turn(eng, side: str, bp, events) -> None:
    if bp.fainted:
        return
    if held(bp) == "leftovers" and bp.current_hp < bp.max_hp:
        if not magic_guard(bp):
            healed = bp.heal(max(1, bp.max_hp // 16))
            events.append(Event(E.ITEM_HELD, side, {"item": "leftovers",
                                                    "pokemon": bp.name}))
            events.append(Event(E.HEAL, side, {"pokemon": bp.name, "amount": healed,
                                               "remaining_hp": bp.current_hp}))
        else:
            # Magic Guard doesn't block leftovers healing (it only blocks damage)
            healed = bp.heal(max(1, bp.max_hp // 16))
            events.append(Event(E.ITEM_HELD, side, {"item": "leftovers",
                                                    "pokemon": bp.name}))
            events.append(Event(E.HEAL, side, {"pokemon": bp.name, "amount": healed,
                                               "remaining_hp": bp.current_hp}))
    check_hp_berry(eng, bp, events)
    a = abil(bp)
    if a == "speed-boost":
        applied = bp.modify_stage("speed", 1)
        if applied:
            events.append(Event(E.ABILITY, side, {"ability": "speed-boost",
                                                  "pokemon": bp.name}))
            events.append(Event(E.STAT_CHANGE, side,
                                {"pokemon": bp.name, "stat": "speed",
                                 "change": applied,
                                 "stage": bp.stages["speed"]}))
    # Ice Body: heal 1/16 in hail
    if a == "ice-body" and eng.weather == "hail":
        healed = bp.heal(max(1, bp.max_hp // 16))
        if healed:
            events.append(Event(E.ABILITY, side, {"ability": "ice-body",
                                                  "pokemon": bp.name}))
            events.append(Event(E.HEAL, side, {"pokemon": bp.name, "amount": healed,
                                               "remaining_hp": bp.current_hp}))
    # Rain Dish: heal 1/16 in rain
    if a == "rain-dish" and eng.weather == "rain":
        healed = bp.heal(max(1, bp.max_hp // 16))
        if healed:
            events.append(Event(E.ABILITY, side, {"ability": "rain-dish",
                                                  "pokemon": bp.name}))
            events.append(Event(E.HEAL, side, {"pokemon": bp.name, "amount": healed,
                                               "remaining_hp": bp.current_hp}))
    # Solar Power: take 1/8 chip in sun
    if a == "solar-power" and eng.weather == "sun" and not magic_guard(bp):
        dmg = max(1, bp.max_hp // 8)
        bp.take_damage(dmg)
        events.append(Event(E.ABILITY, side, {"ability": "solar-power",
                                              "pokemon": bp.name}))
        events.append(Event(E.WEATHER_DAMAGE, side,
                            {"weather": "sun", "pokemon": bp.name,
                             "amount": dmg, "remaining_hp": bp.current_hp}))
        eng.announce_faint(bp, events)
    # Dry Skin: heal 1/8 in rain, take 1/8 chip in sun
    if a == "dry-skin":
        if eng.weather == "rain":
            healed = bp.heal(max(1, bp.max_hp // 8))
            if healed:
                events.append(Event(E.ABILITY, side, {"ability": "dry-skin",
                                                      "pokemon": bp.name}))
                events.append(Event(E.HEAL, side, {"pokemon": bp.name,
                                                   "amount": healed,
                                                   "remaining_hp": bp.current_hp}))
        elif eng.weather == "sun" and not magic_guard(bp):
            dmg = max(1, bp.max_hp // 8)
            bp.take_damage(dmg)
            events.append(Event(E.ABILITY, side, {"ability": "dry-skin",
                                                  "pokemon": bp.name}))
            events.append(Event(E.WEATHER_DAMAGE, side,
                                {"weather": "sun", "pokemon": bp.name,
                                 "amount": dmg, "remaining_hp": bp.current_hp}))
            eng.announce_faint(bp, events)
    # Shed Skin: 33% chance to cure status each turn
    if a == "shed-skin" and bp.status and not bp.fainted:
        if eng.rng.randint(1, 3) == 1:
            cured = bp.status
            bp.status = None
            bp.vol.toxic_counter = 0
            events.append(Event(E.ABILITY, side, {"ability": "shed-skin",
                                                  "pokemon": bp.name}))
            events.append(Event(E.STATUS_CURED, side,
                                {"pokemon": bp.name, "status": cured,
                                 "ability": "shed-skin"}))
    # Hydration: cure status in rain each turn
    if a == "hydration" and bp.status and eng.weather == "rain" and not bp.fainted:
        cured = bp.status
        bp.status = None
        bp.vol.toxic_counter = 0
        events.append(Event(E.ABILITY, side, {"ability": "hydration",
                                              "pokemon": bp.name}))
        events.append(Event(E.STATUS_CURED, side,
                            {"pokemon": bp.name, "status": cured,
                             "ability": "hydration"}))
    # Moody: +2 one random stat, -1 another random stat each turn
    if a == "moody" and not bp.fainted:
        from ..data.models import STAGE_KEYS
        raise_stat = eng.rng.choice(STAGE_KEYS)
        lower_pool = [s for s in STAGE_KEYS if s != raise_stat]
        lower_stat = eng.rng.choice(lower_pool)
        events.append(Event(E.ABILITY, side, {"ability": "moody",
                                              "pokemon": bp.name}))
        for stat, change in ((raise_stat, 2), (lower_stat, -1)):
            applied = bp.modify_stage(stat, change)
            if applied:
                events.append(Event(E.STAT_CHANGE, side,
                                    {"pokemon": bp.name, "stat": stat,
                                     "change": applied,
                                     "stage": bp.stages[stat]}))
    # Flame Orb: apply burn at end of turn if no status
    if held(bp) == "flame-orb" and not bp.status and not bp.fainted:
        from .moves import apply_status
        apply_status(eng, bp, "burn", events)
    # Toxic Orb: apply toxic at end of turn if no status
    if held(bp) == "toxic-orb" and not bp.status and not bp.fainted:
        from .moves import apply_status
        apply_status(eng, bp, "toxic", events)
    # Yawn counter
    if bp.vol.yawn_turns > 0 and not bp.fainted:
        bp.vol.yawn_turns -= 1
        if bp.vol.yawn_turns == 0:
            from .moves import apply_status
            apply_status(eng, bp, "sleep", events)
    # Magnet Rise countdown
    if bp.vol.magnet_rise_turns > 0:
        bp.vol.magnet_rise_turns -= 1
    # Perish Song countdown
    if bp.vol.perish_count > 0 and not bp.fainted:
        bp.vol.perish_count -= 1
        events.append(Event(E.ABILITY, side, {"ability": "perish-song",
                                              "pokemon": bp.name,
                                              "count": bp.vol.perish_count}))
        if bp.vol.perish_count == 0:
            bp.take_damage(bp.current_hp)
            eng.announce_faint(bp, events)
    # Nightmare damage: sleeping + nightmare -> 1/4 HP damage
    if bp.status == "sleep" and bp.vol.nightmare and not bp.fainted:
        if not magic_guard(bp):
            dmg = max(1, bp.max_hp // 4)
            bp.take_damage(dmg)
            events.append(Event(E.STATUS_DAMAGE, side,
                                {"pokemon": bp.name, "status": "nightmare",
                                 "amount": dmg, "remaining_hp": bp.current_hp}))
            eng.announce_faint(bp, events)


def on_absorb_raise(eng, side: str, defender, move, events) -> None:
    """Handle absorb-and-raise abilities (motor-drive, lightning-rod, sap-sipper,
    storm-drain). Called from execute_move when immunity_or_absorb returns 'absorb-raise'."""
    a = abil(defender)
    events.append(Event(E.ABILITY, side,
                        {"ability": a, "pokemon": defender.name}))
    stat_to_raise = None
    if a in ABSORB_RAISE:
        _, stat_to_raise, amt = ABSORB_RAISE[a]
    elif a == "storm-drain":
        stat_to_raise, amt = "special_attack", 1
    if stat_to_raise:
        applied = defender.modify_stage(stat_to_raise, amt)
        if applied:
            events.append(Event(E.STAT_CHANGE, side,
                                {"pokemon": defender.name, "stat": stat_to_raise,
                                 "change": applied,
                                 "stage": defender.stages[stat_to_raise]}))


def on_flash_fire(eng, side: str, defender, move, events) -> None:
    """Handle Flash Fire: immune to fire, activates boost."""
    defender.vol.flash_fire_active = True
    events.append(Event(E.ABILITY, side,
                        {"ability": "flash-fire", "pokemon": defender.name}))
    events.append(Event(E.MOVE_IMMUNE, side, {"pokemon": defender.name}))


def on_dry_skin_fire(eng, defender, total_dmg: int, events) -> None:
    """Dry Skin takes extra 25% damage on fire hit (applied after damage)."""
    if abil(defender) == "dry-skin" and not magic_guard(defender):
        side = eng.side_of(defender)
        extra = max(1, defender.max_hp // 4)
        defender.take_damage(extra)
        events.append(Event(E.ABILITY, side,
                            {"ability": "dry-skin", "pokemon": defender.name}))
        events.append(Event(E.DAMAGE, side,
                            {"pokemon": defender.name, "amount": extra,
                             "remaining_hp": defender.current_hp,
                             "max_hp": defender.max_hp,
                             "crit": False, "effectiveness": 1.0}))
        eng.announce_faint(defender, events)


def on_defiant_competitive(eng, holder, stat: str, change: int,
                           from_foe: bool, events) -> None:
    """Defiant/Competitive: when holder's stat is lowered by foe -> +2 Atk/SpAtk."""
    if not from_foe or change >= 0:
        return
    a = abil(holder)
    if a == "defiant":
        raise_stat = "attack"
    elif a == "competitive":
        raise_stat = "special_attack"
    else:
        return
    applied = holder.modify_stage(raise_stat, 2)
    if applied:
        side = eng.side_of(holder)
        events.append(Event(E.ABILITY, side,
                            {"ability": a, "pokemon": holder.name}))
        events.append(Event(E.STAT_CHANGE, side,
                            {"pokemon": holder.name, "stat": raise_stat,
                             "change": applied,
                             "stage": holder.stages[raise_stat]}))
