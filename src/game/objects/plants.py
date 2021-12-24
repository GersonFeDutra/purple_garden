from src.core.nodes import *
from ..utils import get_icon_sequence_slice, spritesheet_slice


class Plant(Sprite):
    animation_idle: str
    animation_attack: str
    view_range: Body
    animations: AtlasBook
    grow: Callable

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
            atlas: Icon = self.atlas
            atlas.set_texture(self._current_stage)
            
            if self._current_stage == self._grow_stages:
                self._grow_up()
                self.grow = NONE_CALL

    def _grow_up(self) -> None:
        self.atlas = self.animations

        if self.animation_idle is not None:
            self.atlas.set_current_animation(self.animation_idle)
            self.atlas._current_sequence.speed = self._animation_speed

    def __init__(self, color: Color, growing_color: Color, spritesheet: Surface,
                 spritesheet_data: dict[str, list[dict]], name: str = 'Plant',
                 coords: tuple[int, int] = VECTOR_ZERO, atlas: BaseAtlas = None,
                 animation_idle: str = None, animation_atk: str = None) -> None:
        atlas: Icon = Icon(get_icon_sequence_slice(
            spritesheet, spritesheet_data, color, 0))
        atlas.set_texture(0)
        super().__init__(name=name, coords=coords, atlas=atlas)
        self.anchor = array(TOP_LEFT)
        self.grow = self._grow
        self.color = color
        self.animation_idle = animation_idle
        self.animation_attack = animation_atk
        self.animations = AtlasBook()
        spritesheet_slice(spritesheet, spritesheet_data,
                          growing_color, self.animations)

        self.view_range = Body('View')
        self.add_child(self.view_range)


class Rose(Plant):
    _DEFAULT_TIMES: tuple[float] = (1.0, 2.0, 3.0) if IS_DEBUG_ENABLED else (10.0, 20.0, 30.0)

    def __init__(self, spritesheet: Surface, spritesheet_data: dict[str, list[dict]],
                 name: str = 'Rose', coords: tuple[int, int] = VECTOR_ZERO,
                 atlas: BaseAtlas = None) -> None:
        super().__init__(Color('#bb2635'), Color('#fe5b59'), spritesheet, spritesheet_data, name=name, coords=coords,
                         atlas=atlas, animation_idle='rose_idle', animation_atk='rose_attack')
        self._stage_triggers = self._DEFAULT_TIMES


class Violet(Plant):
    _DEFAULT_TIMES: tuple[float] = (15., 30., 45.) if IS_DEBUG_ENABLED else (15., 30., 45.)

    def __init__(self, spritesheet: Surface, spritesheet_data: dict[str, list[dict]],
                 name: str = 'Violet', coords: tuple[int, int] = VECTOR_ZERO,
                 atlas: BaseAtlas = None) -> None:
        super().__init__(Color('#54189f'), Color('#d186df'), spritesheet, spritesheet_data, name=name, coords=coords,
                         atlas=atlas, animation_idle='violet_idle', animation_atk='violet_attack')
        self._stage_triggers = self._DEFAULT_TIMES


class OxTree(Sprite):

    def __init__(self, spritesheet: Surface, spritesheet_data: dict[str, list[dict]], name: str = 'OxTree',
                 coords: tuple[int, int] = VECTOR_ZERO) -> None:
        super().__init__(name=name, coords=coords, atlas=Icon(get_icon_sequence_slice(
            spritesheet, spritesheet_data, Color('#159a42'))))
        self.anchor = array(TOP_LEFT)
