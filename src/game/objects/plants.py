from src.core.nodes import *
from ..utils import get_icon_sequence_slice, spritesheet_slice


class Plant(Area):
    animation_idle: str
    animation_attack: str
    view_range: Area
    animations: AtlasBook
    grow: Callable
    sprite: Sprite

    _grow_stages: int = 3
    _current_stage: int = 0
    _grow_progress: float = 0.0
    _animation_speed: float = 0.1
    _stage_triggers: list[float] = None

    def _process(self, delta: float) -> None:
        self.grow()

    def _grow(self) -> None:
        self._grow_progress += root.delta_persec

        if self._grow_progress >= self._stage_triggers[self._current_stage]:
            self._current_stage += 1
            atlas: Icon = self.sprite.atlas
            atlas.set_texture(self._current_stage)

            if self._current_stage == self._grow_stages:
                self._grow_up()
                self.grow = NONE_CALL

    def _grow_up(self) -> None:
        self.sprite.atlas = self.animations

        if self.animation_idle is not None:
            self.sprite.atlas.set_current_animation(self.animation_idle)
            self.sprite.atlas._current_sequence.speed = self._animation_speed

    def __init__(self, color: Color, growing_color: Color, spritesheet: Surface,
                 spritesheet_data: dict[str, list[dict]], name: str = 'Plant',
                 coords: tuple[int, int] = VECTOR_ZERO, animation_idle: str = None,
                 animation_atk: str = None) -> None:
        super().__init__(name=name, coords=coords, color=color)
        atlas: Icon = Icon(get_icon_sequence_slice(
            spritesheet, spritesheet_data, color, 0))
        atlas.set_texture(0)
        sprite: Sprite = Sprite(atlas=atlas)
        sprite.anchor = array(TOP_LEFT)
        self.sprite = sprite

        self.grow = self._grow
        self.color = color
        self.animation_idle = animation_idle
        self.animation_attack = animation_atk
        self.animations = AtlasBook()
        spritesheet_slice(spritesheet, spritesheet_data,
                          growing_color, self.animations)

        # Set the view
        view_range: Area = Area('View', color=Color(145, 135, 25))
        # TODO -> Circle collision shape
        view_range.collision_layer = 0
        view_range.collision_mask = 0
        _rect_size: ndarray = array(atlas.rect.size)
        _rect_offset: ndarray = _rect_size * 2
        view: Shape = Shape(coords=_rect_offset)
        view.rect = Rect(_rect_offset, _rect_size * 2)
        self.view_range = view_range
        view_range.add_child(view, 0)

        # Set the shape
        shape: Shape = Shape()
        shape.anchor = array(TOP_LEFT)
        shape.rect = Rect(atlas.rect)

        self.add_child(view_range)
        self.add_child(shape)
        self.add_child(sprite)


class Rose(Plant):
    _DEFAULT_TIMES: tuple[float] = (
        1.0, 2.0, 3.0) if IS_DEBUG_ENABLED else (10.0, 20.0, 30.0)

    def __init__(self, spritesheet: Surface, spritesheet_data: dict[str, list[dict]],
                 name: str = 'Rose', coords: tuple[int, int] = VECTOR_ZERO) -> None:
        super().__init__(
            Color('#bb2635'), Color('#fe5b59'), spritesheet, spritesheet_data,
            name=name, coords=coords, animation_idle='rose_idle', animation_atk='rose_attack')
        self._stage_triggers = self._DEFAULT_TIMES


class Violet(Plant):
    _DEFAULT_TIMES: tuple[float] = (
        15., 30., 45.) if IS_DEBUG_ENABLED else (15., 30., 45.)

    def __init__(self, spritesheet: Surface, spritesheet_data: dict[str, list[dict]],
                 name: str = 'Violet', coords: tuple[int, int] = VECTOR_ZERO) -> None:
        super().__init__(
            Color('#54189f'), Color('#d186df'), spritesheet, spritesheet_data,
            name=name, coords=coords, animation_idle='violet_idle', animation_atk='violet_attack')
        self._stage_triggers = self._DEFAULT_TIMES


class OxTree(Sprite):

    def __init__(self, spritesheet: Surface, spritesheet_data: dict[str, list[dict]],
                 name: str = 'OxTree', coords: tuple[int, int] = VECTOR_ZERO) -> None:
        super().__init__(name=name, coords=coords, atlas=Icon(get_icon_sequence_slice(
            spritesheet, spritesheet_data, Color('#159a42'))))
        self.anchor = array(TOP_LEFT)
