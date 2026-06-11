"""Client constants."""
TILE = 16
LOGICAL_W, LOGICAL_H = 256, 192      # GBA-ish logical resolution
SCALE = 3                            # window = logical * SCALE
FPS = 60
WALK_SPEED = 2                       # px per frame (16px tile / 8 frames)
TURN_FRAMES = 5                      # tap-to-turn grace before stepping
ENCOUNTER_CHANCE = 8                 # 1-in-N per tall-grass step
ASSET_DIR = "game/assets"
DATA_DIR = "game/data"

# input names
A, B, UP, DOWN, LEFT, RIGHT = "a", "b", "up", "down", "left", "right"
DIRS = {UP: (0, -1), DOWN: (0, 1), LEFT: (-1, 0), RIGHT: (1, 0)}
