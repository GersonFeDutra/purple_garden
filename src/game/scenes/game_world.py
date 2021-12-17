from typing import Optional
from numpy import ceil
from src.core.nodes import *
from ..consts import *
from ..gui.ui import *
from ..objects.chars import *
from ..objects.props import *
from ..utils import get_icon_sequence_slice
from ..objects.ground import GroundGrid


class GUI(Node):
    '''Game's Graphical User Interface from the Level.'''
    game_over_display: GameOverDisplay
    o2_bar: ProgressBar
    nl2_bar: ProgressBar
    wave_bar: ProgressBar

    def set_wave_time(self, value: float) -> None:
        self.wave_bar.progress = value

    def __init__(self, spritesheet: Surface, spritesheet_data: dict[str, list[dict]],
                 default_font: font.Font, gui_font: font.Font, name: str = 'GUI',
                 coords: tuple[int, int] = VECTOR_ZERO) -> None:
        super().__init__(name=name, coords=coords)
        MAX_KEY_ITEMS: int = 10

        # label: Label = Label((240, 240), color=colors.BLACK, text='Points: 0')

        # Bars
        BAR_THICKNESS: int = 25
        BAR_OFFSET: tuple = BAR_THICKNESS, BAR_THICKNESS
        bar: ProgressBar = ProgressBar(
            name='WaveBar', coords=(BAR_OFFSET[X] * 3, BAR_OFFSET[Y]),
            size=(root._screen_width - BAR_OFFSET[X] * 4, BAR_THICKNESS), flip=True)
        o2_bar: ProgressBar = ProgressBar(name='O2Bar', coords=(
            BAR_OFFSET[X], BAR_OFFSET[Y] * 2), v_grow=True,
            size=(BAR_THICKNESS, root._screen_height - BAR_OFFSET[Y] * 3))
        o2_label: Label = Label(gui_font, name='O2Label',
                                coords=BAR_OFFSET, color=colors.CYAN, text='O²')
        nl2_bar: ProgressBar = ProgressBar(name='Nl2Bar', coords=(
            int(BAR_OFFSET[X] * 3.5), BAR_OFFSET[Y] * 3), size=(BAR_THICKNESS * 7, BAR_THICKNESS))
        nl2_label: Label = Label(gui_font, name='Nl2Label', coords=nl2_bar.position +
                                 (nl2_bar.size[X], 0), color=colors.BLUE, text='NL²')
        display: GameOverDisplay = GameOverDisplay(default_font)
        self.wave_bar = bar
        self.o2_bar = o2_bar
        self.nl2_bar = nl2_bar
        self.game_over_display = display

        # Key Items
        key_items: Grid = Grid(
            coords=(int(BAR_OFFSET[X] * 3.8), BAR_OFFSET[Y] * 5), rows=MAX_KEY_ITEMS // 2)

        violet_color_key = str(Color('#fe5b59ff'))
        item_textures: list[Surface] = get_icon_sequence_slice(
            spritesheet, spritesheet_data, violet_color_key)

        for i in range(MAX_KEY_ITEMS):
            item: Sprite = Sprite(
                name=f'Item{i}', atlas=Icon(item_textures))
            item.anchor = array(TOP_LEFT)
            key_items.add_child(item)

        # Construção da árvore
        self.add_child(bar)
        self.add_child(o2_bar)
        self.add_child(o2_label)
        self.add_child(nl2_bar)
        self.add_child(nl2_label)
        self.add_child(key_items)
        self.add_child(display)


class Limits(Shape):

    def __init__(self, size: tuple[int, int], name: str = 'Limits',
                 coords: tuple[int, int] = VECTOR_ZERO) -> None:
        super().__init__(name=name, coords=coords)
        self._debug_fill_bounds = False
        self.set_rect(Rect(VECTOR_ZERO, size))


class Level(Node):
    '''Node that holds all "space related" nodes.
    That is the "world" and all objects that can be interected with.'''
    waved: Node.Signal
    wave_length_changed: Node.Signal

    wave_n: int = 0
    spawns: int = 0
    elapsed_time: float = 0.0
    wave_trigger: float = .3  # %
    wave_percent: float = 0.  # %
    wave_length: float = 60.0 if IS_DEBUG_ENABLED else 600.0
    spawn_frequency: float = 3.0 if IS_DEBUG_ENABLED else 10.0
    center: tuple[int, int]

    gui: GUI
    ship: Ship
    player: Player
    bg: GroundGrid

    spritesheet: Surface
    spritesheet_data: dict[str, list[dict]]
    natives: list[type[Native]] = [Hermiga, Mosca, Lunar]

    def _process(self, delta: float) -> None:
        self.elapsed_time += delta / root.fixed_fps

        if self.elapsed_time >= self.spawn_frequency * (self.spawns + 1):
            self._spawn_native(self)

        try:
            self.wave_percent = self.elapsed_time / self.wave_length
        except ZeroDivisionError:
            return

        self.wave_length_changed.emit(self.wave_percent)

        if self.wave_percent >= self.wave_trigger * self.wave_n:
            self.wave_n += 1
            self.waved.emit(self.wave_n)

    def _enter_tree(self) -> None:
        super()._enter_tree()
        self.bg.spawn_object(self.ship, self.bg.map_size // 2 - (2, 1))

    def spawn_native(self, offset: tuple[int, int] = (-1, -1)) -> None:
        spawn: Native = self.natives[randint(0, self.wave_n % 3)](
            self.center, spritesheet=self.spritesheet,
            spritesheet_data=self.spritesheet_data, name=f'Native{self.spawns}')
        self.bg.spawn_object(spawn, self.bg.get_random_edge_spot(offset))
        self.spawns += 1

    def __init__(self, size: tuple[int, int], spritesheet: Surface,
                 spritesheet_data: dict[str, list[dict]], sound_fxs: dict[str, Sound],
                 name: str = 'Level', coords: tuple[int, int] = VECTOR_ZERO) -> None:
        super().__init__(name=name, coords=coords)
        self.waved = Node.Signal(self, 'waved')
        self.wave_length_changed = Node.Signal(self, 'wave_length_changed')
        self.spritesheet = spritesheet
        self.spritesheet_data = spritesheet_data
        self._spawn_native: Callable[[tuple[int, int]], None] = \
            lambda self: self.spawn_native(array(self.bg.map_size) // 3) \
                if IS_DEBUG_ENABLED else self.spawn_native

        # Level Setup
        center: ndarray = array(size) // 2
        self.center = tuple(center)
        # Sets the Ship
        self.ship = Ship(spritesheet, spritesheet_data,
                         coords=center - (0, 150))
        # Sets the Player in level space
        player: Player = Player(
            Limits(root.screen_size), spritesheet, spritesheet_data,
            sound_fxs['death'], coords=tuple(center))
        player.scale = array(SPRITES_SCALE)
        self.player = player
        # Sets the BackGround Grid
        grid_size: tuple[int, int] = array(ceil(
            size / (self.scale * array(SPRITES_SCALE, float) * CELL_SIZE)), int)
        bg: GroundGrid = GroundGrid(
            grid_size, CELL, SPRITES_SCALE, spritesheet, spritesheet_data, player)
        self.bg = bg

        # Construção da árvore
        self.add_child(bg)
        self.add_child(player)


class GameWorld(Node):
    '''First Game's Scene.'''

    def __init__(self, spritesheet: Surface,
                 spritesheet_data: dict[str, list[dict]], sound_fxs: dict[str, Sound],
                 default_font: font.Font, gui_font: font.Font, name: str = 'GameWorld',
                 coords: tuple[int, int] = VECTOR_ZERO) -> None:
        super().__init__(name=name, coords=coords)
        root.screen_color = colors.GRAY

        map_size: tuple[int, int] = array(root.get_screen_size()) * 3
        # Construção da cena
        level: Level = Level(
            map_size, spritesheet, spritesheet_data, sound_fxs)
        gui: GUI = GUI(spritesheet, spritesheet_data, default_font, gui_font)

        level_layer: CanvasLayer = CanvasLayer(name='LevelLayer')
        self.add_child(level_layer)
        level_layer.add_child(level)
        self.add_child(gui)

        player: Player = level.player

        display: GameOverDisplay = gui.game_over_display
        camera: Camera = Camera(Camera.FollowLimit(
            player, (*VECTOR_ZERO, *map_size)))
        level_layer.add_child(camera)
        level_layer.active_camera = camera

        # Conexões
        # spawn.connect(spawn.collected, score_sfx, score_sfx.play)
        # player.connect(player.points_changed, label, label.set_text)
        player.connect(player.died, display, display.show)
        # display.connect(display.game_resumed, spawner,
        #                 spawner._on_Game_resumed)
        display.connect(display.game_resumed, player, player._on_Game_resumed)
        level.connect(level.wave_length_changed, self, gui.set_wave_time)
