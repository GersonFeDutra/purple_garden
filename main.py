import json

from pygame.image import load
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
root.start(TITLE)

# %%
# Setup Game's Content

# Loading Resources
ROOT_DIR: str = path.dirname(__file__)
ASSETS_DIR: str = path.join(ROOT_DIR, 'assets')
SPRITES_DIR: str = path.join(ASSETS_DIR, 'sprites')
SOUNDS_DIR: str = path.join(ASSETS_DIR, 'sounds')

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
label: Label = Label((40, 40), color=colors.BLACK, text='Points: 0')
display: GameOverDisplay = GameOverDisplay()


# %%
# Construção da árvore
root.add_child(bg)
# root.add_child(spawn)
root.add_child(player)
root.add_child(spawner)
root.add_child(label)
root.add_child(display)

# Conexões
# spawn.connect(spawn.collected, score_sfx, score_sfx.play)
player.connect(player.points_changed, label, label.set_text)
player.connect(player.scored, bg, bg.speed_up)
player.connect(player.scored, spawner, spawner.speed_up)
player.connect(player.died, display, display.show)
display.connect(display.game_resumed, spawner, spawner._on_Game_resumed)
display.connect(display.game_resumed, player, player._on_Game_resumed)


# %%
# Runs the Engine
root.run()
