"""The content contract.

This module is the single source of truth for *what a region may
contain*: the engine version, the tile flags, map properties, object
types, script commands, and weather names the engine understands. Both
the runtime and the linter import these, so "if it lints, it runs"
holds -- the validator and the engine can never drift apart.

Pure data and tiny helpers only: no pygame, no I/O. Safe to import from
the headless linter.

Versioning
----------
`ENGINE_VERSION` is the public semver of this engine release ("major.minor").
A game declares the version it was authored for in `game.json`
("engine_version"). Compatibility is determined by major version only:

  - A game targeting major N runs on any engine whose major is >= N.
  - A game targeting major N cannot run on an engine whose major is < N.

This means all 1.x games run on every 1.x engine and on any future 2.x+
engine. A game built for 2.0 cannot run on a 1.x engine.

Bump the MAJOR component only when adding features that old engines cannot
safely ignore. Bump the MINOR component for additive, backward-compatible
additions (new optional fields, new commands, new tile flags).
"""
from __future__ import annotations

ENGINE_VERSION = "1.0"

# ── tiles ────────────────────────────────────────────────────────────
# Per-tile properties, set on tiles in the tileset (.tsx). Anything else
# on a tile is a typo the linter flags. pytmx's own bookkeeping keys are
# ignored by the linter (see TILE_META).
LEDGE_FLAGS: dict[str, str] = {            # facing the player jumps -> flag
    "down": "ledge_down", "up": "ledge_up",
    "left": "ledge_left", "right": "ledge_right",
}
# Per-direction passage (RMXP partial passability). A tile carrying
# `block_<dir>` cannot be crossed moving in that direction -- counters you
# talk over, one-way fences, cliff edges, bridge sides. `blocked` is the
# all-directions case kept as a shorthand.
DIR_BLOCK_FLAGS: dict[str, str] = {
    "down": "block_down", "up": "block_up",
    "left": "block_left", "right": "block_right",
}
REVERSE_DIR: dict[str, str] = {"up": "down", "down": "up",
                               "left": "right", "right": "left"}
TILE_FLAGS: set[str] = {
    "blocked",         # solid: cannot be entered from any direction
    "grass",           # tall grass: rolls for a wild encounter on entry
    "surf",            # water: crossable only while surfing (needs can_surf)
    "cuttable",        # obstacle removed by Cut (needs can_cut); then walkable
    "rock_smash",      # boulder removed by Rock Smash (needs can_rock_smash); then walkable
    "waterfall",       # surf tile that blocks upward movement without can_waterfall
    "headbutt_tree",   # tree that rolls a headbutt encounter when bumped (A)
    "z_up",            # stepping here raises the player's Z level by 1 (top of staircase)
    "z_down",          # stepping here lowers the player's Z level by 1 (bottom of staircase)
    *LEDGE_FLAGS.values(),   # one-way ledges: jumped over in that direction
    *DIR_BLOCK_FLAGS.values(),   # per-direction (partial) passability
}
TILE_META: set[str] = {"id", "width", "height", "frames", "type", "name"}

# Render-only tile properties (do not affect collision/behaviour).
#   over: draw this tile *above* the player sprite (RMXP "priority > 0":
#         tree canopies, roofs, bridges, second-floor overpasses).
RENDER_FLAGS: set[str] = {"over"}

# Every property the linter accepts on a tileset tile.
TILE_PROPS: set[str] = TILE_FLAGS | RENDER_FLAGS

# Maps are multi-layer (engine_version >= 2). All tile layers are drawn
# bottom-to-top; tiles flagged `over` draw in a second pass above the
# player. Collision and terrain flags (blocked/grass/surf/...) are OR'd
# across every layer at a cell. `BASE_LAYER` must exist on every map as
# the bottom layer; additional tile layers are optional and unnamed-order
# is their draw order.
BASE_LAYER: str = "ground"

# Reserved state flags the engine reads as field-move capabilities. Content
# grants them like HMs (e.g. {"set_flag": "can_cut"} from an NPC script).
CAPABILITY_FLAGS: set[str] = {
    "can_surf",        # ride water tiles
    "can_cut",         # clear cuttable obstacles
    "can_strength",    # push strength_block boulders
    "can_rock_smash",  # break rock_smash obstacles
    "can_flash",       # illuminate dark caves / reduce encounter rate
    "can_waterfall",   # climb waterfall tiles while surfing
    "can_dive",        # dive into/from underwater tiles
    "can_fly",         # open the Town Map to fly to visited locations
    "can_headbutt",    # headbutt trees to trigger encounters
}

# ── maps ─────────────────────────────────────────────────────────────
# Per-map custom properties, set on the map (.tmx). Connections + offsets
# describe a seamless overworld (see docs/ENGINE_PHILOSOPHY.md); a map
# with no connections is a discrete, warp-linked map.
DIRECTIONS: tuple[str, ...] = ("north", "south", "east", "west")
MAP_PROPS: set[str] = (
    {"weather", "border", "encounter_chance", "music", "battle_bg",
     "heal_point",      # JSON {map, tile}: whiteout respawn override for this map
     "escape_point",    # JSON {map, tile}: Escape Rope destination for this map
     "dark_cave",       # bool: cave is pitch-black without Flash
     "fly_name",        # display name shown in the Town Map / Fly list
     }
    | {f"connect_{d}" for d in DIRECTIONS}
    | {f"offset_{d}" for d in DIRECTIONS}
)
WEATHERS: set[str] = {"rain", "sun", "sandstorm", "hail"}

# Each edge's connection resolves an off-map tile into a neighbour. The
# rule (mirroring Gen 1): the perpendicular axis is shifted by `offset`,
# the parallel axis by the crossed map's size. Kept here so the runtime
# resolver and the linter agree on the geometry.
#   north: (nx, ny) = (x - offset, y + neighbour.height)
#   south: (nx, ny) = (x - offset, y - this.height)
#   west : (nx, ny) = (x + neighbour.width, y - offset)
#   east : (nx, ny) = (x - this.width,  y - offset)
OPPOSITE: dict[str, str] = {"north": "south", "south": "north",
                            "east": "west", "west": "east"}

# ── objects ──────────────────────────────────────────────────────────
# Object-layer types and the property keys each accepts. The linter
# flags unknown types and unknown keys.
OBJECT_TYPES: dict[str, set[str]] = {
    "warp":    {"to_map", "to_x", "to_y", "facing"},
    "npc":     {"display", "facing", "dialog", "heal", "script",
                "visible_unless"},
    "trainer": {"display", "facing", "sight", "party", "prize", "flag",
                "before", "after"},
    "trigger": {"script", "unless_flag", "when", "time"},
    "sign":    {"dialog", "script"},
    "spawn":   set(),
}
TRIGGER_WHEN: set[str] = {"step", "enter", "autorun", "parallel"}

# ── scripts ──────────────────────────────────────────────────────────
# Command keys the event runtime (pkmn/game/script.py) implements. A leaf
# step is a dict with exactly one of these as its command key; structured
# steps (if/while/choice) carry nested command lists. Conditions used by
# if/while/event-pages: flag, var, self_switch, item, money, not, all, any.
SCRIPT_COMMANDS: set[str] = {
    # dialogue / flow
    "say", "wait", "choice", "shop", "pc", "battle",
    # state: flags / money / items / badges
    "heal", "give_item", "give_money", "take_money",
    "set_flag", "clear_flag", "give_pokemon", "give_badge",
    # state: variables / self-switches (event runtime)
    "set_var", "add_var", "set_self_switch", "clear_self_switch",
    # control flow
    "if", "if_flag", "if_money", "if_var", "if_self_switch",
    "while", "label", "goto",
    # world / npcs
    "warp", "move_npc", "move_route", "face_npc", "hide_npc", "screen",
}

# ── manifest features / settings ─────────────────────────────────────
# Designer toggles: manifest["features"][name] turns optional engine
# systems on or off (default ON). The linter flags unknown keys.
FEATURES: set[str] = {
    "encounters", "trainers", "experience", "evolution",
    "move_replacement", "running",
    "menu_party", "menu_bag", "saving", "pokedex", "controls",
    "badges",   # badge display in the pause menu
    "fly",      # Town Map / Fly scene accessible when can_fly is set
}

# Numeric / string knobs: manifest["settings"][name]. The linter flags
# unknown keys so typos can't silently disable a setting.
SETTINGS: set[str] = {"encounter_chance", "daynight"}

# ── helpers ──────────────────────────────────────────────────────────
def compatible(region_version) -> bool:
    """True if a region targeting `region_version` runs on this engine.

    Compatibility is major-version only: game.major <= engine.major.
    Accepts both the legacy integer format (1, 2, 3) and the semver
    string format ("1.0", "1.9", "2.0").
    """
    try:
        game_major = int(str(region_version).split(".")[0])
        engine_major = int(ENGINE_VERSION.split(".")[0])
        return 0 < game_major <= engine_major
    except (TypeError, ValueError, AttributeError):
        return False


def rebase(direction: str, x: int, y: int,
           this_w: int, this_h: int, nb_w: int, nb_h: int,
           offset: int) -> tuple[int, int]:
    """Map an off-edge coordinate into the neighbour's coordinate frame."""
    if direction == "north":
        return x - offset, y + nb_h
    if direction == "south":
        return x - offset, y - this_h
    if direction == "west":
        return x + nb_w, y - offset
    if direction == "east":
        return x - this_w, y - offset
    raise ValueError(f"bad direction {direction!r}")
