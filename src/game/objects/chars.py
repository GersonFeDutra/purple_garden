from pygame.mixer import Sound
from random import randint
from src.core.nodes import *
from ..consts import *
from ..utils import HurtBox, Steering, spritesheet_slice
from .plants import Plant, Rose, Violet


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
    final_target_pos: tuple[int, int]
    target_pos: tuple[int, int]
    animation_walk: str
    animation_attack: str
    animation_damage: str
    move: Callable[[float], None]

    _damage_anim_duration: float
    _is_flipped: bool = False
    _timer: Timer = None

    def _draw(self, target_pos: tuple[int, int], target_scale: tuple[float, float], offset: tuple[int, int]) -> None:
        return super()._draw(target_pos, target_scale, offset)

    def _physics_process(self, factor: float) -> None:
        self.move(factor)

    def _follow(self, factor: float) -> None:
        self._velocity = Steering.follow(Vector2(
            *self._velocity), Vector2(*self._global_position), Vector2(*self.final_target_pos))
        self.move_and_collide(self._velocity * self.speed)
        super()._physics_process(factor)

    def _move(self, factor: float) -> None:
        self._velocity = Steering.follow(Vector2(
            *self._velocity), Vector2(*self._global_position), Vector2(*self.final_target_pos))
        is_flipped: bool = self._velocity.x > 0.0

        if self._is_flipped != is_flipped:
            self.sprite.atlas.flip_h = is_flipped
            self._is_flipped = is_flipped

        self.move_and_collide(self._velocity * self.speed)
        super()._physics_process(factor)

    def _knockback(self, _factor: float) -> None:
        # self.move_and_collide(Vector2(*VECTOR_ZERO))
        # super()._physics_process(factor)
        self._timer._process(root.delta)

    def set_target(self, value: Node) -> None:
        self._current_target = value
        self.move = self._move if value is None else self._follow

    def _on_Body_collided(self, body: Body) -> None:

        if body.name == 'Ship':
            self.move = NONE_CALL
            self.disconnect(self.body_entered, self)

    def _on_Timer_timeout(self, move: Callable[[float], None], animation: str, timer: Timer) -> None:
        atlas: AtlasBook = self.sprite.atlas
        atlas.set_current_animation(animation)
        timer.timeout.disconnect(timer, self)
        self.move = move
        self._timer = None
        # Retorna para o estado anterior

    def _on_hurtted(self, _strength: int) -> None:

        if self._timer is None:
            atlas: AtlasBook = self.sprite.atlas
            atlas.set_current_animation(self.animation_damage)
            timer: Timer = Timer(self._damage_anim_duration)
            self._timer = timer
            self._timer.timeout.connect(
                self._timer, self, self._on_Timer_timeout, self.move, self.animation_walk)
            self.move = self._knockback
        else:
            # Reseta o timer
            self._timer.elapsed_time = 0.0

    def _on_health_depleated(self) -> None:
        self.free()

    def _on_Area_enter_view(self, area: Area) -> None:
        return

    def __init__(self, final_target_pos: tuple[int, int], max_hp_range: tuple[int, int],
                 spritesheet: Surface, spritesheet_data: dict[str, list[dict]],
                 animation_move: str, animation_damage: str, animation_attack: str,
                 name: str = 'Native', coords: tuple[int, int] = VECTOR_ZERO,
                 color: Color = Color('#f3ce52')) -> None:
        super().__init__(spritesheet, spritesheet_data, name=name,
                         coords=coords, color=color, animation=animation_move)
        self.collision_layer = PhysicsLayers.NATIVES_BODIES
        self.final_target_pos = final_target_pos
        self.move = self._move
        self.animation_walk = animation_move
        self.animation_damage = animation_damage
        self.animation_attack = animation_attack
        self._current_target: Node = None
        animations: AtlasBook = self.sprite.atlas
        self._damage_anim_duration = animations.animations[animation_damage].get_frames() * \
            animations.sequence.speed / 60.0

        # Sets `HurtBox`
        hurt_box: HurtBox = HurtBox(
            PhysicsLayers.NATIVES_BODIES, health=randint(*max_hp_range))
        hurt_box.collision_mask = PhysicsLayers.PLANTS_VIEW
        hurt_box.connect(hurt_box.hitted, self, self._on_hurtted)
        hurt_box.connect(hurt_box.health_depleated, self,
                         self._on_health_depleated)

        shape: Shape = Shape()
        shape.set_rect(Rect(VECTOR_ZERO, array(
            self.sprite.atlas.base_size) - (12, 6)))
        hurt_box.add_child(shape)

        # View Range
        # WATCH
        view_range: Area = Area('View', color=Color(145, 135, 25))
        view_range.collision_layer = PhysicsLayers.NATIVES_VIEW
        view_range.collision_mask = 0
        view_range.connect(view_range.body_entered, self,
                           self._on_Area_enter_view)

        view: CircleShape = CircleShape(
            radius=self.sprite.atlas.rect.size[X] * 4)
        view_range.add_child(view)

        # Sets the `Shape` child
        shape = Shape()
        shape.set_rect(Rect(VECTOR_ZERO, array(
            self.sprite.atlas.base_size) - (16, 10)))

        self.connect(self.body_entered, self, self._on_Body_collided)

        self.add_child(shape, 0)
        self.add_child(hurt_box, 1)
        self.add_child(view_range)
        self.current_target: Node = property(
            lambda _self: _self.target, self.set_target)


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
