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
    _was_game_ended: bool = False
    RETURN: str = 'return'
    dialog: PopupDialog
    game_resumed: Node.Signal

    def show(self, addition_message: str = '') -> None:
        # Previne uma chamada adicional de `show` durante a animação de popup.
        if self._was_game_ended:
            return

        self._was_game_ended = True
        dialog: PopupDialog = PopupDialog(
            root.gui_font, name='GameOverDialog', coords=array(root.screen_size) // 2)
        dialog.set_anchor(CENTER)
        message: list = [addition_message] + root.tr('GAME_OVER')
        dialog.set_text(*message)
        self.dialog = dialog
        self.add_child(dialog)
        dialog.connect(dialog.hided, self, self._on_Dialog_closed)
        dialog.popup(True, True, True)

    def _on_Dialog_closed(self) -> None:
        self.dialog.free()
        root.pause(False)
        self.game_resumed.emit()

    def __init__(self, font: font.Font, name: str = 'GameOverDisplay', coords: tuple[int, int] = VECTOR_ZERO) -> None:
        global root
        super().__init__(name=name, coords=coords)
        self.game_resumed = Node.Signal(self, 'game_resumed')
        self.pause_mode = SceneTree.PauseModes.IGNORE
