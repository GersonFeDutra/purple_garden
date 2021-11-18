from src.core.nodes import *


class GameOverDisplay(Node):
    RESTART: str = 'restart'
    label: Label
    game_resumed: Node.Signal

    def _input_event(self, event: InputEvent) -> None:
        global root
        # if event.tag is self.RESTART:
        
        if root.tree_pause & Node.PauseModes.TREE_PAUSED:
            self.remove_child(self.label)
            self.game_resumed.emit()
            root.pause_tree(0)

    def show(self) -> None:
        self.add_child(self.label)

    def __init__(self, font: font.Font, name: str = 'GameOverDisplay', coords: tuple[int, int] = VECTOR_ZERO) -> None:
        global root
        super().__init__(name=name, coords=coords)

        self.label = Label(font, coords=array(root.screen_size) // 2,
                           color=colors.BLACK, text='Game Over')
        self.label.anchor = CENTER
        # self.label.position = array(SCREEN_SIZE) // 2 - \
        #     array(self.label.update_surface().get_size()) // 2

        input.register_event(self, KEYDOWN, K_SPACE, self.RESTART)
        self.game_resumed = Node.Signal(self, 'game_resumed')
