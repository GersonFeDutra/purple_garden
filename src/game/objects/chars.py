from pygame.mixer import Sound
from random import randint
from src.core.nodes import *
from ..consts import *
from ..utils import HurtBox, Steering, get_distance, spritesheet_slice
from .plants import Plant, Rose, Violet
from .props import Ship


class Char(KinematicBody):
    speed: float = 10.0
    sprite: Sprite
    _velocity: Vector2
    _animation_speed: float = TextureSequence.DEFAULT_SPEED

    def __init__(self, spritesheet: Surface, spritesheet_data: dict[str, list[dict]],
                 name: str = 'Char', coords: tuple[int, int] = VECTOR_ZERO,
                 color: Color = Color('#0d89c6'), animation: str = None) -> None:
        super().__init__(name=name, coords=coords, color=color)
        # Desabilita as máscaras de colisão por padrão (apenas recebe colisão).
        self.collision_mask = 0
        self._velocity = Vector2(*VECTOR_ZERO)

        # Set the Sprite
        atlas: AtlasBook = AtlasBook()
        self.sprite = Sprite(atlas=atlas)
        spritesheet_slice(spritesheet, spritesheet_data, self._color, atlas)
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
    hand_item: type[Plant] = Rose
    hand_items: list[type[Plant]] = [Rose, Violet]
    _start_position: tuple[int, int]

    max_o2: int = 100
    o2: int = 50

    def _physics_process(self, factor: float) -> None:
        self.sprite.atlas.set_flip(int(self._velocity[X] < 0))
        self.move_and_collide(self._velocity * self.speed)
        super()._physics_process(factor)

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
        self._points = 0

    def set_points(self, value) -> None:
        self._points = value
        self.points_changed.emit(f'Points: {value}')

    def take_damage(self, value: int) -> None:
        self.o2 -= value

    def __init__(self, spritesheet: Surface, spritesheet_data: dict[str, list[dict]],
                 death_sfx: Sound, coords: tuple[int, int] = VECTOR_ZERO) -> None:
        global root, input, root, SPRITE_SIZE, SPRITES_SCALE, PLAYER_GROUP
        super().__init__(spritesheet, spritesheet_data,
                         name='Char', coords=coords, color=Color('#6acd5bff'), animation='char_idle')
        # TODO -> Fazer a colisão do jogador com o mundo
        self.collision_layer = 0

        # Set Sprite Group
        self.sprite.group = PLAYER_GROUP
        # Set Scene Tree Group
        root.add_to_group(self, PLAYER_GROUP)

        self.death_sfx = death_sfx
        self._points: int = 0
        self._start_position = coords

        # TODO -> Shoot
        # input.register_event(self, KEYDOWN, K_SPACE, self.JUMP)

        #self.body_entered.connect(self, self, self._on_Body_collided)

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

        self.points: int = property(
            lambda _self: _self._points, self.set_points)


class Native(Char):
    class States(IntEnum):
        WALK: int = 0
        ATK_CHARGE: int = 1
        FINISHING_ATK: int = 2
        TAKING_DAMAGE: int = 4

    atk: int
    final_target_pos: tuple[int, int]
    target_pos: tuple[int, int]
    animation_walk: str
    animation_attack: str
    animation_damage: str
    move: Callable[[float], None]
    animations: AtlasBook
    target: Node = None
    atk_box: Area
    view_range: Area

    _damage_anim_duration: float
    _is_flipped: bool = False
    _state: int = States.WALK
    _last_state: int = _state
    _timer: Timer = None
    _knock_timer: Timer = None
    _cached_move: Callable[[float], None]

    def _draw(self, target_pos: tuple[int, int], target_scale: tuple[float, float], offset: tuple[int, int]) -> None:
        return super()._draw(target_pos, target_scale, offset)

    def _physics_process(self, factor: float) -> None:
        self.move(factor)

    def _follow(self, factor: float) -> None:
        self._go_to(factor, *self.target_pos)

    def _move(self, factor: float) -> None:
        self._go_to(factor, *self.final_target_pos)

    def _go_to(self, factor: float, x: int, y: int) -> None:
        self._velocity = Steering.follow(Vector2(
            *self._velocity), Vector2(*self._global_position), Vector2(x, y))
        is_flipped: bool = self._velocity.x > 0.0

        if self._is_flipped != is_flipped:
            self.sprite.atlas.flip_h = is_flipped
            self._is_flipped = is_flipped

        self.move_and_collide(self._velocity * self.speed)
        super()._physics_process(factor)

    def _knockback(self, _factor: float) -> None:
        # self.move_and_collide(Vector2(*VECTOR_ZERO))
        # super()._physics_process(factor)
        self._knock_timer._process(root.delta)

    def set_target(self, value: Node) -> None:
        self._current_target = value
        self.move = self._move if value is None else self._follow

    def attack(self, body: Body) -> None:
        assert isinstance(body, Ship) or isinstance(
            body, Plant) or isinstance(body, Player)
        # Configura o ataque
        self.move = NONE_CALL
        self._cached_move = self.move
        self._attack(body)
        self.disconnect(self.body_entered, self)

    def _attack(self, target: Union[Ship, Plant, Player]) -> None:
        '''Inicia a animação de ataque.'''
        self._state = Native.States.ATK_CHARGE
        self.target = target
        self.animations.play_once(self.animation_attack, self.sprite, deque(
            [self.animations.animations[self.animation_attack].get_frames() / 2.0]))
        self.sprite.connect(self.sprite.anim_event_triggered, self,
                            self._on_Anim_event_triggered, target)

    def _on_Anim_event_triggered(self, target: Union[Ship, Plant, Player], _time: float) -> None:
        self._state = Native.States.FINISHING_ATK
        target.take_damage(self.atk)
        self.sprite.disconnect(self.sprite.anim_event_triggered, self)
        self.sprite.connect(self.sprite.animation_finished,
                            self, self._on_Anim_event_finished)

    def _on_Anim_event_finished(self) -> None:
        self.sprite.disconnect(self.sprite.animation_finished, self)

        # Reinicia a animação.
        # Note que alguns sinais de colisão redirecionam para o método `attack()`.
        for body in self._last_colliding_bodies:
            # Ataca o navio.
            self._attack(body)
            return

        for body in self.atk_box._last_colliding_bodies:
            # Ataca um dos corpos colisores (planta ou jogador).
            self._attack(body)
            return

        self._state = Native.States.WALK
        self.connect(self.body_entered, self, self.attack)
        self.move = self._cached_move

    def _on_KnockTimer_timeout(self, animation: str, timer: Timer) -> None:
        # Tempo de dano acabou
        atlas: AtlasBook = self.sprite.atlas
        last_state: int = self._last_state

        # Retorna para o estado anterior
        atlas.set_current_animation(animation)
        timer.timeout.disconnect(timer, self)
        self._last_state = Native.States.TAKING_DAMAGE

        if last_state & (Native.States.ATK_CHARGE | Native.States.FINISHING_ATK):
            # Reinicia a animação.
            # Note que alguns sinais de colisão redirecionam para o método `attack()`.
            for body in self._last_colliding_bodies:
                # Ataca o navio.
                self._attack(body)
                return

            for body in self.atk_box._last_colliding_bodies:
                # Ataca um dos corpos colisores (planta ou jogador).
                self._attack(body)
                return

            # Reabilita as colisões
            self.connect(self.body_entered, self, self.attack)
        else:
            self._state = Native.States.WALK
            self.move = self._cached_move

    def _on_hurtted(self, _strength: int) -> None:
        def discharge() -> None:
            nonlocal self
            self.sprite.disconnect(self.sprite.anim_event_triggered, self)

        def finish_already() -> None:
            nonlocal self
            self.sprite.disconnect(self.sprite.animation_finished, self)

        def reset_timer() -> None:
            nonlocal self
            self._knock_timer.elapsed_time = 0.0

        self._last_state = self._state
        STATE_TABLE: dict[int, Callable[[], None]] = {
            Native.States.ATK_CHARGE: discharge,
            Native.States.FINISHING_ATK: finish_already,
            Native.States.TAKING_DAMAGE: reset_timer,
        }

        STATE_TABLE.get(self._state, NONE_CALL)()

        atlas: AtlasBook = self.sprite.atlas
        atlas.set_current_animation(self.animation_damage)
        timer: Timer = Timer(self._damage_anim_duration)

        self._knock_timer = timer
        self.move = self._knockback
        self._knock_timer.timeout.connect(
            self._knock_timer, self, self._on_KnockTimer_timeout, self.animation_walk)
        self._state = Native.States.TAKING_DAMAGE

    def _on_health_depleated(self) -> None:
        self.free()

    def _on_Area_enter_view(self, _area: Area) -> None:
        self._change_target()

    def _on_Area_exit_view(self, _area: Area) -> None:

        if self.view_range._colliding_bodies:
            self._change_target()
        else:
            self.move = self._move

    def _change_target(self) -> None:
        target: Body = self.view_range._colliding_bodies[0]
        target_distance: float = get_distance(
            self._global_position, target._global_position)

        for body in self.view_range._colliding_bodies[1:]:
            distance: float = get_distance(
                self._global_position, body._global_position)

            if distance < target_distance:
                target_distance = distance
                target = body

        self.target = target
        self.target_pos = target._global_position
        self.move = self._follow

    def __init__(self, final_target_pos: tuple[int, int], max_hp_range: tuple[int, int],
                 spritesheet: Surface, spritesheet_data: dict[str, list[dict]],
                 animation_move: str, animation_damage: str, animation_attack: str,
                 name: str = 'Native', coords: tuple[int, int] = VECTOR_ZERO,
                 color: Color = Color('#f3ce52')) -> None:
        super().__init__(spritesheet, spritesheet_data, name=name,
                         coords=coords, color=color, animation=animation_move)
        self.collision_layer = PhysicsLayers.NATIVES_BODIES
        self.target_pos = self.final_target_pos = final_target_pos
        self.move = self._move
        self.animation_walk = animation_move
        self.animation_damage = animation_damage
        self.animation_attack = animation_attack

        self._current_target: Node = None
        self._cached_move = self._move

        animations: AtlasBook = self.sprite.atlas
        self.animations = animations
        damage_sequence: TextureSequence = animations.animations[animation_damage]
        self._damage_anim_duration = damage_sequence.get_frames() * \
            damage_sequence.speed / 60.0

        # Sets the `HurtBox`
        hurt_box: HurtBox = HurtBox(
            PhysicsLayers.NATIVES_BODIES, health=randint(*max_hp_range))
        hurt_box.collision_mask = PhysicsLayers.PLANTS_VIEW
        hurt_box.connect(hurt_box.hitted, self, self._on_hurtted)
        hurt_box.connect(hurt_box.health_depleated, self,
                         self._on_health_depleated)

        # Sets the "attack box"
        atk_box: Area = Area('AtkBox', color=(250, 100, 50))
        atk_shape: Shape = Shape()
        atk_shape.set_rect(Rect(VECTOR_ZERO, animations.image.get_size()))
        atk_box.collision_layer = PhysicsLayers.NATIVES_HITBOX
        atk_box.collision_mask = 0
        atk_box.add_child(atk_shape)
        atk_box.connect(atk_box.body_entered, self, self.attack)
        self.atk_box = atk_box

        shape: Shape = Shape()
        shape.set_rect(Rect(VECTOR_ZERO, array(
            self.sprite.atlas.base_size) - (12, 6)))
        hurt_box.add_child(shape)

        # View Range
        # WATCH
        view_range: Area = Area('View', color=Color(145, 135, 25))
        view_range.collision_layer = PhysicsLayers.NATIVES_VIEW
        view_range.collision_mask = 0
        self.view_range = view_range
        view_range.connect(view_range.body_entered, self, self._on_Area_enter_view)
        view_range.connect(view_range.body_exited, self, self._on_Area_exit_view)

        view: CircleShape = CircleShape(
            radius=self.sprite.atlas.rect.size[X] * 4)
        view_range.add_child(view)

        # Sets the `Shape` child
        shape = Shape()
        shape.set_rect(Rect(VECTOR_ZERO, array(
            self.sprite.atlas.base_size) - (16, 10)))

        self.connect(self.body_entered, self, self.attack)

        self.add_child(shape, 0)
        self.add_child(hurt_box, 1)
        self.add_child(atk_box, 2)
        self.add_child(view_range)

    current_target: Node = property(lambda _self: _self.target, set_target)


class Hermiga(Native):

    def __init__(self, final_target_pos: tuple[int, int], spritesheet: Surface,
                 spritesheet_data: dict[str, list[dict]], name: str = 'Hermiga',
                 coords: tuple[int, int] = VECTOR_ZERO, max_hp_range: tuple[int, int] = (3, 6)) -> None:
        super().__init__(final_target_pos, max_hp_range, spritesheet, spritesheet_data,
                         animation_move='hermiga_walk', animation_damage='hermiga_damage',
                         animation_attack='hermiga_attack', name=name,
                         coords=coords, color=Color('#f3ce52'))
        self.atk = 3


class Mosca(Native):

    def __init__(self, final_target_pos: tuple[int, int], spritesheet: Surface,
                 spritesheet_data: dict[str, list[dict]], name: str = 'Mosca',
                 coords: tuple[int, int] = VECTOR_ZERO, max_hp_range: tuple[int, int] = (3, 5)) -> None:
        super().__init__(final_target_pos, max_hp_range, spritesheet, spritesheet_data,
                         animation_move='mosca_fly', animation_damage='mosca_damage',
                         animation_attack='mosca_attack', name=name,
                         coords=coords, color=Color('#57b9f2'))
        self.atk = 2


class Lunar(Native):

    def __init__(self, final_target_pos: tuple[int, int], spritesheet: Surface,
                 spritesheet_data: dict[str, list[dict]], name: str = 'Lunar',
                 coords: tuple[int, int] = VECTOR_ZERO, max_hp_range: tuple[int, int] = (3, 4)) -> None:
        super().__init__(final_target_pos, max_hp_range, spritesheet, spritesheet_data,
                         animation_move='lunar_dig', animation_damage='lunar_damage',
                         animation_attack='lunar_attack', name=name,
                         coords=coords, color=Color('#8e6b2b'))
        self.atk = 1
