from pygame import Surface, sprite
from pygame.key import name
from src.core.nodes import Atlas, AtlasBook


def spritesheet_slice(spritesheet: Surface, data: list[dict], atlas: AtlasBook) -> None:
    '''Cria as animações do atlas com base nos dados da spritesheet.'''

    for slice in data:
        bounds: dict[str, int] = slice['keys'][0]['bounds']
        n_slices: int = int(slice['data'])

        atlas.add_animation(slice['name'], spritesheet, v_slice=n_slices, coords=(
            bounds['x'], bounds['y']), sprite_size=(bounds['w'], bounds['h'] / n_slices))
