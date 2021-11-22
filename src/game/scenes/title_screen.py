from pygame.mixer import Sound
from src.core.nodes import *
from .game_world import GameWorld


class TitleScreen(Node):
    START_GAME_EVENT: str = 'start_game'
    KEY_UP_EVENT: str = 'key_up'
    KEY_DOWN_EVENT: str = 'key_down'
    ESCAPE_EVENT: str = 'escape'

    spritesheet_old: Surface
    spritesheet: Surface
    spritesheet_data: dict[str, list[dict]]
    sound_fxs: dict[str, Sound]
    default_font: font.Font
    gui_font: font.Font

    selected_button: int
    buttons: list[Button]
    start_button: Button
    exit_button: Button
    info_button: Button
    credits_button: Button
    
    info: list[str]
    info_label: Label

    on_focus: bool = True
    credits: Popup
    tuto: Popup
    current_focus: Popup = None

    def _input_event(self, event: InputEvent) -> None:

        if self.on_focus:

            if event.tag is TitleScreen.START_GAME_EVENT:
                if self.buttons[self.selected_button] is self.start_button:
                    self.change_scene()
                elif self.buttons[self.selected_button] is self.info_button:
                    self._on_Info_pressed()
                elif self.buttons[self.selected_button] is self.credits_button:
                    self._on_Credits_pressed()
                elif self.buttons[self.selected_button] is self.exit_button:
                    self._on_Exit_pressed()

                self.on_focus = False

            if event.tag is TitleScreen.KEY_DOWN_EVENT:
                self.buttons[self.selected_button].is_on_focus = False
                self.selected_button = (
                    self.selected_button + 1) % len(self.buttons)
                self.info_label.text = self.info[self.selected_button]
                self.buttons[self.selected_button].is_on_focus = True

            if event.tag is TitleScreen.KEY_UP_EVENT:
                self.buttons[self.selected_button].is_on_focus = False
                self.selected_button = (
                    self.selected_button - 1) % len(self.buttons)
                self.info_label.text = self.info[self.selected_button]
                self.buttons[self.selected_button].is_on_focus = True

        else:

            if event.tag is TitleScreen.ESCAPE_EVENT:
                if self.current_focus is None:
                    self.on_focus = True
                    return

                self.current_focus.hide()

    def change_scene(self) -> None:

        if not self.on_focus:
            return

        root.clear_cached_locales()
        root.current_scene = GameWorld(
            self.spritesheet_old, self.spritesheet,
            self.spritesheet_data, self.sound_fxs, self.default_font, self.gui_font)

    # def _on_Languages_pressed(self) -> None:
    #     # TODO
    #     pass

    def _on_Language_pressed(self) -> None:
        pass

    def _on_Info_pressed(self) -> None:

        if not self.on_focus:
            return

        self.add_child(self.tuto)
        self.current_focus = self.tuto
        self.tuto.popup()
        self.on_focus = False

    def _on_Credits_pressed(self) -> None:

        if not self.on_focus:
            return

        self.add_child(self.credits)
        self.current_focus = self.credits
        self.credits.popup()
        self.on_focus = False

    def _on_Exit_pressed(self) -> None:

        if not self.on_focus:
            return

        pygame.quit()

    def _on_Popup_hidden(self) -> None:

        self.remove_child(self.current_focus)
        self.current_focus = None
        self.on_focus = True

    def _on_Locale_changed(self, to: str) -> None:
        self.info = root.tr('INFOS')

    def __init__(self, spritesheet_old: Surface, spritesheet: Surface,
                 spritesheet_data: dict[str, list[dict]], sound_fxs: dict[str, Sound],
                 default_font: font.Font, gui_font: font.Font, title_font: font.Font,
                 name: str = 'TitleScreen', coords: tuple[int, int] = VECTOR_ZERO) -> None:
        super().__init__(name=name, coords=coords)
        self.spritesheet_old = spritesheet_old
        self.spritesheet = spritesheet
        self.spritesheet_data = spritesheet_data
        self.sound_fxs = sound_fxs
        self.default_font = default_font
        self.gui_font = gui_font
        self.buttons = []
        self.info = root.tr('INFOS')
        
        root.screen_color = Color('#6E34B7')

        Y_OFFSET: tuple = (0, 55)
        title: Label = Label(title_font, name='Title', coords=(array(
            root.screen_size) // 2) - array(Y_OFFSET) * 2, color=colors.WHITE, text='Purple Garden')
        title.anchor = array(CENTER)
        copyright_label: Label = Label(gui_font, name='Copyright', coords=(
            root._screen_width // 2, root._screen_height - Y_OFFSET[Y]), color=colors.GRAY,
            text='© 2021 - GersonFeDutra')
        copyright_label.anchor = array(CENTER)
        info_label: Label = Label(gui_font, name='Info', coords=copyright_label.position - Y_OFFSET,
                                  color=colors.CYAN, text=root.tr('PRESS_TO_PLAY'))
        info_label.anchor = array(CENTER)
        self.info_label = info_label

        start_button: Button = Button(
            default_font, name='StartButton',
            coords=title.position + array(Y_OFFSET) * 2, text=root.tr('START'))
        start_button.set_anchor(CENTER)
        start_button.is_on_focus = True
        self.buttons.append(start_button)
        self.start_button = start_button
        self.selected_button = 0
        start_button.connect(start_button.pressed, self, self.change_scene)
        # h_box.add_child(start_button)

        # WATCH
        lang_button: Button = Button(
            default_font, name='LangButton',
            coords=start_button.position + Y_OFFSET, text=root.tr('LANGUAGE'))
        lang_button.set_anchor(CENTER)
        lang_button.connect(
            lang_button.pressed, self, self._on_Language_pressed)

        info_button: Button = Button(
            default_font, name='InfoButton',
            coords=start_button.position + Y_OFFSET, text=root.tr('INFO'))
        info_button.set_anchor(CENTER)
        info_button.connect(info_button.pressed, self, self._on_Info_pressed)
        self.buttons.append(info_button)
        self.info_button = info_button

        credits_button: Button = Button(
            default_font, name='Credits',
            coords=info_button.position + Y_OFFSET, text=root.tr('CREDITS'))
        credits_button.set_anchor(CENTER)
        credits_button.connect(
            credits_button.pressed, self, self._on_Credits_pressed)
        self.buttons.append(credits_button)
        self.credits_button = credits_button

        exit_button: Button = Button(
            default_font, name='Exit',
            coords=credits_button.position + Y_OFFSET, text=root.tr('EXIT'))
        exit_button.set_anchor(CENTER)
        exit_button.connect(
            exit_button.pressed, self, self._on_Exit_pressed)
        self.buttons.append(exit_button)
        self.exit_button = exit_button

        credits_popup: Popup = Popup(name='CreditsPopup', coords=array(
            root.screen_size) // 2, size=array(root.screen_size) // 3)
        credits_popup.anchor = array(CENTER)
        self.credits = credits_popup
        credits_popup.set_anchor(CENTER)
        credits_popup.connect(credits_popup.hided, self, self._on_Popup_hidden)

        rt_label: RichTextLabel = RichTextLabel(
            gui_font, 'CreditsText', color=colors.BLACK)
        rt_label.anchor = array(CENTER)
        rt_label.set_rich_text(*root.tr('CREDITS_TXT'))
        credits_popup.add_child(rt_label)

        info_popup: Popup = Popup(name='InfoPopup', coords=array(
            root.screen_size) // 2, size=array(root.screen_size) // 2)
        info_popup.connect(info_popup.hided, self, self._on_Popup_hidden)
        info_popup.set_anchor(CENTER)
        self.tuto = info_popup

        tuto_label: RichTextLabel = RichTextLabel(
            gui_font, name='TutorialText', color=colors.BLACK)
        tuto_label.anchor = array(CENTER)
        tuto_label.set_rich_text(*root.tr('INFO_TXT'))
        info_popup.add_child(tuto_label)

        label_tuto: Label = Label(gui_font, text=self.info[self.selected_button])
        label_tuto.anchor = array(CENTER)
        info_popup.add_child(label_tuto)

        # Registro dos eventos de entrada

        for key in (K_RETURN, K_SPACE, K_KP_ENTER):
            input.register_event(self, KEYDOWN, key,
                                 TitleScreen.START_GAME_EVENT)

        input.register_event(self, KEYDOWN, K_UP, TitleScreen.KEY_UP_EVENT)
        input.register_event(self, KEYDOWN, K_DOWN, TitleScreen.KEY_DOWN_EVENT)
        input.register_event(self, KEYDOWN, K_ESCAPE, TitleScreen.ESCAPE_EVENT)
        input.register_event(self, MOUSEBUTTONUP,
                             Input.Mouse.RIGHT_CLICK, TitleScreen.ESCAPE_EVENT)

        # Construção da tela
        self.add_child(title)
        self.add_child(info_label)

        self.add_child(start_button)
        self.add_child(info_button)
        self.add_child(credits_button)
        self.add_child(exit_button)

        # self.add_child(h_box)
        self.add_child(copyright_label)
        
        # Sinais
        root.connect(root.locale_changed, self, self._on_Locale_changed)
