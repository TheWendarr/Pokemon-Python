"""Game-folder validator.

Lints a content folder (manifest, maps, scripts, encounters, trainers)
against the dataset and the engine's command set — the authoring
equivalent of `pkmn.cli.audit` for data. Runs headless (no pygame):
maps are parsed with pytmx's base loader.

    python -m pkmn.cli.lint --game examples/isleton [--data game/data]
"""
from __future__ import annotations

import argparse
import json
import os

import pytmx

from ..data.repository import GameData
from ..game.contract import (BASE_LAYER, DIRECTIONS, ENGINE_VERSION,
                             FEATURES, MAP_PROPS, OBJECT_TYPES, OPPOSITE,
                             RENDER_FLAGS, SCRIPT_COMMANDS, SETTINGS,
                             TILE_FLAGS, TILE_META, TRIGGER_WHEN, WEATHERS,
                             compatible)

DIRS = {"up", "down", "left", "right"}      # sprite facings (not map edges)


class Lint:
    def __init__(self, game_dir: str, data: GameData):
        self.dir = game_dir
        self.data = data
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.maps: dict[str, pytmx.TiledMap] = {}
        self.scripts: dict = {}
        self.dex: set | None = None

    def err(self, where, msg):
        self.errors.append(f"{where}: {msg}")

    def warn(self, where, msg):
        self.warnings.append(f"{where}: {msg}")

    # ── pieces ───────────────────────────────────────────────────────
    def _json(self, name, required=False):
        path = os.path.join(self.dir, name)
        if not os.path.exists(path):
            if required:
                self.err(name, "missing")
            return {}
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            self.err(name, f"invalid JSON ({e})")
            return {}

    def check_species(self, where, sid, level=None):
        try:
            self.data.species(sid)
        except Exception:
            self.err(where, f"unknown species {sid!r}")
            return
        if self.dex is not None and sid not in self.dex:
            self.err(where, f"species {sid!r} not in the manifest dex subset")
        if level is not None and not 1 <= int(level) <= 100:
            self.err(where, f"bad level {level} for {sid}")

    def check_party_spec(self, where, spec):
        if isinstance(spec, list):                # rich per-mon party
            for m in spec:
                self.check_species(where, m.get("species", "?"),
                                   m.get("level", 5))
                if m.get("item"):
                    self.check_item(where, m["item"])
                for mv in (m.get("moves") or []):
                    if not self.data.has_move(mv):
                        self.warn(where, f"unknown move {mv!r}")
            return
        for part in str(spec).split("|"):
            sid, _, rest = part.strip().partition(":")
            lvl, _, item = rest.partition("@")
            self.check_species(where, sid, lvl or 5)
            if item:
                self.check_item(where, item)

    def check_item(self, where, iid):
        if self.data.item(iid) is None:
            self.err(where, f"unknown item {iid!r}")

    # ── sections ─────────────────────────────────────────────────────
    def load_maps(self):
        mdir = os.path.join(self.dir, "maps")
        if not os.path.isdir(mdir):
            self.err("maps/", "missing directory")
            return
        for fn in sorted(os.listdir(mdir)):
            if not fn.endswith(".tmx"):
                continue
            mid = fn[:-4]
            try:
                self.maps[mid] = pytmx.TiledMap(os.path.join(mdir, fn))
            except Exception as e:
                self.err(f"maps/{fn}", f"failed to parse ({e})")
        for mid, tm in self.maps.items():
            try:
                tm.get_layer_by_name(BASE_LAYER)
            except Exception:
                self.err(f"maps/{mid}", f"no {BASE_LAYER!r} layer")
            props = getattr(tm, "properties", {}) or {}
            w = props.get("weather")
            if w and w not in WEATHERS:
                self.err(f"maps/{mid}", f"unknown weather {w!r}")
            for key in props:
                if key not in MAP_PROPS:
                    self.warn(f"maps/{mid}", f"unknown map property {key!r}")
            # tile flags: typos here silently disable collision/grass
            allowed = TILE_FLAGS | RENDER_FLAGS | TILE_META
            for tp in getattr(tm, "tile_properties", {}).values():
                for key in tp:
                    if key not in allowed:
                        self.err(f"maps/{mid}",
                                 f"unknown tile flag {key!r} "
                                 f"(known: {sorted(TILE_FLAGS | RENDER_FLAGS)})")

    def _blocked(self, tm, x, y) -> bool:
        if not (0 <= x < tm.width and 0 <= y < tm.height):
            return True
        layers = [i for i, l in enumerate(tm.layers)
                  if isinstance(l, pytmx.TiledTileLayer)]
        for li in layers:
            props = tm.get_tile_properties(x, y, li) or {}
            if props.get("blocked"):
                return True
        return False

    def check_connections(self):
        for mid, tm in self.maps.items():
            props = getattr(tm, "properties", {}) or {}
            for d in DIRECTIONS:
                nb = props.get(f"connect_{d}")
                if nb is None:
                    continue
                where = f"maps/{mid}"
                if nb not in self.maps:
                    self.err(where, f"connect_{d} -> unknown map {nb!r}")
                    continue
                off = props.get(f"offset_{d}", 0)
                try:
                    int(off)
                except (TypeError, ValueError):
                    self.err(where, f"offset_{d} {off!r} is not an integer")
                back = (getattr(self.maps[nb], "properties", {}) or {}).get(
                    f"connect_{OPPOSITE[d]}")
                if back != mid:
                    self.warn(where, f"connect_{d} -> {nb} is one-way "
                                     f"({nb} does not connect {OPPOSITE[d]} "
                                     f"back to {mid})")

    def check_map_objects(self):
        for mid, tm in self.maps.items():
            where = f"maps/{mid}"
            tw, th = tm.tilewidth, tm.tileheight
            seen_spawn = False
            for obj in tm.objects:
                t = (int(obj.x // tw), int(obj.y // th))
                p = obj.properties
                if obj.name == "spawn":
                    seen_spawn = True
                    if self._blocked(tm, *t):
                        self.err(where, f"spawn at {t} is blocked")
                elif obj.name == "warp":
                    dest = p.get("to_map")
                    if dest not in self.maps:
                        self.err(where, f"warp at {t} -> unknown map {dest!r}")
                        continue
                    dt = (int(p.get("to_x", -1)), int(p.get("to_y", -1)))
                    target = self.maps[dest]
                    if not (0 <= dt[0] < target.width
                            and 0 <= dt[1] < target.height):
                        self.err(where, f"warp at {t} -> {dest} {dt} out of bounds")
                    elif self._blocked(target, *dt):
                        self.warn(where, f"warp at {t} -> {dest} {dt} lands on a blocked tile")
                    if p.get("facing", "down") not in DIRS:
                        self.err(where, f"warp at {t}: bad facing")
                elif obj.name in ("npc", "sign", "trigger"):
                    sid = p.get("script", "")
                    if sid and sid not in self.scripts:
                        self.err(where, f"{obj.name} at {t}: unknown script {sid!r}")
                elif obj.name == "trainer":
                    self.check_party_spec(f"{where} trainer at {t}",
                                          p.get("party", "patrat:3"))
                    if p.get("facing", "down") not in DIRS:
                        self.err(where, f"trainer at {t}: bad facing")
                if obj.name not in OBJECT_TYPES:
                    self.err(where, f"unknown object type {obj.name!r} at {t} "
                                    f"(known: {sorted(OBJECT_TYPES)})")
                else:
                    for key in p:
                        if key not in OBJECT_TYPES[obj.name]:
                            self.warn(where, f"{obj.name} at {t}: "
                                             f"unknown property {key!r}")
                if obj.name == "trigger":
                    if not p.get("script"):
                        self.err(where, f"trigger at {t}: no script")
                    if p.get("when", "step") not in TRIGGER_WHEN:
                        self.err(where, f"trigger at {t}: bad 'when' "
                                        f"{p.get('when')!r}")
            if not seen_spawn:
                self.warn(where, "no spawn object")

    def check_scripts(self):
        def branches(step):
            out = []
            if "if" in step or "if_flag" in step:
                out += [step.get("then", []), step.get("else", [])]
            for k in ("if_money", "if_var", "if_self_switch"):
                if k in step:
                    out += [step[k].get("then", []), step[k].get("else", [])]
            if "while" in step:
                out.append(step.get("do", []))
            if "choice" in step:
                out += [o.get("then", [])
                        for o in step["choice"].get("options", [])]
            return out

        def walk(name, steps):
            if not isinstance(steps, list):
                self.err(f"scripts.json[{name}]", "not a list")
                return
            for i, step in enumerate(steps):
                where = f"scripts.json[{name}][{i}]"
                if not isinstance(step, dict) or not set(step) & SCRIPT_COMMANDS:
                    self.err(where, f"unknown command in {sorted(step)}")
                    continue
                if "battle" in step:
                    self.check_party_spec(where, step["battle"].get("party", ""))
                if "give_item" in step:
                    self.check_item(where, step["give_item"].get("item", "?"))
                if "warp" in step and step["warp"].get("map") not in self.maps:
                    self.err(where, f"warp to unknown map "
                                    f"{step['warp'].get('map')!r}")
                if "choice" in step and not step["choice"].get("options"):
                    self.err(where, "choice with no options")
                if "shop" in step:
                    for iid in step["shop"].get("items", []):
                        self.check_item(where, iid)
                    for iid in step["shop"].get("prices", {}):
                        self.check_item(where, iid)
                if "give_pokemon" in step:
                    g = step["give_pokemon"]
                    self.check_species(where, g.get("species", "?"),
                                       g.get("level", 5))
                    if g.get("item"):
                        self.check_item(where, g["item"])
                for j, sub in enumerate(branches(step)):
                    walk(f"{name}.{i}.{j}", sub)

        for name, defn in self.scripts.items():
            if isinstance(defn, dict) and "pages" in defn:
                for pi, page in enumerate(defn["pages"]):
                    walk(f"{name}.page{pi}", page.get("do", []))
            else:
                walk(name, defn)

    ENC_METHODS = {"land", "surf", "old_rod", "good_rod", "super_rod",
                   "rock_smash", "headbutt", "cave"}

    def check_encounters(self, enc):
        def check_table(where, table):
            if not isinstance(table, list):
                self.err(where, "encounter table must be a list")
                return
            for e in table:
                self.check_species(where, e.get("species", "?"))
                if int(e.get("min", 1)) > int(e.get("max", 1)):
                    self.err(where, f"min > max for {e.get('species')}")
                if int(e.get("weight", 1)) <= 0:
                    self.err(where, "non-positive weight")

        for mid, table in enc.items():
            where = f"encounters.json[{mid}]"
            if mid not in self.maps:
                self.err(where, "unknown map")
            if isinstance(table, dict):           # per-method tables
                for method, slots in table.items():
                    if method not in self.ENC_METHODS:
                        self.warn(where, f"unknown encounter method {method!r}")
                    check_table(f"{where}.{method}", slots)
            else:                                 # legacy flat list == land
                check_table(where, table)

    def check_manifest(self, m):
        if not m:
            self.err("game.json", "missing or empty manifest")
            return
        ev = m.get("engine_version", ENGINE_VERSION)
        if not compatible(ev):
            self.err("game.json", f"engine_version {ev!r} unsupported "
                                  f"(engine is v{ENGINE_VERSION})")
        self.dex = set(m["dex"]) if m.get("dex") else None
        st = m.get("starter") or {}          # absent/null -> empty party, OK
        if st.get("species"):
            self.check_species("game.json starter", st["species"],
                               st.get("level", 5))
        # start (required) and whiteout (optional) must point at real,
        # walkable tiles -- both are entry points into the world graph.
        for key, required in (("start", True), ("whiteout", False)):
            loc = m.get(key)
            if loc is None:
                if required:
                    self.err("game.json", f"missing {key} location")
                continue
            if loc.get("map") not in self.maps:
                self.err("game.json", f"{key} map {loc.get('map')!r} not found")
            elif loc.get("tile") and self._blocked(self.maps[loc["map"]],
                                                   *loc["tile"]):
                self.err("game.json", f"{key} tile {loc['tile']} is blocked")
        for key in m.get("features", {}):
            if key not in FEATURES:
                self.err("game.json features",
                         f"unknown feature toggle {key!r} "
                         f"(known: {sorted(FEATURES)})")
        for key in m.get("settings", {}):
            if key not in SETTINGS:
                self.err("game.json settings",
                         f"unknown setting {key!r} "
                         f"(known: {sorted(SETTINGS)})")
        for iid in m.get("bag", {}):
            self.check_item("game.json bag", iid)
        for spr in ("player.png", "npc.png"):
            if not os.path.exists(os.path.join(self.dir, spr)):
                self.err(spr, "missing sprite sheet")

    # ── run ──────────────────────────────────────────────────────────
    def run(self) -> int:
        manifest = self._json("game.json", required=True)
        self.scripts = self._json("scripts.json")
        self.load_maps()
        self.check_manifest(manifest)
        self.check_map_objects()
        self.check_connections()
        self.check_scripts()
        self.check_encounters(self._json("encounters.json"))
        for w in self.warnings:
            print("WARN ", w)
        for e in self.errors:
            print("ERROR", e)
        n_obj = sum(len(list(t.objects)) for t in self.maps.values())
        print(f"checked {len(self.maps)} maps, {n_obj} objects, "
              f"{len(self.scripts)} scripts -> "
              f"{len(self.errors)} error(s), {len(self.warnings)} warning(s)")
        return 1 if self.errors else 0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", default="game/assets")
    ap.add_argument("--data", default="game/data")
    a = ap.parse_args()
    raise SystemExit(Lint(a.game, GameData(a.data)).run())


if __name__ == "__main__":
    main()
