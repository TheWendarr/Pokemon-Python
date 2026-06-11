"""Phase 2 mechanics: abilities, held items, weather, hazards, screens,
Protect, two-turn/rampage moves, traps, Leech Seed, forced switching."""
import pytest

from pkmn.battle.damage import calc_damage
from pkmn.battle.engine import BattleEngine
from pkmn.battle.events import E
from pkmn.battle.state import MoveAction, P1, P2, SwitchAction


def first(events, etype, side=None):
    for e in events:
        if e.type == etype and (side is None or e.side == side):
            return e
    return None


def all_of(events, etype, side=None):
    return [e for e in events if e.type == etype and (side is None or e.side == side)]


# ── weather ──────────────────────────────────────────────────────────

def test_sun_boosts_fire_weakens_water(data, make_mon, maxroll):
    eng = BattleEngine(data, [make_mon("charmander")], [make_mon("bulbasaur")],
                       rng=maxroll)
    atk, dfn = eng.active(P1), eng.active(P2)
    ember = data.move("ember")
    plain, _ = calc_damage(data, atk, dfn, ember, rng=maxroll)
    sunny, _ = calc_damage(data, atk, dfn, ember, rng=maxroll, weather="sun")
    assert sunny > plain
    wg = data.move("water-gun")
    eng2 = BattleEngine(data, [make_mon("squirtle")], [make_mon("charmander")],
                        rng=maxroll)
    a2, d2 = eng2.active(P1), eng2.active(P2)
    plain_w, _ = calc_damage(data, a2, d2, wg, rng=maxroll)
    sun_w, _ = calc_damage(data, a2, d2, wg, rng=maxroll, weather="sun")
    assert sun_w < plain_w


def test_sandstorm_chips_and_spares_immune_types(data, make_mon, nochance):
    eng = BattleEngine(data, [make_mon("geodude")], [make_mon("squirtle")],
                       rng=nochance)
    ev = eng.submit_turn(MoveAction("rest"), MoveAction("recover"))
    # geodude knows no sandstorm; set weather via engine API for the test
    eng.set_weather("sandstorm", 5, [])
    ev = eng.submit_turn(MoveAction("rest"), MoveAction("recover"))
    chips = all_of(ev, E.WEATHER_DAMAGE)
    assert len(chips) == 1 and chips[0].side == P2  # rock/ground is immune
    assert chips[0].data["amount"] == eng.active(P2).max_hp // 16


def test_weather_expires_after_five_turns(data, make_mon, nochance):
    eng = BattleEngine(data, [make_mon("pikachu", moves=["rain-dance", "tackle"])],
                       [make_mon("squirtle", level=100)], rng=nochance)
    ev = eng.submit_turn(MoveAction("rain-dance"), MoveAction("recover"))
    assert first(ev, E.WEATHER_START).data["weather"] == "rain"
    ended = None
    for _ in range(5):
        ev = eng.submit_turn(MoveAction("tackle"), MoveAction("recover"))
        ended = first(ev, E.WEATHER_END) or ended
    assert ended is not None
    assert eng.weather is None


def test_blizzard_never_misses_in_hail(data, make_mon, nochance):
    eng = BattleEngine(data,
                       [make_mon("pikachu", moves=["hail", "blizzard"])],
                       [make_mon("squirtle", level=100)], rng=nochance)
    # NoChance fails every accuracy roll: blizzard at 70 must miss normally
    ev = eng.submit_turn(MoveAction("blizzard"), MoveAction("recover"))
    assert first(ev, E.MOVE_MISSED, P1) is not None
    eng.submit_turn(MoveAction("hail"), MoveAction("recover"))
    ev = eng.submit_turn(MoveAction("blizzard"), MoveAction("recover"))
    assert first(ev, E.DAMAGE, P2) is not None


def test_drizzle_sets_permanent_rain(data, make_mon, maxroll):
    p = make_mon("squirtle")
    p.ability = "drizzle"
    eng = BattleEngine(data, [p], [make_mon("pikachu")], rng=maxroll)
    assert eng.weather == "rain"
    assert eng.weather_turns == -1
    for _ in range(6):
        eng.submit_turn(MoveAction("recover"), MoveAction("tackle"))
    assert eng.weather == "rain"


def test_swift_swim_doubles_speed_in_rain(data, make_mon, maxroll):
    p = make_mon("squirtle")
    p.ability = "swift-swim"
    eng = BattleEngine(data, [p], [make_mon("pikachu")], rng=maxroll)
    bp = eng.active(P1)
    assert bp.effective_speed("rain") == bp.effective_speed() * 2


# ── entry hazards ────────────────────────────────────────────────────

def test_stealth_rock_scales_with_rock_weakness(data, make_mon, maxroll):
    eng = BattleEngine(data,
                       [make_mon("geodude", moves=["stealth-rock", "rest"])],
                       [make_mon("squirtle"), make_mon("charmander")],
                       rng=maxroll)
    ev = eng.submit_turn(MoveAction("stealth-rock"), MoveAction("recover"))
    assert first(ev, E.HAZARD_SET, P2).data["hazard"] == "stealth-rock"
    ev = eng.submit_turn(MoveAction("rest"), SwitchAction(1))
    hz = first(ev, E.HAZARD_DAMAGE, P2)
    char = eng.active(P2)
    assert hz.data["amount"] == char.max_hp * 2 // 8  # fire is 2x weak to rock


def test_spikes_hit_grounded_but_not_levitate(data, make_mon, maxroll):
    lev = make_mon("gengar")
    lev.ability = "levitate"
    eng = BattleEngine(data,
                       [make_mon("geodude", moves=["spikes", "rest"])],
                       [make_mon("squirtle"), make_mon("charmander"), lev],
                       rng=maxroll)
    eng.submit_turn(MoveAction("spikes"), MoveAction("recover"))
    ev = eng.submit_turn(MoveAction("rest"), SwitchAction(1))
    assert first(ev, E.HAZARD_DAMAGE, P2).data["amount"] == \
        eng.active(P2).max_hp // 8
    ev = eng.submit_turn(MoveAction("rest"), SwitchAction(2))
    assert first(ev, E.HAZARD_DAMAGE, P2) is None  # levitate floats over


def test_toxic_spikes_layers_and_poison_absorb(data, make_mon, maxroll):
    eng = BattleEngine(data,
                       [make_mon("gengar", moves=["toxic-spikes", "confuse-ray"])],
                       [make_mon("squirtle"), make_mon("charmander"),
                        make_mon("bulbasaur")],
                       rng=maxroll)
    eng.submit_turn(MoveAction("toxic-spikes"), MoveAction("recover"))
    eng.submit_turn(MoveAction("toxic-spikes"), MoveAction("recover"))
    ev = eng.submit_turn(MoveAction("confuse-ray"), SwitchAction(1))
    assert first(ev, E.STATUS_APPLIED, P2).data["status"] == "toxic"  # 2 layers
    ev = eng.submit_turn(MoveAction("confuse-ray"), SwitchAction(2))
    assert first(ev, E.HAZARD_CLEARED, P2).data["hazard"] == "toxic-spikes"
    assert eng.active(P2).status is None
    assert eng.sides[P2].toxic_spikes == 0


def test_rapid_spin_clears_own_hazards(data, make_mon, maxroll):
    eng = BattleEngine(data,
                       [make_mon("geodude", moves=["stealth-rock", "spikes", "rest"])],
                       [make_mon("squirtle", moves=["rapid-spin", "recover"])],
                       rng=maxroll)
    eng.submit_turn(MoveAction("stealth-rock"), MoveAction("recover"))
    eng.submit_turn(MoveAction("spikes"), MoveAction("recover"))
    ev = eng.submit_turn(MoveAction("rest"), MoveAction("rapid-spin"))
    cleared = {e.data["hazard"] for e in all_of(ev, E.HAZARD_CLEARED, P2)}
    assert cleared == {"spikes", "stealth-rock"}
    assert eng.sides[P2].spikes == 0 and not eng.sides[P2].stealth_rock


# ── Protect ──────────────────────────────────────────────────────────

def test_protect_blocks_and_consecutive_use_fails(data, make_mon, maxroll):
    eng = BattleEngine(data,
                       [make_mon("squirtle", moves=["protect", "recover"])],
                       [make_mon("pikachu", moves=["tackle"])], rng=maxroll)
    ev = eng.submit_turn(MoveAction("protect"), MoveAction("tackle"))
    assert first(ev, E.PROTECTED, P1).data["setup"] is True
    assert first(ev, E.DAMAGE, P1) is None
    blocked = [e for e in all_of(ev, E.PROTECTED, P1) if not e.data["setup"]]
    assert blocked
    # MaxRoll random()=1.0 makes the halved second attempt fail
    ev = eng.submit_turn(MoveAction("protect"), MoveAction("tackle"))
    assert first(ev, E.MOVE_FAILED, P1) is not None
    assert first(ev, E.DAMAGE, P1) is not None


# ── two-turn / recharge / rampage ────────────────────────────────────

def test_fly_semi_invulnerable_then_lands(data, make_mon, maxroll):
    eng = BattleEngine(data, [make_mon("pikachu", moves=["fly"])],
                       [make_mon("squirtle", moves=["tackle", "recover"])],
                       rng=maxroll)
    ev = eng.submit_turn(MoveAction("fly"), MoveAction("tackle"))
    assert first(ev, E.CHARGING, P1) is not None
    assert first(ev, E.MOVE_MISSED, P2) is not None  # can't touch it up there
    assert eng.legal_actions(P1) == [MoveAction("fly")]
    ev = eng.submit_turn(MoveAction("fly"), MoveAction("recover"))
    assert first(ev, E.DAMAGE, P2) is not None
    assert eng.active(P1).vol.charging is None


def test_gust_hits_flying_target(data, make_mon, maxroll):
    eng = BattleEngine(data, [make_mon("pikachu", moves=["fly"])],
                       [make_mon("squirtle", moves=["gust"])],
                       rng=maxroll)
    ev = eng.submit_turn(MoveAction("fly"), MoveAction("gust"))
    assert first(ev, E.DAMAGE, P1) is not None  # gust reaches Fly users


def test_solar_beam_skips_charge_in_sun(data, make_mon, maxroll):
    p = make_mon("bulbasaur", moves=["solar-beam"])
    p.ability = "drought"
    eng = BattleEngine(data, [p], [make_mon("squirtle", level=100)], rng=maxroll)
    ev = eng.submit_turn(MoveAction("solar-beam"), MoveAction("recover"))
    assert first(ev, E.CHARGING, P1) is None
    assert first(ev, E.DAMAGE, P2) is not None


def test_hyper_beam_forces_recharge_turn(data, make_mon, maxroll):
    eng = BattleEngine(data, [make_mon("pikachu", moves=["hyper-beam"])],
                       [make_mon("squirtle", level=100)], rng=maxroll)
    ev = eng.submit_turn(MoveAction("hyper-beam"), MoveAction("recover"))
    assert first(ev, E.DAMAGE, P2) is not None
    assert eng.legal_actions(P1) == [MoveAction("recharge")]
    ev = eng.submit_turn(MoveAction("recharge"), MoveAction("recover"))
    assert first(ev, E.RECHARGING, P1) is not None
    assert first(ev, E.MOVE_USED, P1) is None


def test_outrage_locks_then_confuses(data, make_mon, maxroll):
    eng = BattleEngine(data, [make_mon("pikachu", moves=["outrage", "tackle"])],
                       [make_mon("squirtle", level=100)], rng=maxroll)
    eng.submit_turn(MoveAction("outrage"), MoveAction("recover"))
    assert eng.legal_actions(P1) == [MoveAction("outrage")]  # locked in
    ev = eng.submit_turn(MoveAction("outrage"), MoveAction("recover"))
    fatigue = [e for e in all_of(ev, E.CONFUSED, P1) if e.data.get("fatigue")]
    assert fatigue
    assert eng.active(P1).vol.rampage_move is None
    assert eng.active(P1).vol.confusion_turns > 0


# ── held items ───────────────────────────────────────────────────────

def test_leftovers_heals_each_turn(data, make_mon, nochance):
    p = make_mon("squirtle", level=100)
    p.held_item = "leftovers"
    eng = BattleEngine(data, [p], [make_mon("pikachu")], rng=nochance)
    eng.active(P1).take_damage(50)
    hp = eng.active(P1).current_hp
    ev = eng.submit_turn(MoveAction("growl"), MoveAction("thunder-wave"))
    assert first(ev, E.ITEM_HELD, P1).data["item"] == "leftovers"
    assert eng.active(P1).current_hp == hp + eng.active(P1).max_hp // 16


def test_sitrus_berry_triggers_below_half(data, make_mon, maxroll):
    p = make_mon("squirtle")
    p.held_item = "sitrus-berry"
    eng = BattleEngine(data, [make_mon("pikachu")], [p], rng=maxroll)
    ev = eng.submit_turn(MoveAction("thunderbolt"), MoveAction("growl"))
    # 108 damage drops Squirtle below half; berry restores 25% immediately
    tgt = eng.active(P2)
    assert tgt.held_item is None
    assert first(ev, E.ITEM_HELD, P2).data["item"] == "sitrus-berry"
    assert tgt.current_hp == tgt.max_hp - 108 + tgt.max_hp // 4


def test_lum_berry_cures_status_instantly(data, make_mon, maxroll):
    p = make_mon("squirtle")
    p.held_item = "lum-berry"
    eng = BattleEngine(data, [make_mon("pikachu")], [p], rng=maxroll)
    ev = eng.submit_turn(MoveAction("thunder-wave"), MoveAction("recover"))
    assert first(ev, E.STATUS_APPLIED, P2) is not None
    assert first(ev, E.STATUS_CURED, P2) is not None
    assert eng.active(P2).status is None
    assert eng.active(P2).held_item is None


def test_choice_band_boosts_and_locks(data, make_mon, maxroll):
    p = make_mon("pikachu")
    p.held_item = "choice-band"
    eng = BattleEngine(data, [p], [make_mon("squirtle", level=100)], rng=maxroll)
    atk, dfn = eng.active(P1), eng.active(P2)
    tackle = data.move("tackle")
    banded, _ = calc_damage(data, atk, dfn, tackle, rng=maxroll)
    p.held_item = None
    plain, _ = calc_damage(data, atk, dfn, tackle, rng=maxroll)
    assert banded > plain
    p.held_item = "choice-band"
    eng.submit_turn(MoveAction("tackle"), MoveAction("recover"))
    locked = [a for a in eng.legal_actions(P1) if isinstance(a, MoveAction)]
    assert locked == [MoveAction("tackle")]


def test_choice_scarf_speed(data, make_mon, maxroll):
    p = make_mon("squirtle")
    eng = BattleEngine(data, [p], [make_mon("pikachu")], rng=maxroll)
    base = eng.active(P1).effective_speed()
    p.held_item = "choice-scarf"
    assert eng.active(P1).effective_speed() == int(base * 1.5)


def test_life_orb_boost_and_recoil(data, make_mon, maxroll):
    p = make_mon("pikachu")
    eng = BattleEngine(data, [p], [make_mon("squirtle", level=100)], rng=maxroll)
    atk, dfn = eng.active(P1), eng.active(P2)
    tackle = data.move("tackle")
    plain, _ = calc_damage(data, atk, dfn, tackle, rng=maxroll)
    p.held_item = "life-orb"
    boosted, _ = calc_damage(data, atk, dfn, tackle, rng=maxroll)
    assert boosted == int(plain * 1.3)
    ev = eng.submit_turn(MoveAction("tackle"), MoveAction("recover"))
    rec = first(ev, E.RECOIL, P1)
    assert rec.data["amount"] == atk.max_hp // 10


def test_focus_sash_survives_from_full(data, make_mon, maxroll):
    p = make_mon("squirtle", level=5)
    p.held_item = "focus-sash"
    eng = BattleEngine(data, [make_mon("pikachu", level=100)], [p], rng=maxroll)
    ev = eng.submit_turn(MoveAction("thunderbolt"), MoveAction("growl"))
    tgt = eng.active(P2)
    assert tgt.current_hp == 1
    assert tgt.held_item is None
    assert first(ev, E.ITEM_HELD, P2).data.get("endure") is True


# ── abilities ────────────────────────────────────────────────────────

def test_intimidate_on_battle_start(data, make_mon, maxroll):
    p = make_mon("geodude")
    p.ability = "intimidate"
    eng = BattleEngine(data, [p], [make_mon("squirtle")], rng=maxroll)
    assert eng.active(P2).stages["attack"] == -1


def test_levitate_blocks_ground_moves(data, make_mon, maxroll):
    p = make_mon("pikachu")
    p.ability = "levitate"
    eng = BattleEngine(data, [make_mon("geodude")], [p], rng=maxroll)
    ev = eng.submit_turn(MoveAction("earthquake"), MoveAction("tackle"))
    assert first(ev, E.MOVE_IMMUNE, P2) is not None
    assert first(ev, E.DAMAGE, P2) is None


def test_static_paralyzes_on_contact(data, make_mon, maxroll):
    p = make_mon("pikachu")
    p.ability = "static"
    eng = BattleEngine(data, [make_mon("squirtle", level=100)], [p], rng=maxroll)
    ev = eng.submit_turn(MoveAction("tackle"), MoveAction("thunder-wave"))
    assert eng.active(P1).status == "paralysis"
    assert first(ev, E.ABILITY, P2).data["ability"] == "static"


def test_guts_ignores_burn_and_boosts_attack(data, make_mon, maxroll):
    eng = BattleEngine(data, [make_mon("pikachu")],
                       [make_mon("squirtle", level=100)], rng=maxroll)
    atk, dfn = eng.active(P1), eng.active(P2)
    tackle = data.move("tackle")
    plain, _ = calc_damage(data, atk, dfn, tackle, rng=maxroll)
    atk.state.ability = "guts"
    atk.status = "burn"
    gutsy, _ = calc_damage(data, atk, dfn, tackle, rng=maxroll)
    assert gutsy > plain  # 1.5x attack, and no burn halving


def test_sturdy_endures_from_full_hp(data, make_mon, maxroll):
    p = make_mon("geodude", level=5)
    p.ability = "sturdy"
    eng = BattleEngine(data, [make_mon("squirtle", level=100)], [p], rng=maxroll)
    ev = eng.submit_turn(MoveAction("water-gun"), MoveAction("tackle"))
    assert eng.active(P2).current_hp == 1
    assert first(ev, E.ABILITY, P2).data["ability"] == "sturdy"


def test_huge_power_doubles_physical(data, make_mon, maxroll):
    eng = BattleEngine(data, [make_mon("pikachu")],
                       [make_mon("squirtle", level=100)], rng=maxroll)
    atk, dfn = eng.active(P1), eng.active(P2)
    tackle = data.move("tackle")
    plain, _ = calc_damage(data, atk, dfn, tackle, rng=maxroll)
    atk.state.ability = "huge-power"
    huge, _ = calc_damage(data, atk, dfn, tackle, rng=maxroll)
    assert huge > plain * 1.8  # ~2x modulo integer floors


def test_blaze_boosts_fire_in_a_pinch(data, make_mon, maxroll):
    eng = BattleEngine(data, [make_mon("charmander")],
                       [make_mon("squirtle", level=100)], rng=maxroll)
    atk, dfn = eng.active(P1), eng.active(P2)
    ember = data.move("ember")
    plain, _ = calc_damage(data, atk, dfn, ember, rng=maxroll)
    atk.state.ability = "blaze"
    high_hp, _ = calc_damage(data, atk, dfn, ember, rng=maxroll)
    assert high_hp == plain  # not in a pinch yet
    atk.take_damage(atk.max_hp - atk.max_hp // 4)
    pinch, _ = calc_damage(data, atk, dfn, ember, rng=maxroll)
    assert pinch > plain


def test_volt_absorb_heals_instead_of_damaging(data, make_mon, maxroll):
    p = make_mon("squirtle")
    p.ability = "volt-absorb"
    eng = BattleEngine(data, [make_mon("pikachu")], [p], rng=maxroll)
    eng.active(P2).take_damage(40)
    ev = eng.submit_turn(MoveAction("thunderbolt"), MoveAction("recover"))
    assert first(ev, E.DAMAGE, P2) is None
    assert first(ev, E.ABILITY, P2).data["ability"] == "volt-absorb"
    assert first(ev, E.HEAL, P2) is not None


def test_natural_cure_on_switch_out(data, make_mon, maxroll):
    p = make_mon("squirtle")
    p.ability = "natural-cure"
    eng = BattleEngine(data, [p, make_mon("charmander")],
                       [make_mon("bulbasaur")], rng=maxroll)
    eng.active(P1).status = "poison"
    ev = eng.submit_turn(SwitchAction(1), MoveAction("growl"))
    assert first(ev, E.STATUS_CURED, P1) is not None
    assert p.status is None


def test_thick_fat_halves_fire(data, make_mon, maxroll):
    eng = BattleEngine(data, [make_mon("charmander")],
                       [make_mon("squirtle", level=100)], rng=maxroll)
    atk, dfn = eng.active(P1), eng.active(P2)
    ember = data.move("ember")
    plain, _ = calc_damage(data, atk, dfn, ember, rng=maxroll)
    dfn.state.ability = "thick-fat"
    halved, _ = calc_damage(data, atk, dfn, ember, rng=maxroll)
    assert halved < plain


# ── screens, seeds, traps, misc ──────────────────────────────────────

def test_reflect_halves_physical_damage(data, make_mon, maxroll):
    eng = BattleEngine(data, [make_mon("pikachu", level=100, moves=["tackle"])],
                       [make_mon("squirtle", level=100,
                                 moves=["reflect", "recover"])], rng=maxroll)
    ev1 = eng.submit_turn(MoveAction("tackle"), MoveAction("reflect"))
    d1 = first(ev1, E.DAMAGE, P2).data["amount"]  # tackle lands pre-screen
    assert first(ev1, E.SCREEN_START, P2) is not None
    ev2 = eng.submit_turn(MoveAction("tackle"), MoveAction("recover"))
    d2 = first(ev2, E.DAMAGE, P2).data["amount"]
    assert d2 <= d1 // 2 + 1


def test_leech_seed_drains_and_grass_is_immune(data, make_mon, maxroll):
    eng = BattleEngine(data,
                       [make_mon("bulbasaur", moves=["leech-seed", "growl"])],
                       [make_mon("squirtle", level=100)], rng=maxroll)
    bulba = eng.active(P1)
    bulba.take_damage(30)
    hp = bulba.current_hp
    ev = eng.submit_turn(MoveAction("leech-seed"), MoveAction("recover"))
    assert first(ev, E.LEECH_SEED, P2) is not None
    drain = first(ev, E.LEECH_DRAIN, P2)
    assert drain.data["amount"] == eng.active(P2).max_hp // 8
    assert bulba.current_hp == hp + drain.data["amount"]
    # grass types can't be seeded
    eng2 = BattleEngine(data, [make_mon("squirtle", moves=["leech-seed"])],
                        [make_mon("bulbasaur")], rng=maxroll)
    ev = eng2.submit_turn(MoveAction("leech-seed"), MoveAction("growl"))
    assert first(ev, E.MOVE_FAILED, P1) is not None


def test_wrap_traps_blocks_switch_then_frees(data, make_mon, maxroll):
    eng = BattleEngine(data,
                       [make_mon("pikachu", moves=["wrap", "tackle"])],
                       [make_mon("squirtle", level=100), make_mon("charmander")],
                       rng=maxroll)
    ev = eng.submit_turn(MoveAction("wrap"), MoveAction("recover"))
    assert first(ev, E.TRAPPED, P2) is not None
    assert not any(isinstance(a, SwitchAction) for a in eng.legal_actions(P2))
    assert first(ev, E.TRAP_DAMAGE, P2).data["amount"] == \
        eng.active(P2).max_hp // 16
    freed = None
    for _ in range(4):  # MaxRoll rolled 4 trap turns
        ev = eng.submit_turn(MoveAction("tackle"), MoveAction("recover"))
        freed = first(ev, E.TRAP_END, P2) or freed
    assert freed is not None
    assert any(isinstance(a, SwitchAction) for a in eng.legal_actions(P2))


def test_explosion_faints_user(data, make_mon, maxroll):
    eng = BattleEngine(data, [make_mon("geodude", moves=["explosion"])],
                       [make_mon("squirtle", level=100)], rng=maxroll)
    ev = eng.submit_turn(MoveAction("explosion"), MoveAction("recover"))
    assert first(ev, E.DAMAGE, P2) is not None
    assert first(ev, E.FAINT, P1) is not None
    assert eng.winner == P2


def test_false_swipe_leaves_one_hp(data, make_mon, maxroll):
    eng = BattleEngine(data, [make_mon("pikachu", level=100,
                                       moves=["false-swipe"])],
                       [make_mon("squirtle", level=5)], rng=maxroll)
    eng.submit_turn(MoveAction("false-swipe"), MoveAction("growl"))
    assert eng.active(P2).current_hp == 1
    eng.submit_turn(MoveAction("false-swipe"), MoveAction("growl"))
    assert eng.active(P2).current_hp == 1  # never below 1


def test_roar_drags_random_bench_or_fails(data, make_mon, maxroll):
    eng = BattleEngine(data, [make_mon("geodude", moves=["roar", "rest"])],
                       [make_mon("pikachu"), make_mon("squirtle")], rng=maxroll)
    ev = eng.submit_turn(MoveAction("roar"), MoveAction("tackle"))
    assert first(ev, E.DRAGGED, P2) is not None
    assert eng.active(P2).name == "Squirtle"
    # no bench left -> fails
    eng2 = BattleEngine(data, [make_mon("geodude", moves=["roar"])],
                        [make_mon("pikachu")], rng=maxroll)
    ev = eng2.submit_turn(MoveAction("roar"), MoveAction("tackle"))
    assert first(ev, E.MOVE_FAILED, P1) is not None


def test_haze_resets_all_stages(data, make_mon, maxroll):
    eng = BattleEngine(data,
                       [make_mon("pikachu", moves=["swords-dance", "tackle"])],
                       [make_mon("squirtle", moves=["haze", "growl"])],
                       rng=maxroll)
    eng.submit_turn(MoveAction("swords-dance"), MoveAction("growl"))
    assert eng.active(P1).stages["attack"] == 1
    ev = eng.submit_turn(MoveAction("swords-dance"), MoveAction("haze"))
    assert first(ev, E.STAGES_RESET) is not None
    assert eng.active(P1).stages["attack"] == 0


def test_focus_energy_raises_crit_stage(data, make_mon, maxroll):
    eng = BattleEngine(data,
                       [make_mon("pikachu", moves=["focus-energy", "tackle"])],
                       [make_mon("squirtle")], rng=maxroll)
    eng.submit_turn(MoveAction("focus-energy"), MoveAction("growl"))
    bp = eng.active(P1)
    assert bp.vol.crit_bonus == 2
    assert eng.crit_chance_for(bp, data.move("tackle")) == pytest.approx(1 / 4)
    bp.state.held_item = "scope-lens"
    assert eng.crit_chance_for(bp, data.move("tackle")) == pytest.approx(1 / 3)
