"""Client constants.

The game renders at a high *native* resolution: a base 256x192 design
grid multiplied by SCALE. At SCALE=4 the canvas is 1024x768 with 64px
tiles, so text and sprites are rendered with enough real pixels to stay
crisp, and the final scale to the window is gentle (often 1:1). The
gameplay viewport is unchanged (16x12 tiles); only the pixel density is.
All on-screen geometry derives from SCALE, TILE, or LOGICAL_*.
"""
SCALE = 4                            # native render scale (base 16px -> 64px)
BASE_TILE = 16                       # grid tiles & sprites are authored on (disk)
TILE = BASE_TILE * SCALE             # 64: on-screen tile size (art upscaled at load)
LOGICAL_W, LOGICAL_H = 256 * SCALE, 192 * SCALE   # 1024 x 768 native canvas
WINDOW_W, WINDOW_H = 1920, 1080      # default output resolution (1080p)
FPS = 60
WALK_SPEED = 2 * SCALE               # 8 px/frame -> still 8 frames per tile
TURN_FRAMES = 5                      # tap-to-turn grace before stepping
ENCOUNTER_CHANCE = 8                 # 1-in-N per tall-grass step
ASSET_DIR = "game/assets"
DATA_DIR = "game/data"

# input names
A, B, UP, DOWN, LEFT, RIGHT = "a", "b", "up", "down", "left", "right"
START = "start"
SPRITE_PX = 96 * 2                   # 192: Gen 5 battlers upscaled, never shrunk
DIRS = {UP: (0, -1), DOWN: (0, 1), LEFT: (-1, 0), RIGHT: (1, 0)}
