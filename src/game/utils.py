from pygame import Color, Surface, Vector2
from numpy import array
from src.core.nodes import Atlas, AtlasBook, Icon
from src.core.lib.utils import push_warning


def animation_slice(
        spritesheet: Surface, data: dict[str, list[dict]], tag: Color, atlas: Atlas) -> None:
    '''Cria as animações do atlas com base nos dados da spritesheet.'''
    slices: list[dict] = data.get(str(tag))

    if not slices:
        push_warning('spritesheet load error', SpriteSheetLoadError)
        return

    slice: dict = slices[0]
    bounds: dict[str, int] = slice['keys'][0]['bounds']
    h_slices: int
    v_slices: int
    h_slices, v_slices = array(slice['data'].split(','), dtype=int)

    atlas.add_spritesheet(
        spritesheet, h_slice=h_slices, v_slice=v_slices, coords=(
            bounds['x'], bounds['y']),
        sprite_size=(bounds['w'] / h_slices, bounds['h'] / v_slices))


def spritesheet_slice(
        spritesheet: Surface, data: dict[str, list[dict]], tag: Color, atlas: AtlasBook) -> None:
    '''Cria as animações do atlas com base nos dados da spritesheet.'''
    slices: list[dict] = data.get(str(tag))

    if not slices:
        push_warning('spritesheet load error', SpriteSheetLoadError)
        return

    for slice in slices:
        bounds: dict[str, int] = slice['keys'][0]['bounds']
        h_slices: int
        v_slices: int
        h_slices, v_slices = array(slice['data'].split(','), dtype=int)

        atlas.add_animation(
            slice['name'], spritesheet, h_slice=h_slices, v_slice=v_slices,
            coords=(bounds['x'], bounds['y']), sprite_size=(
                bounds['w'] / h_slices, bounds['h'] / v_slices))


def get_icon_sequence_slice(
        spritesheet: Surface, data: dict[str, list[dict]], tag: Color, from_slice: int = 0) -> list[Surface]:
    '''Cria uma sequência de texturas para o ícone dado.'''
    slices: list[dict] = data.get(str(tag))

    if not slices:
        push_warning('spritesheet load error', SpriteSheetLoadError)
        return

    slice: int = slices[from_slice]
    bounds: dict[str, int] = slice['keys'][0]['bounds']
    h_slices: int
    v_slices: int
    h_slices, v_slices = array(slice['data'].split(','), dtype=int)

    return Icon.get_spritesheet(spritesheet, h_slice=h_slices, v_slice=v_slices, coords=(
        bounds['x'], bounds['y']), sprite_size=(bounds['w'] / h_slices, bounds['h'] / v_slices))


class SpriteSheetLoadError(Warning):
    '''Fail loading SpriteSheet. Color code do not match.'''


class Steering():
    DEFAULT_MASS: float = 2.0
    DEFAULT_MAX_SPEED: float = .4
    DEFAULT_SLOW_RADIUS: float = .2
    SLOW_OFFSET_ADD: float = 0.2
    SLOW_OFFSET_FACTOR: float = 0.8

    @staticmethod
    def follow(
            velocity: Vector2, global_position: Vector2, target_position: Vector2,
            max_speed: float = DEFAULT_MAX_SPEED, mass: float = DEFAULT_MASS) -> Vector2:
        desired_velocity: Vector2 = (
            target_position - global_position).normalize() * max_speed
        steering: Vector2 = (desired_velocity - velocity) / mass

        return velocity + steering

    @staticmethod
    def arrive_to(
            velocity: Vector2, global_position: Vector2, target_position: Vector2,
            max_speed: float = DEFAULT_MAX_SPEED, slow_radius: float = DEFAULT_SLOW_RADIUS,
            mass: float = DEFAULT_MASS) -> Vector2:
        to_target: float = global_position.distance_to(target_position)
        desired_velocity: Vector2 = (
            target_position - global_position).normalize() * max_speed
        steering: Vector2

        if to_target < slow_radius:
            desired_velocity *= (to_target / slow_radius) * \
                Steering.SLOW_OFFSET_FACTOR + Steering.SLOW_OFFSET_ADD

        steering = (desired_velocity - velocity) / mass
        return velocity + steering
