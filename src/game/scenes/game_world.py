from numpy.core.arrayprint import SubArrayFormat
from src.core.nodes import *
from ..gui.ui import *
from ..objects.chars import *
from ..objects.props import *
from ..consts import *


class GUI(Node):
    '''Game's Graphical User Interface from the Level.'''
    game_over_display: GameOverDisplay

    def __init__(self, spritesheet: Surface, spritesheet_data: dict[str, list[dict]],
                 default_font: font.Font, gui_font: font.Font, name: str = 'GUI',
                 coords: tuple[int, int] = VECTOR_ZERO) -> None:
        super().__init__(name=name, coords=coords)
        MAX_KEY_ITEMS: int = 10

        # label: Label = Label((240, 240), color=colors.BLACK, text='Points: 0')

        # Bars
        BAR_THICKNESS: int = 25
        BAR_OFFSET: tuple = BAR_THICKNESS, BAR_THICKNESS
        bar: ProgressBar = ProgressBar(coords=(BAR_OFFSET[X] * 3, BAR_OFFSET[Y]), size=(
            root._screen_width - BAR_OFFSET[X] * 4, BAR_THICKNESS))
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
        self.game_over_display = display

        # Key Items
        key_items: Grid = Grid(
            coords=(int(BAR_OFFSET[X] * 3.8), BAR_OFFSET[Y] * 5), rows=MAX_KEY_ITEMS // 2)

        violet_color_key = str(Color('#fe5b59ff'))

        if violet_color_key in spritesheet_data:

            for i in range(MAX_KEY_ITEMS):
                slice: dict = spritesheet_data[violet_color_key][0]
                n_slices: int = int(slice['data'])
                bounds: dict[str, int] = slice['keys'][0]['bounds']
                item_textures: list[Surface] = Icon.get_spritesheet(spritesheet, v_slice=n_slices, coords=(
                    bounds['x'], bounds['y']), sprite_size=(bounds['w'], bounds['h'] / n_slices))
                item: Sprite = Sprite(
                    name=f'Item{i}', atlas=Icon(item_textures))
                item.anchor = array(TOP_LEFT)
                key_items.add_child(item)

        else:
            warnings.warn('color not found')

        # Construção da árvore
        self.add_child(bar)
        self.add_child(o2_bar)
        self.add_child(o2_label)
        self.add_child(nl2_bar)
        self.add_child(nl2_label)
        self.add_child(key_items)
        self.add_child(display)


class Level(Node):
    '''Node that holds all "space related" nodes.
    That is the "world" and all objects that can be interected with.'''
    player: Player
    spawner: Spawner
    bg: BackGround

    def __init__(self, spritesheet_old: Surface, spritesheet: Surface,
                 spritesheet_data: dict[str, list[dict]], sound_fxs: dict[str, Sound],
                 name: str = 'Level', coords: tuple[int, int] = VECTOR_ZERO) -> None:
        super().__init__(name=name, coords=coords)
        # Nodes Setup
        FLOOR_COORD: float = root._screen_height - CELL_SIZE * SPRITES_SCALE[Y]

        bg: BackGround = BackGround(spritesheet_old, 3)
        self.bg = bg
        spawner: Spawner = Spawner(
            FLOOR_COORD, spritesheet_old, speed=bg.scroll_speed)
        self.spawner = spawner
        # spawn: Spawn = Spawn(coords=(randint(0, root._screen_width), randint(0, root._screen_height)))

        player: Player = Player(
            spritesheet, spritesheet_data, sound_fxs['score'],
            sound_fxs['death'], coords=array(
                [root._screen_width // 2, FLOOR_COORD + CELL_SIZE // 2]) + (16, 16))
        # player: Player = Player(coords=(root._screen_width // 2, root._screen_height // 2))
        player.scale = array(SPRITES_SCALE)
        self.player = player

        # Construção da árvore
        self.add_child(bg)
        # root.add_child(spawn)
        self.add_child(player)
        self.add_child(spawner)
        # root.add_child(label)


class GameWorld(Node):
    '''First Game's Scene.'''

    def __init__(self, spritesheet_old: Surface, spritesheet: SubArrayFormat,
                 spritesheet_data: dict[str, list[dict]], sound_fxs: dict[str, Sound],
                 default_font: font.Font, gui_font: font.Font, name: str = 'GameWorld',
                 coords: tuple[int, int] = VECTOR_ZERO) -> None:
        super().__init__(name=name, coords=coords)
        root.screen_color = colors.WHITE
        # Construção da cena
        level: Level = Level(spritesheet_old, spritesheet,
                             spritesheet_data, sound_fxs)
        gui: GUI = GUI(spritesheet, spritesheet_data, default_font, gui_font)
        self.add_child(level)
        self.add_child(gui)

        # Conexões
        player: Player = level.player
        spawner: Spawner = level.spawner
        bg: BackGround = level.bg
        display: GameOverDisplay = gui.game_over_display

        # spawn.connect(spawn.collected, score_sfx, score_sfx.play)
        # player.connect(player.points_changed, label, label.set_text)
        player.connect(player.scored, bg, bg.speed_up)
        player.connect(player.scored, spawner, spawner.speed_up)
        player.connect(player.died, display, display.show)
        display.connect(display.game_resumed, spawner,
                        spawner._on_Game_resumed)
        display.connect(display.game_resumed, player, player._on_Game_resumed)
