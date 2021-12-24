from pygame.mixer import Sound
from random import randint
from src.core.nodes import *
from ..consts import *
from ..utils import Steering, spritesheet_slice
from .plants import Plant, Rose, Violet


class Char(KinematicBody):
    speed: float = 10.0
    sprite: Sprite
    _velocity: Vector2
    _animation_speed: float = 0.1

    def __init__(self, spritesheet: Surface, spritesheet_data: dict[str, list[dict]],
                 name: str = 'Char', coords: tuple[int, int] = VECTOR_ZERO,
                 color: Color = Color('#0d89c6'), animation: str = None) -> None:
        super().__init__(name=name, coords=coords, color=color)
        self._velocity = Vector2(*VECTOR_ZERO)

        # Set the Sprite
        atlas: AtlasBook = AtlasBook()
        self.sprite = Sprite(atlas=atlas)
        spritesheet_slice(spritesheet, spritesheet_data, self.color, atlas)
        self.add_child(self.sprite)

        if animation is not None:
            atlas.set_current_animation(animation)
            atlas._current_sequence.speed = self._animation_speed


class Player(Char):
    '''Objeto único de jogo. É o ator/ personagem principal controlado pelo jogador.'''
    JUMP: str = "jump"
    GRAVITY: float = 0.1

    points_changed: Entity.Signal
    scored: Entity.Signal
    died: Entity.Signal

    was_collided: bool = False
    death_sfx: Sound = None
    limits: Shape
    hand_item: type[Plant] = Rose
    hand_items: list[type[Plant]] = [Rose, Violet]
    _start_position: tuple[int, int]

    def _physics_process(self, delta: float) -> None:
        self.sprite.atlas.set_flip(int(self._velocity[X] < 0))
        self.move_and_collide(self._velocity * self.speed)
        super()._physics_process(delta)

    def _input(self) -> None:
        self._velocity = Input.get_input_strength()
        super()._input()

    # def _on_Body_collided(self, body: Body) -> None:
    #     global root, ENEMY_GROUP
    #
    #     if self.was_collided:
    #         return
    #
    #     if root.is_on_group(body, ENEMY_GROUP):
    #         root.pause_tree()
    #         self.sprite.atlas.is_paused = True
    #         self.death_sfx.play()
    #         self.was_collided = True
    #         self.died.emit()

    def _on_Game_resumed(self) -> None:
        self.was_collided = False
        self.position = self._start_position
        self.sprite.atlas.is_paused = False
        self.points = 0

    def set_points(self, value) -> None:
        self._points = value
        self.points_changed.emit(f'Points: {value}')

    def get_points(self) -> None:
        return self._points

    def __init__(self, limits: Shape, spritesheet: Surface, spritesheet_data: dict[str, list[dict]],
                 death_sfx: Sound, coords: tuple[int, int] = VECTOR_ZERO) -> None:
        global root, input, root, SPRITE_SIZE, SPRITES_SCALE, PLAYER_GROUP
        super().__init__(spritesheet, spritesheet_data,
                         name='Char', coords=coords, color=Color('#6acd5bff'), animation='char_idle')

        # Set Sprite Group
        self.sprite.group = PLAYER_GROUP
        # Set Scene Tree Group
        root.add_to_group(self, PLAYER_GROUP)

        self.death_sfx = death_sfx
        self.scale = array(SPRITES_SCALE)
        self._points: int = 0
        self._start_position = coords

        self.limits = limits

        # TODO -> Shoot
        # input.register_event(self, KEYDOWN, K_SPACE, self.JUMP)

        #self.collided.connect(self, self, self._on_Body_collided)

        # Set the Shape
        shape: Shape = Shape()
        # rect: Rect = Rect(sprite.atlas.rect)
        rect: Rect = Rect(VECTOR_ZERO, array(VECTOR_ONE) * 16)
        # rect.size -= array([16, 16])
        shape.rect = rect
        self.add_child(shape, 0)

        # Signals
        self.points_changed = Entity.Signal(self, 'points_changed')
        self.scored = Entity.Signal(self, 'scored')
        self.died = Entity.Signal(self, 'died')

        if IS_DEV_MODE_ENABLED:
            self.speed += 1.0

    points: property = property(get_points, set_points)


class Native(Char):
    atk: int = 1
    hp: int
    final_target_pos: tuple[int, int]
    move: Callable[[float], None]
    _is_flipped: bool = False

    def _physics_process(self, delta: float) -> None:
        self.move(delta)

    def _follow(self, delta: float) -> None:
        self._velocity = Steering.follow(Vector2(
            *self._velocity), Vector2(*self._global_position), Vector2(*self.final_target_pos))
        self.move_and_collide(self._velocity * self.speed)
        super()._physics_process(delta)

    def _move(self, delta: float) -> None:
        self._velocity = Steering.follow(Vector2(
            *self._velocity), Vector2(*self._global_position), Vector2(*self.final_target_pos))
        is_flipped: bool = self._velocity.x > 0.0

        if self._is_flipped != is_flipped:
            self.sprite.atlas.flip_h = is_flipped
            self._is_flipped = is_flipped

        self.move_and_collide(self._velocity * self.speed)
        super()._physics_process(delta)

    def set_target(self, value: Node) -> None:
        self._current_target = value
        self.move = self._move if value is None else self._follow

    def _on_Body_collided(self, body) -> None:

        if body.name == 'Ship':
            self.move = NONE_CALL
            self.disconnect(self.collided, self)

    def __init__(self, final_target_pos: tuple[int, int], max_hp_range: tuple[int, int],
                 spritesheet: Surface, spritesheet_data: dict[str, list[dict]],
                 name: str = 'Native', coords: tuple[int, int] = VECTOR_ZERO,
                 color: Color = Color('#f3ce52'), animation: str = None) -> None:
        super().__init__(spritesheet, spritesheet_data, name=name,
                         coords=coords, color=color, animation=animation)
        self.hp = randint(*max_hp_range)
        self.final_target_pos = final_target_pos
        self.move = self._move
        self._current_target: Node = None
        
        # Set `Shape` child
        shape: Shape = Shape()
        shape.set_rect(Rect(VECTOR_ZERO, self.sprite.atlas.base_size))
        self.add_child(shape, 0)
        
        self.connect(self.collided, self, self._on_Body_collided)

    current_target: Node = property(lambda self: self.target, set_target)


class Hermiga(Native):

    def __init__(self, final_target_pos: tuple[int, int], spritesheet: Surface,
                 spritesheet_data: dict[str, list[dict]], name: str = 'Hermiga',
                 coords: tuple[int, int] = VECTOR_ZERO, max_hp_range: tuple[int, int] = (3, 6)) -> None:
        super().__init__(final_target_pos, max_hp_range, spritesheet, spritesheet_data, name=name,
                         coords=coords, color=Color('#f3ce52'), animation='hermiga_walk')
        self.atk = 3


class Mosca(Native):

    def __init__(self, final_target_pos: tuple[int, int], spritesheet: Surface,
                 spritesheet_data: dict[str, list[dict]], name: str = 'Mosca',
                 coords: tuple[int, int] = VECTOR_ZERO, max_hp_range: tuple[int, int] = (3, 5)) -> None:
        super().__init__(final_target_pos, max_hp_range, spritesheet, spritesheet_data, name=name,
                         coords=coords, color=Color('#57b9f2'), animation='mosca_fly')
        self.atk = 2


class Lunar(Native):

    def __init__(self, final_target_pos: tuple[int, int], spritesheet: Surface,
                 spritesheet_data: dict[str, list[dict]], name: str = 'Lunar',
                 coords: tuple[int, int] = VECTOR_ZERO, max_hp_range: tuple[int, int] = (3, 4)) -> None:
        super().__init__(final_target_pos, max_hp_range, spritesheet, spritesheet_data, name=name,
                         coords=coords, color=Color('#8e6b2b'), animation='lunar_dig')
        self.atk = 1
