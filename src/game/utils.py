import warnings
from pygame import Color, Surface, sprite
from pygame.key import name
from src.core.nodes import Atlas, AtlasBook, Icon


def spritesheet_slice(
        spritesheet: Surface, data: dict[str, list[dict]], tag: Color, atlas: AtlasBook) -> None:
    '''Cria as animações do atlas com base nos dados da spritesheet.'''
    slices: list[dict] = data.get(str(tag))

    if not slices:
        warnings.warn('spritesheet load error', SpriteSheetLoadError)
        return

    for slice in slices:
        bounds: dict[str, int] = slice['keys'][0]['bounds']
        v_slices: int = int(slice['data'])

        atlas.add_animation(slice['name'], spritesheet, v_slice=v_slices, coords=(
            bounds['x'], bounds['y']), sprite_size=(bounds['w'], bounds['h'] / v_slices))


def get_icon_sequence_slice(spritesheet: Surface, data: dict[str, list[dict]], tag: Color) -> None:
    '''Cria uma sequência de texturas para o ícone dado.'''
    slices: list[dict] = data.get(str(tag))

    if not slices:
        warnings.warn('spritesheet load error', SpriteSheetLoadError)
        return

    slice: int = slices[0]
    bounds: dict[str, int] = slice['keys'][0]['bounds']
    v_slices: int = int(slice['data'])

    return Icon.get_spritesheet(spritesheet, v_slice=v_slices, coords=(bounds['x'], bounds['y']),
                                sprite_size=(bounds['w'], bounds['h'] / v_slices))


class SpriteSheetLoadError(Warning):
    '''Fail loading SpriteSheet. Color code do not match.'''
