import json

from os import path
from pygame.mixer import Sound
from src.core.nodes import *
from src.game.objects.chars import *
from src.game.objects.props import *
from src.game.gui.ui import *
from src.game.consts import *


def fetch_spritesheet(from_path: str) -> dict[str, list[dict]]:
    '''Função auxiliar para importar dados de uma spritesheet
    a partir de um arquivo JSON criado no editor Aseprite.'''
    print("Started reading spritesheet JSON file...")

    with open(from_path, "r") as read_file:
        print("Starting to convert JSON decoding...")
        sheet = json.load(read_file)

        print("Decoded JSON Data From File...")
        # print(sheet)
        # for key, value in sheet.items():
        #     print(key, ":", value)

        # print(sheet['frames'])
        # for key, value in sheet['frames'].items():
        # print(key, ":", value)

        # for key, value in refs.items():
        #     print(key, ' : ', sheet['frames'][key]['frame'])

        map: dict[str, list[dict]] = {}

        for slice in sheet['meta']['slices']:
            color: str = str(Color(slice['color']))

            if color in map:
                map[color].append(slice)
            else:
                map[color] = [slice]

        # print(map)

        print("Done reading JSON file...")
        return map


# Setup the Engine
root.start(TITLE, screen_size=BASE_SIZE * array(SPRITES_SCALE, dtype=int))
# root.start(TITLE, screen_size=array(BASE_SIZE) * 2)

# %%
# Setup Game's Content

# Loading Resources
ROOT_DIR: str = path.dirname(__file__)
ASSETS_DIR: str = path.join(ROOT_DIR, 'assets')
SPRITES_DIR: str = path.join(ASSETS_DIR, 'sprites')
SOUNDS_DIR: str = path.join(ASSETS_DIR, 'sounds')
DEFAULT_FONT: font.Font = font.SysFont('roboto', 40, False, False)

spritesheet_data: dict[str, list[dict]] = fetch_spritesheet(
    path.join(SPRITES_DIR, 'sheet1.json'))


# %%
root.sprites_groups = {
    root.DEFAULT_GROUP: sprite.Group(),
    PLAYER_GROUP: sprite.Group(),
    ENEMY_GROUP: sprite.Group(),
}

spritesheet_old: Surface = pygame.image.load(
    path.join(SPRITES_DIR, 'dino.png'))
spritesheet: Surface = pygame.image.load(
    path.join(SPRITES_DIR, 'sheet1.png')
)

# Sound Streams
death_sfx: Sound = Sound(path.join(SOUNDS_DIR, 'death.wav'))
jump_sfx: Sound = Sound(path.join(SOUNDS_DIR, 'jump.wav'))
score_sfx: Sound = Sound(path.join(SOUNDS_DIR, 'score.wav'))


# %%
# Nodes Setup
FLOOR_COORD: float = root._screen_height - CELL_SIZE * SPRITES_SCALE[Y]

bg: BackGround = BackGround(spritesheet_old, 3)
spawner: Spawner = Spawner(FLOOR_COORD, spritesheet_old, speed=bg.scroll_speed)
# spawn: Spawn = Spawn(coords=(randint(0, root._screen_width), randint(0, root._screen_height)))

player: Player = Player(spritesheet, spritesheet_data, score_sfx, death_sfx, coords=array(
    [root._screen_width // 2, FLOOR_COORD + CELL_SIZE // 2]) + (16, 16))
# player: Player = Player(coords=(root._screen_width // 2, root._screen_height // 2))
player.scale = array(SPRITES_SCALE)

# GUI
MAX_KEY_ITEMS: int = 10

# label: Label = Label((240, 240), color=colors.BLACK, text='Points: 0')

# Bars
BAR_THICKNESS: int = 25
BAR_OFFSET: tuple = BAR_THICKNESS, BAR_THICKNESS
TAG_FONTS: font.Font = font.SysFont('roboto', 20, False, False)
bar: ProgressBar = ProgressBar(coords=(BAR_OFFSET[X] * 3, BAR_OFFSET[Y]), size=(
    root._screen_width - BAR_OFFSET[X] * 4, BAR_THICKNESS))
o2_bar: ProgressBar = ProgressBar(name='O2Bar', coords=(
    BAR_OFFSET[X], BAR_OFFSET[Y] * 2), v_grow=True,
    size=(BAR_THICKNESS, root._screen_height - BAR_OFFSET[Y] * 3))
o2_label: Label = Label(TAG_FONTS, name='O2Label',
                        coords=BAR_OFFSET, color=colors.CYAN, text='O²')
nl2_bar: ProgressBar = ProgressBar(name='Nl2Bar', coords=(
    int(BAR_OFFSET[X] * 3.5), BAR_OFFSET[Y] * 3), size=(BAR_THICKNESS * 7, BAR_THICKNESS))
nl2_label: Label = Label(TAG_FONTS, name='Nl2Label', coords=nl2_bar.position +
                         (nl2_bar.size[X], 0), color=colors.BLUE, text='NL²')

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
        item: Sprite = Sprite(name=f'Item{i}', atlas=Icon(item_textures))
        item.anchor = array(TOP_LEFT)
        key_items.add_child(item)

else:
    warnings.warn('color not found')

display: GameOverDisplay = GameOverDisplay(DEFAULT_FONT)


# %%
# Construção da árvore
root.add_child(bg)
# root.add_child(spawn)
root.add_child(player)
root.add_child(spawner)
# root.add_child(label)
root.add_child(o2_label)
root.add_child(nl2_label)
root.add_child(bar)
root.add_child(o2_bar)
root.add_child(nl2_bar)
root.add_child(key_items)
root.add_child(display)

# Conexões
# spawn.connect(spawn.collected, score_sfx, score_sfx.play)
# player.connect(player.points_changed, label, label.set_text)
player.connect(player.scored, bg, bg.speed_up)
player.connect(player.scored, spawner, spawner.speed_up)
player.connect(player.died, display, display.show)
display.connect(display.game_resumed, spawner, spawner._on_Game_resumed)
display.connect(display.game_resumed, player, player._on_Game_resumed)


# %%
# Runs the Engine
root.run()
