"""Gen 5 species sprites with a disk cache.

Real Black/White sprites are pulled from the PokeAPI sprites repository
(github.com/PokeAPI/sprites) — the same image files the REST API hands
out as its `sprites` URLs — and cached on disk by national dex number,
so each sprite is downloaded at most once. Every lookup after the first
is a pure disk read.

Network fetching is OPT-IN: `FETCH_ENABLED` is False by default so the
test suite and any embedding never touch the network unexpectedly. The
game's play entrypoint and `python -m pkmn.cli.sprites` turn it on.
Cache *hits* always work regardless of the flag, so a pre-warmed game
plays with real sprites with zero network access. On a cache miss with
fetching off (or a failed download), callers fall back to a placeholder,
so the game still runs fully offline.
"""
from __future__ import annotations

import os
import urllib.request

BW = ("https://raw.githubusercontent.com/PokeAPI/sprites/master/"
      "sprites/pokemon/versions/generation-v/black-white")

# Flipped on by play.py / the sprites CLI. Env var force-disables it.
FETCH_ENABLED = False


def _can_fetch() -> bool:
    return FETCH_ENABLED and os.environ.get("PKMN_NO_SPRITE_FETCH") != "1"


def default_cache_dir() -> str:
    return os.environ.get("PKMN_SPRITE_CACHE",
                          os.path.join(os.getcwd(), ".sprite_cache"))


def cache_path(dex: int, *, back: bool = False,
               cache_dir: str | None = None) -> str:
    base = cache_dir or default_cache_dir()
    return os.path.join(base, "gen5", "back" if back else "front",
                        f"{dex}.png")


def sprite_path(dex: int, *, back: bool = False,
                cache_dir: str | None = None, timeout: float = 15) -> str | None:
    """Local PNG path for a sprite, downloading + caching on first need.

    Returns None if the sprite isn't cached and can't be fetched (network
    off, offline, or the species has no Gen 5 sprite)."""
    if not dex:
        return None
    path = cache_path(dex, back=back, cache_dir=cache_dir)
    if os.path.exists(path):
        return path
    if not _can_fetch():
        return None
    url = f"{BW}/{'back/' if back else ''}{int(dex)}.png"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            data = resp.read()
    except Exception:
        return None
    if not data.startswith(b"\x89PNG"):
        return None  # 404s come back as an HTML/text body, not a PNG
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, path)
    return path
