from random import choice
from src.core.nodes import *
from ..consts import *


class Player(KinematicBody):
    '''Objeto único de jogo. É o ator/ personagem principal controlado pelo jogador.'''
    JUMP: str = "jump"
    GRAVITY: float = 0.1

    points_changed: Entity.Signal
    scored: Entity.Signal
    died: Entity.Signal

    _velocity: array
    _jump_strength: float = 0.0
    _floor: float
    _start_position: tuple[int, int]

    was_collided: bool = False
    speed: float = 1.0
    jump_force: float = 5.0
    sprite: Sprite

    score_sfx: Sound = None
    death_sfx: Sound = None

    def _process(self) -> None:
        self.points += 1

        if self.points % 500 == 0:
            self.score_sfx.play()
            self.scored.emit()

        super()._process()

    def _physics_process(self) -> None:
        self._move_()

    def _move(self) -> None:
        self.position = array(
            [self._run(self.position[X]), self._jump(self.position[Y])], dtype=int)

    def _float(self) -> None:
        position: list = [self.position[0], self.position[1]]

        for i in range(2):
            position[i] += self._velocity[i] * self.speed

            if position[i] < 0.0:
                position[i] = 0.0
            elif position[i] > root.screen_size[i]:
                position[i] = root.screen_size[i]

        self.position = array(position)

    def _run(self, x: float) -> float:
        x += self._velocity[X] * self.speed

        if x < 0.0:
            x = 0.0
        elif x > root.screen_size[X]:
            x = root.screen_size[X]

        return x

    def _jump(self, y: float) -> float:

        if y < self._floor:
            # Aplicação da gravidade quando não está no chão
            self._velocity[Y] -= self.GRAVITY

        y = min((y - self._velocity[Y], self._floor))
        self._velocity[Y] += self._jump_strength * 0.1

        if self._jump_strength > 0.0:
            self._jump_strength = max((self._jump_strength - lerp(
                self._jump_strength, 0.0, self.GRAVITY), 0.0))

            if self._jump_strength < 0.2:
                self._jump_strength = 0.0

        return y

    def _input(self) -> None:
        self._apply_velocity_()

    def _apply_x_velocity(self) -> None:
        self._velocity[X] = Input.get_input_strength()[0]

    def _apply_xy_velocity(self) -> None:
        self._velocity = Input.get_input_strength()

    def _input_event(self, event: InputEvent) -> None:

        if event.tag is self.JUMP and self.position[Y] >= self._floor:
            # Reseta a velocidade com o impulso do pulo
            self._velocity[Y] -= self._velocity[Y]
            self._jump_strength = self.jump_force

    def _on_Body_collided(self, body: KinematicBody) -> None:
        global root, ENEMY_GROUP

        if self.was_collided:
            return

        if root.is_on_group(body, ENEMY_GROUP):
            root.pause_tree()
            self.sprite.atlas.is_paused = True
            self.death_sfx.play()
            self.was_collided = True
            self.died.emit()

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

    def __init__(self, score_sfx: Sound, death_sfx: Sound, spritesheet: Surface,
                 name: str = 'Player', coords: tuple[int, int] = VECTOR_ZERO,
                 color: Color = (15, 92, 105)) -> None:
        global root, input, root, SPRITE_SIZE, SPRITES_SCALE, PLAYER_GROUP
        super().__init__(name, coords=coords, color=color)

        self.score_sfx = score_sfx
        self.death_sfx = death_sfx
        self.scale = array(SPRITES_SCALE)
        self._points: int = 0

        self._velocity = array([0.0, 0.0])
        self._floor = self.position[Y]
        self._start_position = coords

        input.register_event(self, KEYDOWN, K_SPACE, self.JUMP)
        self.collided.connect(self, self, self._on_Body_collided)

        # Set the Sprite
        sprite: Sprite = Sprite()
        sprite.atlas.add_spritesheet(
            spritesheet, h_slice=3, sprite_size=SPRITE_SIZE)
        sprite.group = PLAYER_GROUP
        self.sprite = sprite
        root.add_to_group(self, PLAYER_GROUP)
        self.add_child(sprite)

        # Set the Shape
        shape: Shape = Shape()
        rect: Rect = Rect(sprite.atlas.rect)
        rect.size -= array([16, 16])
        shape.rect = rect
        self.add_child(shape)

        # Signals
        self.points_changed = Entity.Signal(self, 'points_changed')
        self.scored = Entity.Signal(self, 'scored')
        self.died = Entity.Signal(self, 'died')

        # Connections

        # Shift methods when testing
        self._move_: Callable
        self._apply_velocity_: Callable

        if IS_DEV_MODE_ENABLED:
            self._move_ = self._float
            self._apply_velocity_ = self._apply_xy_velocity
            self.speed += 1.0
        else:
            self._move_ = self._move
            self._apply_velocity_ = self._apply_x_velocity

    points: property = property(get_points, set_points)


class Runner(KinematicBody):
    speed: float = 1.0
    notifier: VisibilityNotifier

    def _physics_process(self) -> None:
        global root

        edge: int = self.sprite.get_cell()[X] * self.scale[X]
        self.position[X] = (self.position[X] - int(self.speed) + edge) % \
            (root._screen_width + edge * 2) - edge

    def __init__(self, name: str = 'Runner', coords: tuple[int, int] = VECTOR_ZERO,
                 color: Color = Color(46, 10, 115)) -> None:
        super().__init__(name=name, coords=coords, color=color)

        # Set the VisibilityNotifier
        notifier: VisibilityNotifier = VisibilityNotifier()
        self.notifier = notifier
        self.add_child(notifier)


class Cactus(Runner):
    '''Objeto único de jogo. Objeto que pode colidir com o personagem protagonista.'''
    sprite: Sprite

    def __init__(self, spritesheet: Surface, name: str = 'Cactus', coords: tuple[int, int] = VECTOR_ZERO) -> None:
        global root, SPRITES_SCALE, ENEMY_GROUP
        super().__init__(name=name, coords=coords)
        self.scale = array(SPRITES_SCALE)

        # Set the sprite
        sprite: Sprite = Sprite()
        sprite.atlas.add_spritesheet(spritesheet, coords=(
            CELL_SIZE * 5, 0), sprite_size=CELL)
        sprite.group = ENEMY_GROUP
        root.add_to_group(self, ENEMY_GROUP)
        self.sprite = sprite
        self.add_child(sprite)

        # Set the shape
        shape: Shape = Shape()
        rect: Rect = Rect(sprite.atlas.rect)
        rect.size = rect.size - array([16, 8])
        shape.rect = rect
        self.add_child(shape)
        self.notifier.rect = Rect((0, 0), rect.size + array([6, 6]))


class PteroDino(Runner):
    sprite: Sprite

    def _on_Game_pause_toggled(self, paused: bool = False) -> None:
        self.sprite.atlas.is_paused = paused

    def __init__(self, spritesheet: Surface, name: str = 'PteroDino',
                 coords: tuple[int, int] = VECTOR_ZERO, color: Color = Color(46, 10, 115)) -> None:
        super().__init__(name=name, coords=coords, color=color)
        global root, SPRITES_SCALE, SPRITE_SIZE, ENEMY_GROUP

        self.scale = array(SPRITES_SCALE)
        self.notifier.rect = Rect((0, 0), (24, 20))

        # Set the Sprite
        sprite: Sprite = Sprite()
        sprite.atlas.add_spritesheet(spritesheet, h_slice=2, coords=(
            CELL_SIZE * 3, 0), sprite_size=array(SPRITE_SIZE))
        sprite.group = ENEMY_GROUP
        self.sprite = sprite
        root.add_to_group(self, ENEMY_GROUP)
        self.add_child(sprite)

        # Set the Shape
        shape: Shape = Shape()
        rect: Rect = Rect(sprite.atlas.rect)
        rect.size -= array([16, 16])
        shape.rect = rect
        self.add_child(shape)

        # Connect to events
        root.connect(root.pause_toggled, self, self._on_Game_pause_toggled)


class Spawner(Node):
    '''Objeto único de jogo. Nó responsável pela aparição de obstáculos na tela.'''
    current_speed: int
    floor_coord: tuple[int, int]
    spritesheet: Surface

    cactus: Cactus = None
    pterodino: PteroDino = None
    spawns: list[Node] = None

    def _on_Game_resumed(self) -> None:

        for child in self._children_index:
            child.position[X] = self._SPAWN_POS

    def set_speed(self, value: float) -> None:
        self.current_speed = value
        self.cactus.speed = value
        self.pterodino.speed = value

    def speed_up(self) -> None:
        self.set_speed(self.current_speed + 1)

    def _on_Notifier_screen_exited(self, node: Node) -> None:
        self.remove_child(node)
        self.add_child(choice(self.spawns))

    def _setup_spawn(self) -> None:
        global root
        notifier: VisibilityNotifier

        self.cactus = Cactus(self.spritesheet, coords=(
            self._SPAWN_POS, self.floor_coord + CELL_SIZE // 2))
        notifier = self.cactus.notifier
        notifier.connect(notifier.screen_exited, self,
                         self._on_Notifier_screen_exited, self.cactus)

        self.pterodino = PteroDino(self.spritesheet, coords=(
            self._SPAWN_POS, root._screen_height // 2 + 100))
        notifier = self.pterodino.notifier
        notifier.connect(notifier.screen_exited, self,
                         self._on_Notifier_screen_exited, self.pterodino)

        self.spawns = [self.cactus, self.pterodino]
        self.add_child(choice(self.spawns))

    def __init__(self, floor_coord: tuple[int, int], spritesheet: Surface, name: str = 'Spawner',
                 coords: tuple[int, int] = VECTOR_ZERO, speed: int = 1) -> None:
        global root
        super().__init__(name=name, coords=coords)

        self.floor_coord = floor_coord
        self.spritesheet = spritesheet
        self._SPAWN_POS: int = root._screen_width + \
            CELL_SIZE * SPRITES_SCALE[X]
        self._setup_spawn()
        self.anchor = array(BOTTOM_RIGHT)
        self.set_speed(speed)
