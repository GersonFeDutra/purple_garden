from src.core.nodes import *


class KeyItems(Grid):
    '''Contêiner do tipo "grade" que apresenta e comanda uma lista de itens.'''
    max_value: int = 0

    def add_child(self, node: Node, at: int = -1) -> None:
        super().add_child(node, at=at)
        self.max_value += 1

    def remove_child(self, node=None, at: int = -1) -> Node:
        node: Node = super().remove_child(node=node, at=at)
        self.max_value -= 1

        return node

    def set_value(self, value: int) -> None:

        if value > self.max_value:
            return

        if value > self._value:
            for child in self._children_index[self._value: value + 1]:
                self.add_child(child)
        else:
            for child in self._children_index[value:]:
                self.remove_child(child)
        self._value = value

    def get_value(self) -> int:
        return self._value

    def __init__(self, name: str = 'Grid', coords: tuple[int, int] = VECTOR_ZERO, rows: int = 1) -> None:
        super().__init__(name=name, coords=coords, rows=rows)
        self._value = 0

    value: property = property(get_value, set_value)


class GameOverDisplay(Node):
    RETURN: str = 'return'
    dialog: PopupDialog
    game_resumed: Node.Signal

    def _input_event(self, event: InputEvent) -> None:
        global root
        # if event.tag is self.RESTART:

        if root.tree_pause & Node.PauseModes.TREE_PAUSED:
            self.remove_child(self.dialog)
            root.pause(False)
            self.game_resumed.emit()

    def show(self, addition_message: str = '') -> None:
        dialog: PopupDialog = PopupDialog(root.gui_font, name='GameOverDialog', coords=array(root.screen_size) // 2)
        dialog.set_anchor(CENTER)
        message: list = [addition_message] + root.tr('GAME_OVER')
        dialog.set_text(*message)
        self.dialog = dialog
        self.add_child(dialog)
        dialog.connect(dialog.hided, self, self._on_Dialog_closed)
        dialog.popup(True, True, True)

    def _on_Dialog_closed(self) -> None:
        self.dialog.free()
        self.game_resumed.emit()

    def __init__(self, font: font.Font, name: str = 'GameOverDisplay', coords: tuple[int, int] = VECTOR_ZERO) -> None:
        global root
        super().__init__(name=name, coords=coords)
        self.pause_mode = SceneTree.PauseModes.IGNORE

        self.dialog = Label(font, coords=array(root.screen_size) // 2,
                            color=colors.BLACK, text='Game Over')
        self.dialog.anchor = CENTER
        # self.label.position = array(SCREEN_SIZE) // 2 - \
        #     array(self.label.update_surface().get_size()) // 2

        input.register_event(self, KEYDOWN, K_SPACE, self.RETURN)
        self.game_resumed = Node.Signal(self, 'game_resumed')
