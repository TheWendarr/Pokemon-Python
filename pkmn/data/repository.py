"""GameData: the single gateway to a game folder's data.

Layout of a game data directory:

    data/
      species/{dex:03d}-{identifier}.json    one file per species
      moves/{identifier}.json                one file per move
      types.json                             {atk_type: {def_type: mult}}
      natures.json                           {nature: {"up": stat|None, "down": stat|None}}
      items.json                             {item_id: {...}}

Design points (deliberate fixes over the previous codebase):
  * The species index is built once from *filenames* -- no opening every
    JSON per lookup (the old Species.__init__ was O(n) file reads each).
  * All keys are normalized to canonical snake_case at load time.
  * Everything is cached; the battle engine performs zero disk I/O once
    its participants are constructed.
"""
from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from typing import Optional

from .models import ItemData, MoveData, SpeciesData, norm_stat

_SPECIES_FN = re.compile(r"^(\d+)-(.+)\.json$")


class GameDataError(Exception):
    pass


class GameData:
    def __init__(self, data_dir: str):
        self.data_dir = os.path.abspath(data_dir)
        if not os.path.isdir(self.data_dir):
            raise GameDataError(f"Game data directory not found: {self.data_dir}")
        self._species_dir = os.path.join(self.data_dir, "species")
        self._moves_dir = os.path.join(self.data_dir, "moves")
        self._species_cache: dict[str, SpeciesData] = {}
        self._move_cache: dict[str, MoveData] = {}
        self._index = self._build_species_index()

    # ── species ──────────────────────────────────────────────────────
    def _build_species_index(self) -> dict[str, str]:
        """Map both identifier and dex-number strings to file paths."""
        index: dict[str, str] = {}
        if not os.path.isdir(self._species_dir):
            return index
        for fn in os.listdir(self._species_dir):
            m = _SPECIES_FN.match(fn)
            if not m:
                continue
            path = os.path.join(self._species_dir, fn)
            dex, ident = int(m.group(1)), m.group(2).lower()
            index[ident] = path
            index[str(dex)] = path
        return index

    def species(self, identifier) -> SpeciesData:
        """Look up by identifier ('pikachu', 'Pikachu') or dex number (25, '025')."""
        key = str(identifier).strip().lower().lstrip("0") or "0"
        key = key.replace(" ", "-")
        if key in self._species_cache:
            return self._species_cache[key]
        path = self._index.get(key)
        if path is None:
            raise GameDataError(f"Species not found: {identifier!r}")
        with open(path, encoding="utf-8") as f:
            sp = SpeciesData.from_dict(json.load(f))
        self._species_cache[key] = sp
        self._species_cache[sp.id] = sp
        self._species_cache[str(sp.dex)] = sp
        return sp

    def all_species_ids(self) -> list[str]:
        return sorted({k for k in self._index if not k.isdigit()})

    # ── moves ────────────────────────────────────────────────────────
    def move(self, move_id: str) -> MoveData:
        key = move_id.strip().lower().replace(" ", "-").replace("'", "")
        if key in self._move_cache:
            return self._move_cache[key]
        path = os.path.join(self._moves_dir, f"{key}.json")
        if not os.path.isfile(path):
            raise GameDataError(f"Move not found: {move_id!r}")
        with open(path, encoding="utf-8") as f:
            mv = MoveData.from_dict(json.load(f))
        self._move_cache[key] = mv
        return mv

    def has_move(self, move_id: str) -> bool:
        key = move_id.strip().lower().replace(" ", "-").replace("'", "")
        return key in self._move_cache or os.path.isfile(
            os.path.join(self._moves_dir, f"{key}.json"))

    # ── flat tables ──────────────────────────────────────────────────
    @lru_cache(maxsize=None)
    def _table(self, name: str) -> dict:
        path = os.path.join(self.data_dir, name)
        if not os.path.isfile(path):
            raise GameDataError(f"Missing data table: {path}")
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    @property
    def type_chart(self) -> dict:
        return self._table("types.json")

    def effectiveness(self, move_type: str, defender_types) -> float:
        chart = self.type_chart
        mult = 1.0
        for t in defender_types:
            mult *= chart.get(move_type, {}).get(t, 1.0)
        return mult

    @property
    def natures(self) -> dict:
        """{nature: {'up': stat|None, 'down': stat|None}} with canonical keys."""
        raw = self._table("natures.json")
        return {
            name.lower(): {
                "up": norm_stat(v["up"]) if v.get("up") else None,
                "down": norm_stat(v["down"]) if v.get("down") else None,
            }
            for name, v in raw.items()
        }

    def item(self, item_id: str) -> Optional[ItemData]:
        d = self._table("items.json").get(item_id)
        if d is None:
            return None
        return ItemData.from_dict({"id": item_id, **d})
