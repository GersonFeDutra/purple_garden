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

    def hit(self) -> int:
        self.free()
        return super().hit()

    def __init__(self, mask: int, angle: float, icon: Icon, name: str = 'Thorn',
                 coords: tuple[int, int] = VECTOR_ZERO) -> None:
        super().__init__(mask, name=name, coords=coords)
        self._velocity = Vector2(-self.speed, 0).rotate(angle)
        self._raw_pos = array(coords, float)

        self.sprite = Sprite(atlas=icon)
        shape: Shape = Shape()
        shape.rect = Rect(VECTOR_ZERO, icon.image.get_size() - array((10, 10)))
        icon.angle = self._velocity.normalize().angle_to(Vector2(*VECTOR_RIGHT))

        self.add_child(shape)
        self.add_child(self.sprite)


class Plant(Area, ABC):
    ATK_ANIM_SPEED: float = TextureSequence.DEFAULT_SPEED * 2.0
    animation_idle: str
    animation_back: str
    animation_attack: str
    process_state: Callable[[], None]
    animations: AtlasBook
    view_range: Area
    sprite: Sprite
    shape: Shape

    _was_looking_back: bool = False
    _is_flip_v: bool = False
    _grow_stages: int = 3
    _current_stage: int = 0
    _grow_progress: float = 0.0
    # Tempo de crescimento: usado para determinar o estágio
    # de crescimento e o tempo entre cargas de ataques.
    _animation_speed: float = .1
    _charge_frequency: float = .5
    _atk_anim_trigger: float
    _stage_triggers: list[float] = None
    _timer: Timer
    _health: int = 33

    def _process(self) -> None:
        self.process_state()
    
    def take_damage(self, value: int) -> None:
        self.set_health(self._health - value)
    
    def _growing(self) -> None:
        self._grow_progress += root.delta

        if self._grow_progress < self._stage_triggers[self._current_stage]:
            return

        self._current_stage += 1
        atlas: Icon = self.sprite.atlas
        atlas.set_texture(self._current_stage)

        if self._current_stage == self._grow_stages:
            self._grow_up()

    def _idling(self) -> None:
        self._grow_progress += root.delta

        if len(self.view_range._last_colliding_bodies) == 0:
            return

        # Vira em direção ao alvo mais próximo.
        target: Body = self._get_nearest_target()
        self._turn_to(target)

        if self._grow_progress < self._charge_frequency:
            return

        # Setup and play the shoot animation
        self._grow_progress = 0.0
        self.process_state = NONE_CALL
        sprite: Sprite = self.sprite

        if self._is_flip_v:
            timer: Timer = Timer(self._atk_anim_trigger / 60.0)
            self.process_state = self._back_shooting
            self._timer = timer
            timer.timeout.connect(timer, self, self._on_Timer_timeout, 1)
        else:
            sprite.connect(sprite.anim_event_triggered, self,
                           self._on_Sprite_anim_event_triggered, target)
            sprite.connect(sprite.animation_finished, self,
                           self._on_Sprite_animation_finished)
            self.animations.play_once(
                self.animation_attack, self.sprite, deque([self._atk_anim_trigger]))

    def _back_shooting(self) -> None:
        '''Estado em que a planta está de costas.'''
        if len(self.view_range._last_colliding_bodies) == 0:
            return

        target: Node = self._get_nearest_target()
        timer: Timer = self._timer
        self._turn_to(target)
        timer._process(root.delta)

        if not self._is_flip_v:
            sprite: Sprite = self.sprite
            timer = self._timer
            timer.timeout.disconnect(timer, self)
            self.process_state = self._idling

            if timer.elapsed_time < self._atk_anim_trigger:
                sprite.connect(sprite.anim_event_triggered, self,
                               self._on_Sprite_anim_event_triggered, target)
                self.animations.play_once(self.animation_attack, sprite, deque(
                    [self._atk_anim_trigger]), timer.elapsed_time)
            else:
                sprite.connect(sprite.animation_finished, self,
                               self._on_Sprite_animation_finished)

    def _grow_up(self) -> None:
        self.sprite.atlas = self.animations
        self.process_state = self._idling
        self._grow_progress = 0.0

        if self.animation_idle is not None:
            self.sprite.atlas.set_current_animation(self.animation_idle)
            self.sprite.atlas._current_sequence.speed = self._animation_speed

    def _get_nearest_target(self) -> Body:
        target: Body = self.view_range._last_colliding_bodies[0]
        target_distance: float = get_distance(
            self._global_position, target._global_position)

        # Toma como alvo o corpo mais próximo dentro da área.
        for body in self.view_range._last_colliding_bodies[1:]:
            distance: float = get_distance(
                self._global_position, body._global_position)

            if distance < target_distance:
                target = body

        return target

    def _turn_to(self, target: Node) -> tuple[bool, bool]:
        '''Vira em direção ano nó indicado.
        Retorna os estados de flipping resultantess `flip_h`, `flip_v`.'''
        atlas: AtlasBook = self.animations
        atlas.flip_h = target._global_position[X] < self._global_position[X]
        flip_v: bool = target._global_position[Y] < self._global_position[Y]
        self._is_flip_v = flip_v

        if self._was_looking_back != flip_v:
            atlas.set_current_animation(
                self.animation_back if flip_v else self.animation_idle)

    @abstractmethod
    def _shoot(self, target: HurtBox) -> None:
        '''Método virtual que deve ser sobrescrito (abstrato) para
        determinar um ataque à distância no alvo indicado.'''

    def _on_Sprite_anim_event_triggered(self, target: Node, time: float) -> None:
        self._shoot(target)
        self.sprite.disconnect(self.sprite.anim_event_triggered, self)

    def _on_Sprite_animation_finished(self) -> None:
        self.process_state = self._idling
        self.animations.set_current_animation(
            self.animation_back if self._is_flip_v else self.animation_idle)
        self.sprite.disconnect(self.sprite.animation_finished, self)

    def _on_Timer_timeout(self, shots: int, timer: Timer) -> None:
        timer.timeout.disconnect(timer, self)

        if shots == 1:
            self._shoot(self._get_nearest_target())
            self._timer = Timer(timer.target_time)
            self._timer.timeout.connect(
                self._timer, self, self._on_Timer_timeout, 2)
        elif shots == 2:
            self.process_state = self._idling

    def set_health(self, value: int) -> None:
        self._health = value

        if value <= 0:
            self.free()

    def __init__(self, color: Color, growing_color: Color, spritesheet: Surface,
                 spritesheet_data: dict[str, list[dict]], animation_idle: str,
                 animation_atk: str, animation_back: str, name: str = 'Plant',
                 coords: tuple[int, int] = VECTOR_ZERO) -> None:
        super().__init__(name=name, coords=coords, color=color)
        self.collision_layer = PhysicsLayers.PLAYER_BODY
        self.collision_mask = PhysicsLayers.NATIVES_VIEW | PhysicsLayers.NATIVES_HITBOX

        atlas: Icon = Icon(get_icon_sequence_slice(
            spritesheet, spritesheet_data, color, 0))
        atlas.set_texture(0)
        sprite: Sprite = Sprite(atlas=atlas)
        sprite.anchor = array(CENTER)
        self.sprite = sprite

        self.set_color(color)
        self.process_state = self._growing
        self.animation_idle = animation_idle
        self.animation_back = animation_back
        self.animation_attack = animation_atk
        animations: AtlasBook = AtlasBook()
        spritesheet_slice(spritesheet, spritesheet_data,
                          growing_color, animations)
        atk_anim_speed: float = Plant.ATK_ANIM_SPEED
        animations.animations[animation_atk].speed = atk_anim_speed
        self._atk_anim_trigger = 4.0  # Ativa no frame 4
        self.animations = animations

        # Set the view
        view_range: Area = Area('View', color=Color(145, 135, 25))
        view_range.collision_layer = PhysicsLayers.PLANTS_VIEW
        view_range.collision_mask = 0

        view: CircleShape = CircleShape(radius=atlas.rect.size[X] * 4)
        self.view_range = view_range
        view_range.add_child(view)

        # Set the shape
        # Note que a `Shape` foi usada de ponto âncora para posicionar os outros nós.
        shape: Shape = Shape(coords=array(atlas.image.get_size()) * 2)
        shape.rect = Rect(atlas.rect)
        self.shape = shape

        self.add_child(shape)
        shape.add_child(view_range)
        shape.add_child(sprite)

    health: int = property(lambda _self: _self.health, set_health)


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
                array(self.shape._global_position) - target._global_position))),
            Icon(self.thorn_textures), f'Thorn{self._spawns}', self.shape.position)
        self._spawns += 1
        self.add_child(thorn)

    def __init__(self, spritesheet: Surface, spritesheet_data: dict[str, list[dict]],
                 name: str = 'Rose', coords: tuple[int, int] = VECTOR_ZERO) -> None:
        super().__init__(
            Color('#bb2635'), Color('#fe5b59'), spritesheet, spritesheet_data,
            'rose_idle', 'rose_attack', 'rose_back', name=name, coords=coords)
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
                array(self.shape._global_position) - target._global_position))),
            Icon(self.thorn_textures), f'Thorn{self._spawns}', self.shape.position)
        thorn.strength = 3
        self._spawns += 1
        self.add_child(thorn)

    def __init__(self, spritesheet: Surface, spritesheet_data: dict[str, list[dict]],
                 name: str = 'Violet', coords: tuple[int, int] = VECTOR_ZERO) -> None:
        super().__init__(
            Color('#54189f'), Color('#d186df'), spritesheet, spritesheet_data,
            'violet_idle', 'violet_attack', 'violet_back', name=name, coords=coords)
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
