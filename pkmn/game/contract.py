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
`ENGINE_VERSION` is the contract version. A region declares the version
it was authored against in `game.json` ("engine_version"). The engine
loads a region whose declared version is <= its own (older content keeps
working); a region targeting a *newer* engine is refused with a clear
message rather than failing deep in a scene. Bump `ENGINE_VERSION` only
when the contract changes in a way that could affect existing regions.
"""
from __future__ import annotations

ENGINE_VERSION = 3

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
    "blocked",     # solid: cannot be entered from any direction
    "grass",       # tall grass: rolls for a wild encounter on entry
    "surf",        # water: crossable only while surfing (needs can_surf)
    "cuttable",    # obstacle removed by Cut (needs can_cut); then walkable
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
CAPABILITY_FLAGS: set[str] = {"can_surf", "can_cut"}

# ── maps ─────────────────────────────────────────────────────────────
# Per-map custom properties, set on the map (.tmx). Connections + offsets
# describe a seamless overworld (see docs/ENGINE_PHILOSOPHY.md); a map
# with no connections is a discrete, warp-linked map.
DIRECTIONS: tuple[str, ...] = ("north", "south", "east", "west")
MAP_PROPS: set[str] = (
    {"weather", "border", "encounter_chance", "music", "battle_bg"}
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
    # state: flags / money / items
    "heal", "give_item", "give_money", "take_money",
    "set_flag", "clear_flag", "give_pokemon",
    # state: variables / self-switches (event runtime)
    "set_var", "add_var", "set_self_switch", "clear_self_switch",
    # control flow
    "if", "if_flag", "if_money", "if_var", "if_self_switch",
    "while", "label", "goto",
    # world / npcs
    "warp", "move_npc", "move_route", "face_npc", "hide_npc", "screen",
}

# ── helpers ──────────────────────────────────────────────────────────
def compatible(region_version) -> bool:
    """True if a region targeting `region_version` runs on this engine."""
    try:
        return 1 <= int(region_version) <= ENGINE_VERSION
    except (TypeError, ValueError):
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
