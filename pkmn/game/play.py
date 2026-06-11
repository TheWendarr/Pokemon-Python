"""Game entry point:  python -m pkmn.game.play  [--seed N]"""
from __future__ import annotations

import argparse

from .overworld import OverworldScene
from .scene import Game


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--headless", action="store_true", help="dummy video (CI)")
    args = ap.parse_args()
    game = Game(headless=args.headless, seed=args.seed)
    game.push(OverworldScene(game))
    game.run()


if __name__ == "__main__":
    main()
