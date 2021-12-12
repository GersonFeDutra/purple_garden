from src.core.nodes import *
from ..consts import CELL, CELL_SIZE, SPRITES_SCALE
from ..utils import get_icon_sequence_slice


class GroundGrid(TileMap):
    marker: Sprite

    def _enter_tree(self) -> None:
        super()._enter_tree()
        self._global_position = super().get_global_position()

    def _input(self) -> None:
        self.marker.position = self.screen_to_map(
            *mouse.get_pos()) * self.tile_size * self._global_scale

    def _input_event(self, event: InputEvent) -> None:
        # Realiza ações no terreno selecionado
        coords: tuple[int, int] = self.screen_to_map(*mouse.get_pos())
        tile: Icon = self.get_tile(*coords)

        if tile:
            self.set_tile_id(
                *coords, (tile.texture_id + 1) % len(tile.textures))

    def screen_to_map(self, x, y) -> tuple[int, int]:
        '''Converte uma posição na tela em um ponto do mapa.'''
        tile_size: array = self.tile_size * self._global_scale

        return array(((x, y) + (self._global_position - self._layer.offset())) // tile_size, int)

    def get_global_position(self) -> tuple[int, int]:
        return self._global_position

    def __init__(self, map_size: tuple[int, int], tile_size: tuple[int, int], scale: tuple[int, int],
                 spritesheet: Surface, spritesheet_data: dict[str, list[dict]],
                 name: str = 'GroundGrid', coords: tuple[int, int] = VECTOR_ZERO) -> None:
        super().__init__(tile_size, name=name, coords=coords)
        self._global_position: array = self.position
        self.color = Color('#663649')
        self.scale = array(scale)

        ground: Icon = Icon(get_icon_sequence_slice(
            spritesheet, spritesheet_data, self.color))
        ground.set_texture(0)

        self.textures = ground.textures
        self.set_tile_area(ground, 0, 0, *map_size)
        self.set_tile_id(0, 0, 1)

        marker: Sprite = Sprite('Marker', atlas=Icon(
            get_icon_sequence_slice(spritesheet, spritesheet_data, Color('#bde5a5'))))
        marker.anchor = array(TOP_LEFT)
        self.marker = marker
        self.add_child(marker)

        input.register_event(self, MOUSEBUTTONDOWN,
                             Input.Mouse.LEFT_CLICK, 'clicked')
