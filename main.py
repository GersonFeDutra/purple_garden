from os import listdir, mkdir, remove
import time
import json
import locale

from pygame.mixer import Sound
from src.core.nodes import *
from src.game.scenes.game_world import GameWorld
from src.game.scenes.title_screen import TitleScreen
from src.game.consts import *

LOG_FILE_PATH: str


def _log(*s: str, sep: str = '\n\t') -> None:
    print(f'\t{sep.join(s)}')


@debug_method(_log)
def log(*s: str, sep: str ='\n\t') -> None:
    '''Emite uma mensagem de log, direcionada de acordo com o modo de execução.'''
    if not path.exists(LOG_FILE_PATH):
        # Tries creating the file
        if not path.exists(root.user_dir): mkdir(root.user_dir)
        _log_dir: str = path.dirname(LOG_FILE_PATH)
        if not path.exists(_log_dir): mkdir(_log_dir)

        with open(LOG_FILE_PATH, 'w') as log_file:
            ...  # Creates empty file

    with open(LOG_FILE_PATH, 'a') as log_file:
        log_file.write(f'{time.asctime(time.localtime(time.time()))}:\n')
        log_file.write(f'\t{sep.join(s)}\n')


@debug_method
def dbglog(*s: str, sep: str ='\n\t') -> None:
    _log(s, sep)


def fetch_spritesheet(from_path: str) -> dict[str, list[dict]]:
    '''Função auxiliar para importar dados de uma spritesheet
    a partir de um arquivo JSON criado no editor Aseprite.'''
    log('Started reading spritesheet JSON file...')

    with open(from_path, 'r') as read_file:

        dbglog('Starting to convert JSON decoding...')
        sheet = json.load(read_file)

        dbglog('Decoded JSON data from File...')
        # log(sheet)
        # for key, value in sheet.items():
        #     log(key, ':', value)

        # log(sheet['frames'])
        # for key, value in sheet['frames'].items():
        # log(key, ':', value)

        # for key, value in refs.items():
        #     log(key, ' : ', sheet['frames'][key]['frame'])

        map: dict[str, list[dict]] = {}

        for slice in sheet['meta']['slices']:
            color: str = str(Color(slice['color']))

            if color in map:
                map[color].append(slice)
            else:
                map[color] = [slice]

        # log(map)

        log('Done reading JSON file...')
        return map


def fetch_locales(dir: str, locale: str) -> dict[str, str]:
    '''Função auxiliar para importar traduções de strings
    a partir de um arquivo JSON criado no editor Aseprite.'''
    log('Started reading locales JSON file...')
    locales: dict[str, str]

    with open(path.join(dir, f'{locale}.json'), 'r') as read_file:
        dbglog('Starting to convert JSON decoding...')
        locales = json.load(read_file)
        log('Decoded JSON Data From File...')

    return locales


def filter_locale(from_key: str) -> str:
    '''Verifica se a chave passada está presente nas traduções disponíveis.'''
    key: str = from_key[:2]

    if key in ['pt', 'en']:
        return key

    return 'en'  # Fallback to english


def main(*args) -> None:
    '''Setups the engine and runs the game.'''
    global LOG_FILE_PATH

    # Setup Game's Content

    # Paths
    ROOT_DIR: str = path.dirname(__file__)
    ASSETS_DIR: str = path.join(ROOT_DIR, 'assets')
    LOCALES_DIR: str = path.join(ASSETS_DIR, 'locales')
    SPRITES_DIR: str = path.join(ASSETS_DIR, 'sprites')
    SOUNDS_DIR: str = path.join(ASSETS_DIR, 'sounds')
    FONTS_DIR: str = path.join(ASSETS_DIR, 'fonts')
    ## Files
    PIXELATED_FONT_PATH: str = path.join(
        FONTS_DIR, 'basis33', 'basis33.ttf')


    # Setup the Engine
    root.start(TITLE, screen_size=BASE_SIZE * array(
        SPRITES_SCALE, dtype=int))


    # Set log-file location
    _log_dir = path.join(root.user_dir, 'log')
    LOG_FILE_PATH = path.join(_log_dir,
            time.asctime(time.localtime(time.time())).replace(' ', '_') ) + '.log'


    # Loading Resources

    ## Fonts
    GUI_FONT: font.Font
    DEFAULT_FONT: font.Font
    TITLE_FONT: font.Font
    try:
        GUI_FONT = font.Font(PIXELATED_FONT_PATH, 20)
        DEFAULT_FONT = font.Font(PIXELATED_FONT_PATH, 40)
        TITLE_FONT = font.Font(PIXELATED_FONT_PATH, 90)
    except FileNotFoundError:
        log(f'Font file [{PIXELATED_FONT_PATH}] not found! Trying to use fallback [roboto]:')
        GUI_FONT = font.SysFont('roboto', 20, False, False)
        DEFAULT_FONT = font.SysFont('roboto', 40, False, False)
        TITLE_FONT = font.SysFont('roboto', 90, False, False)

    # Cleans log folder
    # if path.exists(_log_dir):
    #     for f in listdir(_log_dir):
    #         if not f.endswith('.log'):
    #             continue
    #         remove(path.join(_log_dir, f))

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
        sfx_path: str = path.join(SOUNDS_DIR, f'{sfx}.wav')

        try:
            sound_fxs[sfx] = Sound(sfx_path)
        except FileNotFoundError:
            sound_fxs[sfx] = None
            log(f'Sound file [{sfx_path}] not found!')

    # Sets the first scene.
    root.current_scene = debug_call(
        lambda: TitleScreen(
            title_screen, spritesheet, spritesheet_data,
            sound_fxs, DEFAULT_FONT, GUI_FONT, TITLE_FONT),
        lambda: GameWorld(
            spritesheet, spritesheet_data,
            sound_fxs, (TitleScreen, (title_screen, spritesheet, spritesheet_data,
                                      sound_fxs, DEFAULT_FONT, GUI_FONT, TITLE_FONT), {}), DEFAULT_FONT, GUI_FONT)
    )()

    # Runs the Engine
    root.run()


if __name__ == '__main__':
    main()
