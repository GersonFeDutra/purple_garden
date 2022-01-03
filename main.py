import json
import locale

from os import path
from pygame.mixer import Sound
from src.core.nodes import *
from src.game.scenes.game_world import GameWorld
from src.game.scenes.title_screen import TitleScreen
from src.game.consts import *


def fetch_spritesheet(from_path: str) -> dict[str, list[dict]]:
    '''Função auxiliar para importar dados de uma spritesheet
    a partir de um arquivo JSON criado no editor Aseprite.'''
    print("Started reading spritesheet JSON file...")

    with open(from_path, 'r') as read_file:
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


def fetch_locales(dir: str, locale: str) -> dict[str, str]:
    '''Função auxiliar para importar traduções de strings
    a partir de um arquivo JSON criado no editor Aseprite.'''
    print("Started reading locales JSON file...")
    locales: dict[str, str]

    with open(path.join(dir, f'{locale}.json'), 'r') as read_file:
        print("Starting to convert JSON decoding...")
        locales = json.load(read_file)
        print("Decoded JSON Data From File...")

    return locales


def filter_locale(from_key: str) -> str:
    '''Verifica se a chave passada está presente nas traduções disponíveis.'''
    key: str = from_key[:2]

    if key in ['pt', 'en']:
        return key

    return 'en'  # Fallback to english


def main(*args) -> None:
    '''Setups the engine and runs the game.'''

    # Setup Game's Content

    # Loading Resources
    ROOT_DIR: str = path.dirname(__file__)
    ASSETS_DIR: str = path.join(ROOT_DIR, 'assets')
    LOCALES_DIR: str = path.join(ASSETS_DIR, 'locales')
    SPRITES_DIR: str = path.join(ASSETS_DIR, 'sprites')
    SOUNDS_DIR: str = path.join(ASSETS_DIR, 'sounds')
    FONTS_DIR: str = path.join(ASSETS_DIR, 'fonts')

    GUI_FONT: font.Font = font.SysFont('roboto', 20, False, False)
    DEFAULT_FONT: font.Font = font.SysFont('roboto', 40, False, False)
    TITLE_FONT: font.Font = font.SysFont('roboto', 90, False, False)
    PIXELATED_FONT: str = path.join(
        FONTS_DIR, 'basis33', 'basis33.ttf')
    GUI_FONT: font.Font = font.Font(PIXELATED_FONT, 20)
    DEFAULT_FONT: font.Font = font.Font(PIXELATED_FONT, 40)
    TITLE_FONT: font.Font = font.Font(PIXELATED_FONT, 90)

    # Setup the Engine
    root.start(TITLE, screen_size=BASE_SIZE * array(
        SPRITES_SCALE, dtype=int), gui_font=GUI_FONT)

    # Locales
    lang: str

    try:
        cmd: Union[tuple, list] = args if args else argv
        lang = filter_locale(cmd[cmd.index('-l') + 1]) if '-l' in cmd else None
    except IndexError:
        lang = None

    if lang is None:
        lang = filter_locale(locale.getdefaultlocale()[0][:2])

    root.set_load_method(fetch_locales, LOCALES_DIR)
    root.set_locale(lang)

    # SpriteSheet
    spritesheet_data: dict[str, list[dict]] = fetch_spritesheet(
        path.join(SPRITES_DIR, 'sheet1.json'))

    root.sprites_groups = {
        root.DEFAULT_GROUP: sprite.Group(),
        PLAYER_GROUP: sprite.Group(),
        ENEMY_GROUP: sprite.Group(),
    }
    spritesheet: Surface = pygame.image.load(
        path.join(SPRITES_DIR, 'sheet1.png')
    )
    title_screen: Surface = pygame.image.load(
        path.join(SPRITES_DIR, 'title_screen.png')
    )

    # Sound Streams
    sound_fxs: dict[str, Sound] = {}

    # TODO -> Remover sons
    for sfx in ['death', 'score', 'jump']:
        sound_fxs[sfx] = Sound(path.join(SOUNDS_DIR, f'{sfx}.wav'))

    # Sets the first scene.
    root.current_scene = debug_call(
        lambda: TitleScreen(
            title_screen, spritesheet, spritesheet_data,
            sound_fxs, DEFAULT_FONT, GUI_FONT, TITLE_FONT),
        lambda: GameWorld(
            spritesheet, spritesheet_data,
            sound_fxs, DEFAULT_FONT, GUI_FONT)
    )()

    # Runs the Engine
    root.run()


if __name__ == '__main__':
    main()
