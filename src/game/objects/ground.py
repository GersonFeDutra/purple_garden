from random import randint
from src.core.nodes import *
# from ..consts import CELL, CELL_SIZE, SPRITES_SCALE
from ..utils import get_icon_sequence_slice, spritesheet_slice


class TemporaryBar(ProgressBar):
    finished: Node.Signal
    duration: float = 1.0
    _elapsed_time: float = 0.0

    def _process(self, delta: float) -> None:
        self._elapsed_time += delta

        if self._elapsed_time >= self.duration:
            self.finished.emit()
            self._parent.remove_child(self)

    def set_progress(self, value: float) -> None:
        super().set_progress(value)
        self._elapsed_time = 0.0
        self.finished = Node.Signal(self, 'finished')


class Plant(Sprite):
    animation_idle: str
    animation_attack: str
    view_range: Body
    animations: AtlasBook

    _grow_stages: int = 3
    _current_stage: int = 0
    _grow_progress: float = 0.0
    _animation_speed: float = 0.1
    _stage_triggers: list[float] = None
    grow: Callable
    
    def _process(self, delta: float) -> None:
        self.grow()

    def _grow(self) -> None:
        self._grow_progress += root.delta_persec
        
        if self._grow_progress > self._stage_triggers[self._current_stage]:
            self._current_stage += 1
            atlas: Icon = self.atlas
            atlas.set_texture(self._current_stage)
            
            if self._current_stage >= self._grow_progress:
                self._grow_up()
                self.grow = NONE_CALL

    def _grow_up(self) -> None:
        self.atlas = self.animations

        if self.animation_idle is not None:
            self.atlas.set_current_animation(self.animation_idle)
            self.atlas._current_sequence.speed = self._animation_speed

    def __init__(self, color: Color, spritesheet: Surface, spritesheet_data: dict[str, list[dict]],
                 name: str = 'Plant', coords: tuple[int, int] = VECTOR_ZERO,
                 atlas: BaseAtlas = None, animation_idle: str = None, animation_atk: str = None,
                 from_slice: int = 0) -> None:
        atlas: Icon = Icon(get_icon_sequence_slice(
            spritesheet, spritesheet_data, color, from_slice=from_slice))
        super().__init__(name=name, coords=coords, atlas=atlas)
        self.anchor = array(TOP_LEFT)
        self.grow = self._grow
        self.color = color
        self.animation_idle = animation_idle
        self.animation_attack = animation_atk
        self.animations = AtlasBook()
        spritesheet_slice(spritesheet, spritesheet_data,
                          self.color, self.animations)

        self.view_range = Body('View')
        self.add_child(self.view_range)


class Rose(Plant):

    def __init__(self, spritesheet: Surface, spritesheet_data: dict[str, list[dict]],
                 name: str = 'Rose', coords: tuple[int, int] = VECTOR_ZERO,
                 atlas: BaseAtlas = None) -> None:
        super().__init__(Color('#fe5b59'), spritesheet, spritesheet_data, name=name, coords=coords,
                         atlas=atlas, animation_idle='rose_idle', animation_atk='rose_attack')
        self._stage_triggers = [10.0, 20.0, 30.0]


class Violet(Plant):

    def __init__(self, spritesheet: Surface, spritesheet_data: dict[str, list[dict]],
                 name: str = 'Violet', coords: tuple[int, int] = VECTOR_ZERO,
                 atlas: BaseAtlas = None) -> None:
        super().__init__(Color('#d186df'), spritesheet, spritesheet_data, name=name, coords=coords,
                         atlas=atlas, animation_idle='violet_idle', animation_atk='violet_attack')
        self._stage_triggers = [15.0, 30.0, 45.0]


class OxTree(Sprite):

    def __init__(self, spritesheet: Surface, spritesheet_data: dict[str, list[dict]], name: str = 'OxTree',
                 coords: tuple[int, int] = VECTOR_ZERO) -> None:
        super().__init__(name=name, coords=coords, atlas=Icon(get_icon_sequence_slice(
            spritesheet, spritesheet_data, Color('#159a42'))))
        self.anchor = array(TOP_LEFT)


class GroundGrid(TileMap):
    HOLD_EVENT: str = 'hold'
    RELEASE_EVENT: str = 'release'

    map_size: tuple[int, int]
    marker: Sprite
    gardener: Node
    spritesheet: Surface
    spritesheet_data: dict[str, list[dict]]

    _plants: int = 0 # Plantas spawnadas
    _selected_tile_coords: tuple[int, int] = None
    _selected_tile: Icon = None
    _is_on_hold: bool = False
    _active_bars: dict[tuple[int, int], TemporaryBar]

    def _enter_tree(self) -> None:
        super()._enter_tree()

        # Spawn OXTree
        self.spawn_plant(OxTree, array(self.map_size) // 2)

    def _process(self, delta: float) -> None:
        tile_coords: tuple[int, int] = self.screen_to_map(*mouse.get_pos())
        self.marker.position = tile_coords * self.tile_size * self._global_scale        
        self.marker.atlas.set_texture(int(self.get_tile(*tile_coords).is_occupied))
        tile: Icon = self._selected_tile

        if not self._is_on_hold:
            return

        if self.gardener.hand_item is not None and \
                (self._selected_tile_coords == tile_coords).all():
            
            if self._selected_tile.is_occupied:
                pass
                    # Harvest
            else:
                tile.grow_progress += delta / root.fixed_fps
                self._display_loading_bar(tuple(tile_coords), tile.grow_progress)

                if self._selected_tile.grow_progress >= 1.0:
                    tile.plant = self.spawn_plant(self.gardener.hand_item, tile_coords)
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
            tile: Icon = self.get_tile(*coords)


            if tile:
                if tile.is_occupied:
                    # TODO -> Harvest
                    return

                self._selected_tile_coords = coords
                self._selected_tile = tile
                self._is_on_hold = True
        else:
            self._is_on_hold = False

    def screen_to_map(self, x, y) -> tuple[int, int]:
        '''Converte uma posição na tela em um ponto do mapa.'''
        tile_size: ndarray = array(self.tile_size) * self._global_scale

        return array(((x, y) + (
            array(self._global_position) - self._layer.offset())) // tile_size, int)

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
            self, tile: Icon, from_col: int,  from_row: int, to_col: int, to_row: int) -> None:

        for i in range(from_col, to_col):
            for j in range(from_row, to_row):
                new_tile: Icon = Icon(tile.textures)
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

    def __init__(self, map_size: tuple[int, int], tile_size: tuple[int, int], scale: tuple[int, int],
                 spritesheet: Surface, spritesheet_data: dict[str, list[dict]], gardener: Node,
                 name: str = 'GroundGrid', coords: tuple[int, int] = VECTOR_ZERO) -> None:
        super().__init__(tile_size, name=name, coords=coords)
        self._active_bars = {}
        self.color = Color('#663649')
        self.scale = array(scale)
        self.gardener = gardener
        self.spritesheet = spritesheet
        self.spritesheet_data = spritesheet_data
        self.map_size = map_size

        ground: Icon = Icon(get_icon_sequence_slice(
            spritesheet, spritesheet_data, self.color))
        ground.set_texture(0)

        self.textures = ground.textures
        self.set_tile_area(ground, 0, 0, *map_size)
        self.set_tile_id(0, 0, 1)

        # Selection
        marker_icon: Icon = Icon(get_icon_sequence_slice(
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
