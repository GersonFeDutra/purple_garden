from pygame.mixer import Sound
from src.core.nodes import *
from src.core.lib.colors import BLUE, DEFAULT_POPUP, GREEN, RED, WHITE
from .game_world import GameWorld


class TitleScreen(Node):

    class Events():
        KEY_UP_EVENT: str = 'key_up'
        KEY_DOWN_EVENT: str = 'key_down'
        ESCAPE_EVENT: str = 'escape'

    spritesheet: Surface
    spritesheet_data: dict[str, list[dict]]
    sound_fxs: dict[str, Sound]
    default_font: font.Font
    title_font: font.Font
    gui_font: font.Font

    selected_button: int
    buttons: list[Button]
    start_button: Button
    lang_button: Button
    exit_button: Button
    info_button: Button
    credits_button: Button

    info: list[str]
    info_label: Label

    on_focus: bool = True
    credits: Popup
    tuto: PopupDialog
    current_focus: Popup = None
    title_screen: Surface

    def _enter_tree(self) -> None:
        super()._enter_tree()
        # FIXME -> Verificar a necessidade dessa chamada.
        self._on_Locale_changed(root._locale)

    def _input_event(self, event: InputEvent) -> None:

        if self.on_focus:

            if event.tag is TitleScreen.Events.KEY_DOWN_EVENT:
                self.selected_button = (
                    self.selected_button + 1) % len(self.buttons)
                self.info_label.text = self.info[self.selected_button]
                self.buttons[self.selected_button].is_on_focus = True

            if event.tag is TitleScreen.Events.KEY_UP_EVENT:
                self.selected_button = (
                    self.selected_button - 1) % len(self.buttons)
                self.info_label.text = self.info[self.selected_button]
                self.buttons[self.selected_button].is_on_focus = True

        else:

            if event.tag is TitleScreen.Events.ESCAPE_EVENT:
                if self.current_focus is None:
                    self.on_focus = True
                    return

                self.current_focus.hide()

    def change_scene(self) -> None:

        if not self.on_focus:
            return

        root.clear_cached_locales()
        root.current_scene = GameWorld(
            self.spritesheet, self.spritesheet_data, self.sound_fxs,
            (TitleScreen, (self.title_screen, self.spritesheet, self.spritesheet_data,
            self.sound_fxs, self.default_font, self.gui_font, self.title_font), {}),
            self.default_font, self.gui_font)

    def _on_Language_pressed(self) -> None:
        LOCALES: tuple[str] = 'pt', 'en'
        root.set_locale(
            LOCALES[(LOCALES.index(root._locale) + 1) % len(LOCALES)])

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

        # Fecha o jogo
        pygame.quit()
        exit()

    def _on_Popup_hidden(self) -> None:

        self.remove_child(self.current_focus)
        self.current_focus = None
        self.on_focus = True

    def _on_Locale_changed(self, to: str) -> None:
        self.info = root.tr('INFOS')
        self.start_button.label.set_text(root.tr('START'))
        self.lang_button.label.set_text(root.tr('LANGUAGE'))
        self.info_button.label.set_text(root.tr('INFO'))
        self.credits_button.label.set_text(root.tr('CREDITS'))
        self.exit_button.label.set_text(root.tr('EXIT'))
        self.info_label.set_text(root.tr('INFOS')[self.selected_button])
        self.tuto.set_text(*root.tr('INFO_TXT'))
        self.on_focus = True

    def _on_Button_focus_changed(self, button_id: int, value: bool) -> None:

        if value:
            self.selected_button = button_id
            self.info_label.text = self.info[button_id]

    def __init__(self, title_screen: Surface, spritesheet: Surface,
                 spritesheet_data: dict[str, list[dict]], sound_fxs: dict[str, Sound],
                 default_font: font.Font, gui_font: font.Font, title_font: font.Font,
                 name: str = 'TitleScreen', coords: tuple[int, int] = VECTOR_ZERO) -> None:
        super().__init__(name=name, coords=coords)
        self.spritesheet = spritesheet
        self.spritesheet_data = spritesheet_data
        self.sound_fxs = sound_fxs
        self.default_font = default_font
        self.gui_font = gui_font
        self.buttons = []
        self.info = root.tr('INFOS')
        self.title_screen = title_screen
        self.title_font = title_font
        purple: Color = DEFAULT_POPUP

        # Title Screen
        # root.screen_color = Color('#6E34B7')
        bg: Sprite = Sprite('TitleScreen', atlas=Icon([title_screen]))
        bg.set_anchor(array(TOP_LEFT))
        # bg.scale = array(VECTOR_ONE)
        self.add_child(bg)

        Y_OFFSET: tuple = (0, 55)
        title: Label = Label(title_font, name='Title', coords=(
            array(root.screen_size) // 2) - array(Y_OFFSET) * 3,
            color=purple, text='Purple Garden')
        title.anchor = array(CENTER)
        copyright_label: Label = Label(gui_font, name='Copyright', coords=(
            root._screen_width // 2, root._screen_height - Y_OFFSET[Y]), color=colors.GRAY,
            text='© 2021 - GersonFeDutra')
        copyright_label.anchor = array(CENTER)
        info_label: Label = Label(gui_font, name='Info', coords=copyright_label.position - Y_OFFSET,
                                  color=colors.CYAN, text=root.tr('PRESS_TO_PLAY'))
        info_label.anchor = array(CENTER)
        self.info_label = info_label
        info_label.color = purple

        # h_box: HBox = HBox(name='Buttons', coords=array(
        #     root.get_screen_size()) // 2 + Y_OFFSET)
        # h_box.anchor = array(CENTER)

        # start_button: Button = Button(
        #     default_font, name=root.tr('START'), text=START)
        start_button: Button = Button(
            default_font, name='StartButton', coords=title.position +
            array(Y_OFFSET) * 2, anchor=CENTER, text=root.tr('START'))

        start_button.is_on_focus = True
        self.start_button = start_button
        self.selected_button = 0
        start_button.connect(start_button.pressed, self, self.change_scene)
        start_button.connect(
            start_button.focus_changed, self,
            self._on_Button_focus_changed, 0)
        self.buttons.append(start_button)

        # h_box.add_child(start_button)

        # WATCH
        lang_button: Button = Button(
            default_font, name='LangButton',
            coords=start_button.position + Y_OFFSET,
            anchor=CENTER, text=root.tr('LANGUAGE'))
        lang_button.connect(
            lang_button.pressed, self, self._on_Language_pressed)
        lang_button.connect(lang_button.focus_changed, self,
                            self._on_Button_focus_changed, 1)
        self.buttons.append(lang_button)
        self.lang_button = lang_button

        info_button: Button = Button(
            default_font, name='InfoButton', coords=lang_button.position + Y_OFFSET,
            anchor=CENTER, text=root.tr('INFO'))
        info_button.connect(info_button.pressed, self, self._on_Info_pressed)
        info_button.connect(
            info_button.focus_changed, self,
            self._on_Button_focus_changed, 2)
        self.buttons.append(info_button)
        self.info_button = info_button

        credits_button: Button = Button(
            default_font, name='Credits',
            coords=info_button.position + Y_OFFSET,
            anchor=CENTER, text=root.tr('CREDITS'))
        credits_button.connect(
            credits_button.pressed, self, self._on_Credits_pressed)
        self.credits_button = credits_button
        credits_button.connect(credits_button.focus_changed,
                               self, self._on_Button_focus_changed, 3)
        self.buttons.append(credits_button)

        exit_button: Button = Button(
            default_font, name='Exit',
            coords=credits_button.position + Y_OFFSET,
            anchor=CENTER, text=root.tr('EXIT'))
        exit_button.connect(
            exit_button.pressed, self, self._on_Exit_pressed)
        self.exit_button = exit_button
        exit_button.connect(exit_button.focus_changed, self,
                            self._on_Button_focus_changed, 4)
        self.buttons.append(exit_button)

        credits_popup: PopupDialog = PopupDialog(gui_font, name='CreditsPopup', coords=array(
            root.screen_size) // 2, anchor=CENTER, size=array(root.screen_size) // 3)
        credits_popup.connect(credits_popup.hided, self, self._on_Popup_hidden)
        credits_popup.set_text(*root.tr('CREDITS_TXT'))
        self.credits = credits_popup

        info_popup: PopupDialog = PopupDialog(gui_font, name='InfoPopup', coords=array(
            root.screen_size) // 2, anchor=CENTER, size=array(root.screen_size) // 2)
        info_popup.set_text(*root.tr('INFO_TXT'))
        info_popup.connect(info_popup.hided, self, self._on_Popup_hidden)
        self.tuto = info_popup

        for button in self.buttons:
            button.focus_color = purple.lerp(GREEN, .5)
            button.normal_color = purple
            button.panel.bg.color = purple
            button.highlight_color = purple.lerp(BLUE, .5)
            button.pressed_color = purple.lerp(Color(255, 100, 0), .5)
            button.label.color = WHITE
            button.panel.borders.color = WHITE

        input.register_event(
            self, KEYDOWN, K_UP, TitleScreen.Events.KEY_UP_EVENT)
        input.register_event(
            self, KEYDOWN, K_DOWN, TitleScreen.Events.KEY_DOWN_EVENT)
        input.register_event(
            self, KEYDOWN, K_ESCAPE, TitleScreen.Events.ESCAPE_EVENT)
        input.register_event(
            self, MOUSEBUTTONUP, Input.Mouse.RIGHT_CLICK, TitleScreen.Events.ESCAPE_EVENT)

        # Construção da tela
        self.add_child(title)
        self.add_child(info_label)

        self.add_child(start_button)
        self.add_child(lang_button)
        self.add_child(info_button)
        self.add_child(credits_button)
        self.add_child(exit_button)

        # self.add_child(h_box)
        self.add_child(copyright_label)

        # Sinais
        root.connect(root.locale_changed, self, self._on_Locale_changed)
