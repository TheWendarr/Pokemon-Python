"""Game entry point:  python -m pkmn.game.play  [--seed N]"""
from __future__ import annotations

import argparse

from .scene import Game
from .title import TitleScene


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--headless", action="store_true", help="dummy video (CI)")
    ap.add_argument("--save", default="save.json",
                    help="save file (loaded on start if it exists)")
    ap.add_argument("--game", default="game/assets",
                    help="game folder (manifest, maps, scripts, sprites)")
    ap.add_argument("--no-sprite-fetch", action="store_true",
                    help="never download sprites; use cache + blobs only")
    ap.add_argument("--mute", action="store_true", help="disable all audio")
    ap.add_argument("--controls", default="controls.json",
                    help="path to the key-bindings file (created on rebind)")
    ap.add_argument("--time", default=None,
                    help="day/night: auto|off|morning|day|evening|night|<hour>")
    ap.add_argument("--fullscreen", action="store_true",
                    help="run fullscreen at the display's native resolution")
    ap.add_argument("--fill", action="store_true",
                    help="fill the screen (sharp-bilinear) instead of the "
                         "default pixel-perfect integer scaling")
    args = ap.parse_args()
    from . import sprites
    sprites.FETCH_ENABLED = not args.no_sprite_fetch
    game = Game(headless=args.headless, seed=args.seed,
                save_path=args.save, game_dir=args.game,
                fullscreen=args.fullscreen, fill=args.fill, mute=args.mute,
                controls_path=args.controls, daynight=args.time)
    game.push(TitleScene(game))
    game.run()


if __name__ == "__main__":
    main()
