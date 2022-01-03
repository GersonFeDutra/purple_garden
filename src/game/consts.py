from enum import IntEnum

# Window
# BASE_SIZE: tuple[int, int] = 640, 360
BASE_SIZE: tuple[int, int] = 320, 180
TITLE: str = "Hello PyGame World!"

# Game Constants
CELL_SIZE: int = 32
CELL: tuple = CELL_SIZE, CELL_SIZE

SPRITES_SCALE: tuple[float, float] = 4., 4.

# Sprites
SPRITE_SIZE: tuple[int, int] = 32, 32

# Groups
ENEMY_GROUP: str = 'enemy'
PLAYER_GROUP: str = 'player'


class PhysicsLayers(IntEnum):
    NATIVES_BODIES: int = 1
    PLAYER_HITBOX: int = 2
    PLAYER_BODY: int = 4
    PLANTS_VIEW: int = 8
    NATIVES_VIEW: int = 16
