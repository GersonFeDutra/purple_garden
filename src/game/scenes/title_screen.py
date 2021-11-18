from pygame.mixer import Sound
from src.core.nodes import *
from .game_world import GameWorld


class TitleScreen(Node):
    START_GAME_EVENT: str = 'start_game'
    spritesheet_old: Surface
    spritesheet: Surface
    spritesheet_data: dict[str, list[dict]]
    sound_fxs: dict[str, Sound]
    gui_font: font.Font

    def _input_event(self, event: InputEvent) -> None:

        if event.tag is TitleScreen.START_GAME_EVENT:
            root.current_scene = GameWorld(self.spritesheet_old, self.spritesheet,
                                           self.spritesheet_data, self.sound_fxs, self.gui_font)

    def __init__(self, spritesheet_old: Surface, spritesheet: Surface,
                 spritesheet_data: dict[str, list[dict]], sound_fxs: dict[str, Sound],
                 gui_font: font.Font, title_font: font.Font, name: str = 'TitleScreen',
                 coords: tuple[int, int] = VECTOR_ZERO) -> None:
        super().__init__(name=name, coords=coords)
        self.spritesheet_old = spritesheet_old
        self.spritesheet = spritesheet
        self.spritesheet_data = spritesheet_data
        self.sound_fxs = sound_fxs
        self.gui_font = gui_font

        title: Label = Label(title_font, name='Title', coords=(array(root.screen_size) // 2)
                             - (0, 50), color=Color('#6E34B7'), text='Purple Garden')
        title.anchor = array(CENTER)
        info_label: Label = Label(gui_font, name='Info', coords=title.position + (
            0, 50), color=colors.GRAY, text='Press START to play!')
        info_label.anchor = array(CENTER)

        for key in [K_RETURN, K_SPACE, K_KP_ENTER]:
            input.register_event(self, KEYDOWN, key,
                                 TitleScreen.START_GAME_EVENT)

        self.add_child(title)
        self.add_child(info_label)
