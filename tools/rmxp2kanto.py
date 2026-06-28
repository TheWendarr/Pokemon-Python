#!/usr/bin/env python3
# RMXP/Essentials -> Pokemon-Python importer (reference tool).
# Set PROJ below to an extracted RPG Maker XP / Essentials project dir,
# and OUT to the target examples/<name> folder, then run from the repo
# root: `python tools/rmxp2kanto.py`. Requires: pip install rubymarshal Pillow
"""rmxp2kanto: convert an RPG Maker XP / Pokemon Essentials project into a
content folder for the Pokemon-Python engine (TMX + tiles.tsx + game.json).

Converts geometry, collision, grass/surf/ledge flags (from tileset terrain
tags + passability), map connections (PBS connections.txt), wild encounters
(PBS encounters.txt, Land slots), and door/edge warps (RMXP transfer events,
event code 201). Behavior beyond that — trainers, scripted cutscenes, gym
puzzles — is NOT convertible to the engine's flat script DSL and is dropped.
"""
import os, re, struct, sys
from collections import Counter, defaultdict, deque
from PIL import Image
from rubymarshal.reader import load

PROJ = "/home/claude/pack/JohtoBlaziken's Bootleg Pokemon FireRed v0.6"
REPO = "/home/claude/Pokemon-Python"
OUT  = os.path.join(REPO, "examples", "kanto_frlg")
SEED = 2            # Lappet Town (this bootleg's Pallet Town)
MAXMAPS = 14       # cap the converted overworld component for a tight POC

os.makedirs(os.path.join(OUT, "maps"), exist_ok=True)

def rstr(x):
    if x is None: return ""
    if isinstance(x, bytes): return x.decode("utf-8", "replace")
    s = str(x)
    return s

def slug(s):
    s = rstr(s).lower().replace("\\pn", "player")
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s or "map"

def tbl(ud):
    b = ud._private_data
    dim, x, y, z, tot = struct.unpack_from("<5i", b, 0)
    vals = struct.unpack_from("<%dh" % tot, b, 20)
    return x, y, z, vals

# ── load engine species ids (to validate encounters) ────────────────
def load_species_ids():
    import json, glob
    base = os.path.join(REPO, "game", "data")
    for cand in ("species.json", "pokemon.json"):
        p = os.path.join(base, cand)
        if os.path.exists(p):
            d = json.load(open(p))
            return set(d.keys()) if isinstance(d, dict) else {str(e.get("id")) for e in d}
    d = os.path.join(base, "species")
    if os.path.isdir(d):
        return {re.sub(r"^\d+-", "", os.path.splitext(f)[0])
                for f in os.listdir(d) if f.endswith(".json")}
    # last resort: scan any json for an id-keyed dict that contains 'pikachu'
    for p in glob.glob(os.path.join(base, "*.json")):
        try:
            d = json.load(open(p))
            if isinstance(d, dict) and "pikachu" in d:
                return set(d.keys())
        except Exception:
            pass
    return None
SPECIES = load_species_ids()
print("engine species set:", "loaded %d" % len(SPECIES) if SPECIES else "NOT FOUND (encounters skipped)")

def norm_species(name):
    n = rstr(name).strip().lower()
    n = n.replace("♀", "-f").replace("♂", "-m").replace("'", "").replace(".", "")
    n = re.sub(r"\s+", "-", n)
    return n

# ── parse PBS metadata (outdoor flags + names) ──────────────────────
outdoor = {}
meta = open(os.path.join(PROJ, "PBS", "metadata.txt"), encoding="utf-8-sig").read()
for blk in re.finditer(r"\[(\d+)\](.*?)(?=\n\[|\Z)", meta, re.S):
    mid = int(blk.group(1)); body = blk.group(2)
    outdoor[mid] = "Outdoor=true" in body

# ── parse PBS connections ───────────────────────────────────────────
EDGE = {"North": "north", "South": "south", "East": "east", "West": "west"}
conns = []  # (a, ea, oa, b, eb, ob)
for line in open(os.path.join(PROJ, "PBS", "connections.txt"), encoding="utf-8-sig"):
    line = line.strip()
    if not line or line.startswith("#"): continue
    parts = line.split(",")
    if len(parts) == 6 and parts[1] in EDGE and parts[4] in EDGE:
        a, ea, oa, b, eb, ob = parts
        conns.append((int(a), ea, int(oa), int(b), eb, int(ob)))

# ── parse PBS encounters (all methods) ──────────────────────────────
METHOD_MAP = {"Land": "land", "LandDay": "land", "LandNight": "land",
              "LandMorning": "land", "Cave": "cave", "Water": "surf",
              "OldRod": "old_rod", "GoodRod": "good_rod",
              "SuperRod": "super_rod", "RockSmash": "rock_smash",
              "HeadbuttLow": "headbutt", "HeadbuttHigh": "headbutt"}
enc_by_map = {}
etxt = open(os.path.join(PROJ, "PBS", "encounters.txt"), encoding="utf-8-sig").read().split("#########################")
for block in etxt:
    lines = [l.rstrip() for l in block.splitlines() if l.strip()]
    if not lines: continue
    m = re.match(r"(\d+)", lines[0])
    if not m: continue
    mid = int(m.group(1))
    by_method, cur = {}, None
    for l in lines[1:]:
        if "," not in l and re.match(r"[A-Za-z]", l):
            cur = METHOD_MAP.get(l.strip())            # section header
        elif "," in l and cur and re.match("[A-Za-z♀♂.'\\- ]", l):
            parts = [p.strip() for p in l.split(",")]
            if len(parts) >= 3 and parts[1].isdigit():
                by_method.setdefault(cur, []).append(
                    (parts[0], int(parts[1]), int(parts[-1])))
    if by_method:
        enc_by_map[mid] = by_method

# ── load Tilesets + MapInfos ────────────────────────────────────────
TS = load(open(os.path.join(PROJ, "Data", "Tilesets.rxdata"), "rb"))
def tileset_meta(tid):
    a = TS[tid].attributes
    _, _, _, pas = tbl(a["@passages"])
    _, _, _, ter = tbl(a["@terrain_tags"])
    _, _, _, pri = tbl(a["@priorities"])
    return (rstr(a["@tileset_name"]),
            [rstr(s) for s in a["@autotile_names"]], pas, ter, pri)
MI = load(open(os.path.join(PROJ, "Data", "MapInfos.rxdata"), "rb"))
NAME = {int(rstr(k)): rstr(v.attributes.get("@name", "")) for k, v in MI.items()}

def load_map(mid):
    a = load(open(os.path.join(PROJ, "Data", "Map%03d.rxdata" % mid), "rb")).attributes
    x, y, z, vals = tbl(a["@data"])
    return dict(w=x, h=y, z=z, data=vals, tsid=int(rstr(a["@tileset_id"])), events=a["@events"])

def transfers(mp):
    out = []
    for eid, ev in mp["events"].items():
        ea = ev.attributes
        ex, ey = int(rstr(ea["@x"])), int(rstr(ea["@y"]))
        for pg in ea.get("@pages", []):
            for c in pg.attributes.get("@list", []):
                if int(rstr(c.attributes["@code"])) == 201:
                    p = [int(rstr(v)) for v in c.attributes["@parameters"]
                         if rstr(v).lstrip("-").isdigit()]
                    if len(p) >= 4:
                        out.append((ex, ey, p[1], p[2], p[3], p[4] if len(p) > 4 else 2))
    return out

# ── choose connected outdoor component from SEED ────────────────────
conn_adj = defaultdict(set)
for a, ea, oa, b, eb, ob in conns:
    conn_adj[a].add(b); conn_adj[b].add(a)

chosen, q = [], deque([SEED])
seen = {SEED}
mapcache = {}
while q and len(chosen) < MAXMAPS:
    mid = q.popleft()
    if not os.path.exists(os.path.join(PROJ, "Data", "Map%03d.rxdata" % mid)):
        continue
    if not outdoor.get(mid, False):
        continue
    mapcache[mid] = load_map(mid)
    chosen.append(mid)
    nbrs = set(conn_adj[mid])
    for (_, _, tmid, *_2) in transfers(mapcache[mid]):
        nbrs.add(tmid)
    for n in nbrs:
        if n not in seen and outdoor.get(n, False):
            seen.add(n); q.append(n)
chosen_set = set(chosen)
print("converted maps:", [(m, NAME.get(m, "")) for m in chosen])

# ── tile atlas: (tsid, rmxp_id) -> my tile index, with art + flags ──
TILE_PX = 32          # native RMXP tile size; engine upscales at load
atlas = {}            # key -> idx
atlas_meta = []       # idx -> (img, flag, over)
ts_img_cache = {}
auto_img_cache = {}

def tileset_image(name):
    if name not in ts_img_cache:
        p = None
        for ext in (".png", ".PNG"):
            cand = os.path.join(PROJ, "Graphics", "Tilesets", name + ext)
            if os.path.exists(cand): p = cand; break
        ts_img_cache[name] = Image.open(p).convert("RGBA") if p else None
    return ts_img_cache[name]

def auto_image(name):
    if name not in auto_img_cache:
        p = None
        for ext in (".png", ".PNG"):
            cand = os.path.join(PROJ, "Graphics", "Autotiles", name + ext)
            if os.path.exists(cand): p = cand; break
        auto_img_cache[name] = Image.open(p).convert("RGBA") if p else None
    return auto_img_cache[name]

def flags_for(ter, pas, tid):
    """All engine collision/terrain flags for an RMXP tile id."""
    out = []
    p = (pas[tid] & 0x0f) if tid < len(pas) else 0
    t = ter[tid] if tid < len(ter) else 0
    if p == 0x0f:
        out.append("blocked")
    else:                                  # RMXP partial passage -> directional
        if p & 0x01: out.append("block_down")
        if p & 0x02: out.append("block_left")
        if p & 0x04: out.append("block_right")
        if p & 0x08: out.append("block_up")
    if t in (2, 10):          out.append("grass")     # Grass / TallGrass
    elif t in (5, 6, 7):      out.append("surf")      # water (surfable)
    elif t == 1:              out.append("ledge_down")  # ledge (south = common)
    return out

def _flat(crop32):
    bg = Image.new("RGB", (TILE_PX, TILE_PX), (32, 40, 32))
    bg.paste(crop32, (0, 0), crop32 if crop32.mode == "RGBA" else None)
    return bg

def render_tile(tsid, tid):
    """Return (frames, flags, over). `frames` is a list of 32px RGB images
    (>1 only for animated autotiles -- the engine cycles them)."""
    name, autos, pas, ter, pri = tileset_meta(tsid)
    frames = []
    if tid >= 384:
        pos = tid - 384
        sheet = tileset_image(name)
        if sheet:
            col, row = pos % 8, pos // 8
            box = (col * 32, row * 32, col * 32 + 32, row * 32 + 32)
            if box[2] <= sheet.width and box[3] <= sheet.height:
                frames.append(_flat(sheet.crop(box)))   # native 32px
    elif 48 <= tid <= 383:
        idx = tid // 48 - 1
        a = auto_image(autos[idx]) if 0 <= idx < len(autos) and autos[idx] else None
        if a:
            nframes = max(1, a.width // 96)             # RMXP animates per 96px
            for f in range(nframes):
                # the "all-interior" 32px block of each frame: cols 2-3, rows
                # 4-5 of the 16px grid -> (32,64)-(64,96), offset by the frame.
                bx = f * 96
                box = (bx + 32, 64, bx + 64, 96)
                if box[2] <= a.width and box[3] <= a.height:
                    frames.append(_flat(a.crop(box)))
    if not frames:
        frames = [_flat(Image.new("RGBA", (TILE_PX, TILE_PX), (0, 0, 0, 0)))]
    over = bool(pri[tid] > 0) if tid < len(pri) else False   # RMXP priority>0
    return frames, flags_for(ter, pas, tid), over

anim = {}     # base atlas idx -> [frame atlas idxs...] (len>1 => animated)

def atlas_idx(tsid, tid):
    key = (tsid, tid)
    if key in atlas: return atlas[key]
    frames, flags, over = render_tile(tsid, tid)
    base = len(atlas_meta)
    atlas[key] = base
    atlas_meta.append((frames[0], flags, over))
    if len(frames) > 1:
        ids = [base]
        for im in frames[1:]:
            ids.append(len(atlas_meta))
            atlas_meta.append((im, flags, over))    # frame tiles (map-unused)
        anim[base] = ids
    return base

# ── keep all three RMXP tile layers (no 3->1 flattening) ────────────
def to_layers(mp):
    """Return [layer0, layer1, layer2] grids of engine gids (0 = empty).
    The engine OR's collision across layers and draws `over` tiles above
    the player, so trees/roofs/bridges survive instead of being lost."""
    w, h, vals = mp["w"], mp["h"], mp["data"]
    tsid = mp["tsid"]
    def cell(L, x, y): return vals[x + y * w + L * w * h]
    out = []
    for L in (0, 1, 2):
        g = [[0] * w for _ in range(h)]
        for y in range(h):
            for x in range(w):
                t = cell(L, x, y)
                g[y][x] = (atlas_idx(tsid, t) + 1) if t != 0 else 0
        out.append(g)
    return out

map_layers = {mid: to_layers(mapcache[mid]) for mid in chosen}

# ── emit tiles.png + tiles.tsx (native 32px; flags, over, animation) ─
N = len(atlas_meta)
sheet = Image.new("RGB", (N * TILE_PX, TILE_PX), (0, 0, 0))
for i, (img, _, _) in enumerate(atlas_meta):
    sheet.paste(img, (i * TILE_PX, 0))
sheet.save(os.path.join(OUT, "tiles.png"))
tsx = ['<?xml version="1.0" encoding="UTF-8"?>',
       f'<tileset version="1.10" name="kanto_frlg" tilewidth="{TILE_PX}" '
       f'tileheight="{TILE_PX}" tilecount="{N}" columns="{N}">',
       f' <image source="tiles.png" width="{N*TILE_PX}" height="{TILE_PX}"/>']
for i, (_, flags, over) in enumerate(atlas_meta):
    props = [f'<property name="{f}" type="bool" value="true"/>' for f in flags]
    if over:
        props.append('<property name="over" type="bool" value="true"/>')
    parts = ""
    if props:
        parts += f'<properties>{"".join(props)}</properties>'
    if i in anim:
        fr = "".join(f'<frame tileid="{fi}" duration="280"/>' for fi in anim[i])
        parts += f'<animation>{fr}</animation>'
    if parts:
        tsx.append(f'  <tile id="{i}">{parts}</tile>')
tsx.append("</tileset>")
open(os.path.join(OUT, "tiles.tsx"), "w").write("\n".join(tsx) + "\n")

# ── reuse the engine's own character art (no Nintendo IP committed) ──
import shutil
for f in ("player.png", "npc.png"):
    shutil.copy(os.path.join(REPO, "examples", "triad", f), os.path.join(OUT, f))

# ── file stems + helpers ────────────────────────────────────────────
stem = {mid: f"m{mid:03d}_{slug(NAME.get(mid,''))}" for mid in chosen}

def esc(v):
    if not isinstance(v, str): return v
    return (v.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;").replace("'", "&apos;"))

# connection props per map (only between chosen maps).
# Skip a connection if the target direction slot is already claimed by a
# different map (two RMXP maps can stitch to the same TMX from one side
# -- first wins; without this guard the loser direction is dangling/one-way).
mapprops = defaultdict(dict)
for a, ea, oa, b, eb, ob in conns:
    if a not in chosen_set or b not in chosen_set:
        continue
    dir_a = f"connect_{EDGE[ea]}"
    dir_b = f"connect_{EDGE[eb]}"
    if (mapprops[a].get(dir_a, stem[b]) != stem[b]
            or mapprops[b].get(dir_b, stem[a]) != stem[a]):
        continue   # slot already taken by a different neighbour; skip
    mapprops[a][dir_a] = stem[b]
    mapprops[a][f"offset_{EDGE[ea]}"] = oa - ob
    mapprops[b][dir_b] = stem[a]
    mapprops[b][f"offset_{EDGE[eb]}"] = ob - oa

DIRW = {2: "down", 4: "left", 6: "right", 8: "up", 0: "down"}

BLOCKED_GIDS = None   # filled after atlas is complete (idx+1 of blocked tiles)

def find_spawn(mid):
    global BLOCKED_GIDS
    if BLOCKED_GIDS is None:
        BLOCKED_GIDS = {i + 1 for i, (_, f, _) in enumerate(atlas_meta)
                        if "blocked" in f}
    layers = map_layers[mid]; h = len(layers[0]); w = len(layers[0][0])
    def blocked(x, y):
        return any(g[y][x] in BLOCKED_GIDS for g in layers)
    cx, cy = w // 2, h // 2
    for r in range(max(w, h)):
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                x, y = cx + dx, cy + dy
                if 0 <= x < w and 0 <= y < h and not blocked(x, y):
                    return x, y
    return cx, cy

def write_tmx(mid):
    layers = map_layers[mid]; h = len(layers[0]); w = len(layers[0][0])
    objs = []
    sx, sy = find_spawn(mid)
    objs.append(("spawn", sx, sy, {}))
    for (ex, ey, tmid, tx, ty, tdir) in transfers(mapcache[mid]):
        if tmid in chosen_set:
            objs.append(("warp", ex, ey, {"to_map": stem[tmid], "to_x": tx,
                                          "to_y": ty, "facing": DIRW.get(tdir, "down")}))
    props = dict(mapprops[mid]); props.setdefault("border", 1)
    pblock = ""
    if props:
        pblock = " <properties>" + "".join(
            f'<property name="{k}"' + (' type="int"' if isinstance(v, int) else "")
            + f' value="{esc(v)}"/>' for k, v in props.items()) + "</properties>\n"
    oxml = []
    for oid, (kind, ox, oy, op) in enumerate(objs, 1):
        inner = "".join(f'<property name="{k}"' + (' type="int"' if isinstance(v, int) else "")
                        + f' value="{esc(v)}"/>' for k, v in op.items())
        oxml.append(f'  <object id="{oid}" name="{kind}" x="{ox*TILE_PX}" '
                    f'y="{oy*TILE_PX}" width="{TILE_PX}" height="{TILE_PX}">'
                    f'<properties>{inner}</properties></object>')

    def layer_xml(lid, name, g):
        rows = "\n".join(",".join(str(v) for v in row) + "," for row in g[:-1])
        rows += "\n" + ",".join(str(v) for v in g[-1])
        return (f' <layer id="{lid}" name="{name}" width="{w}" height="{h}">\n'
                f'  <data encoding="csv">\n{rows}\n</data>\n </layer>\n')

    layer_names = ["ground", "layer1", "layer2"]
    layers_xml = "".join(layer_xml(i + 1, layer_names[i], layers[i])
                         for i in range(len(layers)))
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           f'<map version="1.10" orientation="orthogonal" renderorder="right-down" '
           f'width="{w}" height="{h}" tilewidth="{TILE_PX}" tileheight="{TILE_PX}" '
           f'infinite="0" nextobjectid="{len(objs)+1}">\n{pblock}'
           ' <tileset firstgid="1" source="../tiles.tsx"/>\n'
           f'{layers_xml}'
           f' <objectgroup id="{len(layers)+1}" name="objects">\n'
           + ("\n".join(oxml) + "\n" if oxml else "") + ' </objectgroup>\n</map>\n')
    open(os.path.join(OUT, "maps", stem[mid] + ".tmx"), "w").write(xml)

for mid in chosen:
    write_tmx(mid)

# ── encounters.json (per-method tables) ─────────────────────────────
import json
def _aggregate(rows):
    agg = {}
    for sp, lo, hi in rows:
        nid = norm_species(sp)
        if SPECIES and nid not in SPECIES:
            continue
        if nid not in agg:
            agg[nid] = [lo, hi, 0]
        agg[nid][0] = min(agg[nid][0], lo)
        agg[nid][1] = max(agg[nid][1], hi)
        agg[nid][2] += 1
    return [{"species": k, "min": v[0], "max": v[1], "weight": v[2]}
            for k, v in agg.items()]

enc = {}
for mid in chosen:
    methods = enc_by_map.get(mid)
    if not methods:
        continue
    out = {}
    for method, rows in methods.items():
        slots = _aggregate(rows)
        if slots:
            out[method] = slots
    if out:
        enc[stem[mid]] = out
if enc:
    json.dump(enc, open(os.path.join(OUT, "encounters.json"), "w"), indent=1)

# ── game.json (no dex => full catalog allowed; keeps lint clean) ────
sx, sy = find_spawn(SEED)
game = {
    "engine_version": 2,
    "name": "Kanto (converted from JohtoBlaziken FRLG bootleg)",
    "start": {"map": stem[SEED], "tile": [sx, sy], "facing": "down"},
    "whiteout": {"map": stem[SEED], "facing": "down"},
    "starter": {"species": "charmander", "level": 5},
    "bag": {"potion": 5, "poke-ball": 10},
    "money": 3000,
    "flags": ["can_surf"],
    "settings": {"encounter_chance": 8, "daynight": "off"},
}
json.dump(game, open(os.path.join(OUT, "game.json"), "w"), indent=1)

print("\nemitted:", N, "atlas tiles,", len(chosen), "maps,",
      len(enc), "encounter tables")
print("OUT:", OUT)
