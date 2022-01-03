from random import randint
from src.core.nodes import *
from ..utils import get_icon_sequence_slice
from .chars import Player
from .plants import Plant, OxTree


class TemporaryBar(ProgressBar):
    finished: Node.Signal
    duration: float = 1.0
    _elapsed_time: float = 0.0

    def _process(self) -> None:
        self._elapsed_time += root.delta

        if self._elapsed_time >= self.duration:
            self.finished.emit()
            self._parent.remove_child(self)

    def set_progress(self, value: float) -> None:
        super().set_progress(value)
        self._elapsed_time = 0.0
        self.finished = Node.Signal(self, 'finished')


class Tile(Icon):
    '''Um ícone que contém informações relevantes na jogabilidade. Usado como uma célula do mapa.'''
    is_planting: bool = False
    is_occupied: bool = False
    grow_progress: float = 0.0
    plant: Plant = None


class GroundGrid(TileMap):
    _Tile: type[Tile] = Tile
    HOLD_EVENT: str = 'hold'
    RELEASE_EVENT: str = 'release'

    map_size: tuple[int, int]
    marker: Sprite
    gardener: Player
    spritesheet: Surface
    spritesheet_data: dict[str, list[dict]]

    _plants: int = 0  # Plantas spawnadas
    _selected_tile_coords: tuple[int, int] = None
    _selected_tile: Tile = None
    _is_on_hold: bool = False
    _active_bars: dict[tuple[int, int], TemporaryBar]

    def _enter_tree(self) -> None:
        super()._enter_tree()

        # Spawn `OxTree`
        self.spawn_plant(OxTree, array(self.map_size) // 2)

    def _process(self) -> None:
        tile_coords: tuple[int, int] = self.screen_to_map(*mouse.get_pos())
        self.marker.position = tile_coords * self.tile_size * self._global_scale
        self.marker.atlas.set_texture(
            int(self.get_tile(*tile_coords).is_occupied))
        tile: Tile = self._selected_tile

        if not self._is_on_hold:
            return

        if self.gardener.hand_item is not None and \
                (self._selected_tile_coords == tile_coords).all():

            if self._selected_tile.is_occupied:
                pass
                # Harvest
            else:
                tile.grow_progress += root.delta
                self._display_loading_bar(
                    tuple(tile_coords), tile.grow_progress)

                if self._selected_tile.grow_progress >= 1.0:
                    tile.plant = self.spawn_plant(
                        self.gardener.hand_item, tile_coords)
                    tile.is_occupied = True
                    self._is_on_hold = False
                    tile.grow_progress = 1.
        else:
            self._is_on_hold = False

    def _input_event(self, event: InputEvent) -> None:
        # Realiza ações no terreno selecionado.

        if event.tag is GroundGrid.HOLD_EVENT:

            if self.gardener.hand_item is None:
                # TODO -> Harvest
                return

            coords: tuple[int, int] = self.screen_to_map(*mouse.get_pos())
            tile: Tile = self.get_tile(*coords)

            if tile:
                if tile.is_occupied:
                    # TODO -> Harvest
                    return
                
                if self._selected_tile != tile and self._selected_tile is not None:
                    # Caso outro tile seja selecionado, zera o anterior.
                    self._selected_tile.grow_progress = 0.0

                # Seleciona um novo tile.
                self._selected_tile_coords = coords
                self._selected_tile = tile
                self._is_on_hold = True
        else:
            self._is_on_hold = False

    def disable_tile(self, x: int, y: int) -> None:
        tile: Tile = self.get_tile(x, y)

        if tile is None:
            return

        tile.is_occupied = True

    def _display_loading_bar(self, coords: tuple[int, int], value: float) -> None:
        bar: TemporaryBar = self._active_bars.get(coords)

        if bar is None:
            bar: TemporaryBar = TemporaryBar(
                f'TemporaryBar{coords}',
                self._global_position + array(coords) * self.tile_size * self._global_scale)
            bar.scale = 1 / self.scale
            bar.connect(bar.finished, self, self._remove_bar, coords)
            self.add_child(bar)
            self._active_bars[coords] = bar

        bar.progress = value

    def _remove_bar(self, at: tuple[int, int]) -> None:
        self._active_bars.pop(at)

    def set_tile_area(
            self, tile: Tile, from_col: int,  from_row: int, to_col: int, to_row: int) -> None:

        for i in range(from_col, to_col):
            for j in range(from_row, to_row):
                new_tile: Tile = Tile(tile.textures)
                # Randomiza o terreno
                new_tile.set_texture(randint(0, len(tile.textures) - 1))
                self.set_tile(new_tile, i, j)

        self._update_tiles()

    def spawn_plant(self, plant: type[Plant], at: tuple[int, int]) -> None:

        spawn: plant = plant(self.spritesheet, self.spritesheet_data, coords=array(
            at) * self._tile_size * self._global_scale, name=f'Plant{self._plants}')
        self._plants += 1
        self.add_child(spawn)
        # Se torna ocupada

    def spawn_object(self, object: Node, at: tuple[int, int]) -> None:
        object.position = array(at) * self._tile_size * self._global_scale
        self.add_child(object)

    def get_random_edge_spot(self, offset: tuple[int, int] = (0, 0)) -> tuple[int, int]:

        if randint(0, 1):
            # Top | Bottom
            side_flipper: int = randint(0, 1)
            return randint(offset[X], self.map_size[X] - offset[X] - 1), (side_flipper * self.map_size[Y]) + offset[Y] - 2 * offset[Y] * side_flipper
        else:
            # Left Z Right
            side_flipper: int = randint(0, 1)
            return (side_flipper * self.map_size[X]) + offset[X] - 2 * offset[X] * side_flipper, randint(offset[Y], self.map_size[Y] - offset[Y] - 1)

    def __init__(self, map_size: tuple[int, int], tile_size: tuple[int, int],
                 scale: tuple[int, int], spritesheet: Surface,
                 spritesheet_data: dict[str, list[dict]], gardener: Player,
                 name: str = 'GroundGrid', coords: tuple[int, int] = VECTOR_ZERO) -> None:
        super().__init__(tile_size, name=name, coords=coords)
        self._active_bars = {}
        self.use_y_sort = True
        self.color = Color('#663649')
        self.scale = array(scale)
        self.gardener = gardener
        self.spritesheet = spritesheet
        self.spritesheet_data = spritesheet_data
        self.map_size = map_size

        ground: Tile = Tile(get_icon_sequence_slice(
            spritesheet, spritesheet_data, self.color))
        ground.set_texture(0)

        self.textures = ground.textures
        self.set_tile_area(ground, 0, 0, *map_size)
        self.set_tile_id(0, 0, 1)

        # Selection
        marker_icon: Tile = Tile(get_icon_sequence_slice(
            spritesheet, spritesheet_data, Color('#bde5a5')))
        marker_icon.set_texture(0)
        marker: Sprite = Sprite('Marker', atlas=marker_icon)
        marker.anchor = array(TOP_LEFT)
        self.marker = marker
        self.add_child(marker)

        input.register_event(
            self, MOUSEBUTTONDOWN, Input.Mouse.LEFT_CLICK, GroundGrid.HOLD_EVENT)
        input.register_event(
            self, MOUSEBUTTONUP, Input.Mouse.LEFT_CLICK, GroundGrid.RELEASE_EVENT)
