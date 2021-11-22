from random import randrange
from src.core.nodes import *
from ..consts import *


class Clouds(Node):
    '''Objeto único de jogo. Controla a aparição de elementos visuais decorativos.'''
    spritesheet: Surface

    def rearrange(self) -> Node:

        for child in self._children_index:
            child.position = randrange(50, 200, 100), randrange(50, 200, 50)

    def _spawn_clouds(self) -> None:
        global SPRITE_SIZE, SPRITES_SCALE

        for i in range(1, 5):
            cloud: Sprite = Sprite(name=f'Cloud{i}', coords=(
                randrange(50, 200, 100), randrange(50, 200, 50)))
            cloud.atlas.add_spritesheet(self.spritesheet, coords=(
                SPRITE_SIZE[0] * 7, 0), sprite_size=SPRITE_SIZE)
            cloud.scale = array(SPRITES_SCALE)
            self.add_child(cloud)

    def __init__(self, spritesheet: Surface, name: str = 'Clouds',
                 coords: tuple[int, int] = VECTOR_ZERO) -> None:
        super().__init__(name=name, coords=coords)

        self.spritesheet = spritesheet
        self._spawn_clouds()


class Floor(Node):
    '''Objeto único de jogo. Decorativo.'''
    spritesheet: Surface

    def _spawn_floor(self) -> None:
        global root, SPRITE_SIZE, SPRITES_SCALE

        for i in range(root._screen_width // CELL_SIZE):
            piece: Sprite = Sprite(name=f'Piece{i}', coords=array(
                [(CELL_SIZE * SPRITES_SCALE[0]) * i - root._screen_width,
                    root._screen_height - CELL_SIZE]))
            piece.atlas.add_spritesheet(self.spritesheet, coords=(
                SPRITE_SIZE[0] * 6, 0), sprite_size=SPRITE_SIZE)
            piece.scale = array(SPRITES_SCALE)
            self.add_child(piece)

    def __init__(self, spritesheet: Surface, name: str = 'Floor',
                 coords: tuple[int, int] = VECTOR_ZERO) -> None:
        super().__init__(name=name, coords=coords)

        self.spritesheet = spritesheet
        self.anchor = array(VECTOR_ZERO, dtype=float)
        self._spawn_floor()


class BackGround(Node):
    '''Objeto único de jogo. Controla o plano de fundo na tela.'''
    clouds: Clouds
    scroll_speed: int

    def speed_up(self) -> None:
        self.scroll_speed += 1

    def _process(self, delta: float) -> None:
        global root, SPRITES_SCALE

        self.position[X] = self.position[X] - self.scroll_speed

        if self.position[X] < -(root._screen_width // 2):
            self.position[X] = root._screen_width
            self.clouds.rearrange()

    def __init__(self, spritesheet: Surface, scroll_speed: int = 1, name: str = 'BackGround',
                 coords: tuple[int, int] = VECTOR_ZERO) -> None:
        super().__init__(name=name, coords=coords)

        self.scroll_speed = scroll_speed
        self.anchor = array(VECTOR_ZERO, dtype=float)
        self.clouds = Clouds(spritesheet, coords=(0, 50))
        self.add_child(Floor(spritesheet))
        self.add_child(self.clouds)
