from src.core.nodes import *
from ..consts import PhysicsLayers
from ..utils import HitBox, HurtBox, get_distance, get_icon_sequence_slice, spritesheet_slice


class Thorn(HitBox):
    '''Espinhos disparados por uma planta.'''
    speed: float = 10.0
    sprite: Sprite
    _velocity: ndarray
    _raw_pos: ndarray
    _map_limits: tuple[int, int] = 0, 0

    def _enter_tree(self) -> None:
        super()._enter_tree()

        if not hasattr(root.current_scene, 'map_limits'):
            push_warning('Current scene has no `map_limits` attribute.')
            return

        self._map_limits = root.current_scene.map_limits

    def _process(self) -> None:
        self._raw_pos += self._velocity
        self.position = array(self._raw_pos, int)

        for i in (X, Y):
            if 0 > self._global_position[i] or \
                    self._global_position[i] > self._map_limits[i]:
                self.free()
                return

    def __init__(self, mask: int, angle: float, icon: Icon, name: str = 'Thorn',
                 coords: tuple[int, int] = VECTOR_ZERO) -> None:
        super().__init__(mask, name=name, coords=coords)
        self._velocity = Vector2(-self.speed, 0).rotate(angle)
        self._raw_pos = array(coords, float)

        self.sprite = Sprite(atlas=icon)
        shape: Shape = Shape()
        shape.rect = Rect(VECTOR_ZERO, self.sprite.atlas.image.get_size())

        self.add_child(shape)
        self.add_child(self.sprite)


class Plant(Area, ABC):
    animation_idle: str
    animation_attack: str
    process_state: Callable[[], None]
    view_range: Area
    animations: AtlasBook
    sprite: Sprite

    _grow_stages: int = 3
    _current_stage: int = 0
    _grow_progress: float = 0.0
    # Tempo de crescimento: usado para determinar o estágio
    # de crescimento e o tempo entre cargas de ataques.
    _animation_speed: float = .1
    _charge_frequency: float = .5
    _stage_triggers: list[float] = None
    _spawn_position: ndarray = None

    def _enter_tree(self) -> None:
        super()._enter_tree()
        self._spawn_position = array(
            self.sprite.get_cell()) * self._global_scale // 2
        self._show_hint()

    def _process(self) -> None:
        self.process_state()

    def _on_Range_Area_entered(self, _area: Area) -> None:
        self.process_state = self._attack
        self.view_range.disconnect(self.view_range.body_entered, self)

    def _grow(self) -> None:
        self._grow_progress += root.delta

        if self._grow_progress < self._stage_triggers[self._current_stage]:
            return

        self._current_stage += 1
        atlas: Icon = self.sprite.atlas
        atlas.set_texture(self._current_stage)

        if self._current_stage == self._grow_stages:
            self._grow_up()

    def _attack(self) -> None:
        self._grow_progress += root.delta

        if self._grow_progress < self._charge_frequency:
            return

        if len(self.view_range._last_colliding_bodies) == 0:
            self.process_state = NONE_CALL
            self.view_range.connect(
                self.view_range.body_entered, self, self._on_Range_Area_entered)
            return

        self._grow_progress = 0.0
        target: Body = self.view_range._last_colliding_bodies[0]
        target_distance: float = get_distance(
            self._global_position, target._global_position)

        # Toma como alvo o corpo mais próximo dentro da área.
        for body in self.view_range._last_colliding_bodies[1:]:
            distance: float = get_distance(
                self._global_position, body._global_position)

            if distance < target_distance:
                target = body

        self._shoot(target)

    def _grow_up(self) -> None:
        self.sprite.atlas = self.animations
        self.process_state = self._attack
        self._grow_progress = 0.0

        if self.animation_idle is not None:
            self.sprite.atlas.set_current_animation(self.animation_idle)
            self.sprite.atlas._current_sequence.speed = self._animation_speed

    @abstractmethod
    def _shoot(self, target: HurtBox) -> None:
        '''Método virtual que deve ser sobrescrito (abstrato) para
        determinar um ataque à distância no alvo indicado.'''

    @Node.debug()
    def _show_hint(self) -> None:
        self.add_child(Node('DebugHint', self._spawn_position))

    def __init__(self, color: Color, growing_color: Color, spritesheet: Surface,
                 spritesheet_data: dict[str, list[dict]], name: str = 'Plant',
                 coords: tuple[int, int] = VECTOR_ZERO, animation_idle: str = None,
                 animation_atk: str = None) -> None:
        super().__init__(name=name, coords=coords, color=color)
        self.collision_layer = PhysicsLayers.PLAYER_BODY
        self.collision_mask = 0

        atlas: Icon = Icon(get_icon_sequence_slice(
            spritesheet, spritesheet_data, color, 0))
        atlas.set_texture(0)
        sprite: Sprite = Sprite(atlas=atlas)
        sprite.anchor = array(TOP_LEFT)
        self.sprite = sprite

        self.process_state = self._grow
        self.color = color
        self.animation_idle = animation_idle
        self.animation_attack = animation_atk
        self.animations = AtlasBook()
        spritesheet_slice(spritesheet, spritesheet_data,
                          growing_color, self.animations)

        # Set the view
        view_range: Area = Area('View', color=Color(145, 135, 25))
        # TODO -> Circle collision shape
        view_range.collision_layer = PhysicsLayers.PLANTS_VIEW
        view_range.collision_mask = 0

        _rect_size: ndarray = array(atlas.rect.size)
        _rect_offset: ndarray = _rect_size * 2

        view: CircleShape = CircleShape(
            coords=_rect_offset, radius=_rect_size[X] * 4)
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
    THORN_COLOR: Color = Color('#4a0a0a')
    _DEFAULT_TIMES: tuple[float] = (
        1.0, 2.0, 3.0) if IS_DEBUG_ENABLED else (10.0, 20.0, 30.0)

    thorn_textures: list[Surface]
    _spawns: int = 0

    def _shoot(self, target: HurtBox) -> None:
        thorn: Thorn = Thorn(
            PhysicsLayers.NATIVES_BODIES,
            Vector2(*VECTOR_ZERO).angle_to(Vector2(*(
                self._spawn_position + self._global_position - target._global_position))),
            Icon(self.thorn_textures), name=f'Thorn{self._spawns}')
        self._spawns += 1
        self.add_child(thorn)

    def __init__(self, spritesheet: Surface, spritesheet_data: dict[str, list[dict]],
                 name: str = 'Rose', coords: tuple[int, int] = VECTOR_ZERO) -> None:
        super().__init__(
            Color('#bb2635'), Color('#fe5b59'), spritesheet, spritesheet_data, name=name,
            coords=coords, animation_idle='rose_idle', animation_atk='rose_attack')
        self._stage_triggers = self._DEFAULT_TIMES
        self.thorn_textures = get_icon_sequence_slice(
            spritesheet, spritesheet_data, Rose.THORN_COLOR)


class Violet(Plant):
    THORN_COLOR: Color = Color('#b1f2ff')
    _DEFAULT_TIMES: tuple[float] = (15., 30., 45.) if \
        IS_DEBUG_ENABLED else (15., 30., 45.)

    thorn_textures: list[Surface]
    _spawns: int = 0

    def _shoot(self, target: HurtBox) -> None:
        thorn: Thorn = Thorn(
            PhysicsLayers.NATIVES_BODIES,
            Vector2(*VECTOR_ZERO).angle_to(Vector2(*(
                self._spawn_position + self._global_position - target._global_position))),
            Icon(self.thorn_textures), name=f'Thorn{self._spawns}')
        thorn.strength = 3
        self._spawns += 1
        self.add_child(thorn)

    def __init__(self, spritesheet: Surface, spritesheet_data: dict[str, list[dict]],
                 map_limits: tuple[int, int], name: str = 'Violet',
                 coords: tuple[int, int] = VECTOR_ZERO) -> None:
        super().__init__(
            Color('#54189f'), Color('#d186df'), spritesheet, spritesheet_data, name=name,
            coords=coords, animation_idle='violet_idle', animation_atk='violet_attack')
        self._stage_triggers = self._DEFAULT_TIMES
        self.thorn_textures = get_icon_sequence_slice(
            spritesheet, spritesheet_data, Violet.THORN_COLOR
        )


class OxTree(Sprite):

    def __init__(self, spritesheet: Surface, spritesheet_data: dict[str, list[dict]],
                 name: str = 'OxTree', coords: tuple[int, int] = VECTOR_ZERO) -> None:
        super().__init__(name=name, coords=coords, atlas=Icon(get_icon_sequence_slice(
            spritesheet, spritesheet_data, Color('#159a42'))))
        self.anchor = array(TOP_LEFT)
