from pygame import draw
from pygame import Surface
from pygame import Color
from numpy import array
from .vectors import X, Y

'''Global Helper "Static" Methods'''

def lerp(_from_: float, _to_: float, _delta_: float) -> float:
    '''Realiza uma interpolação linear de `_from_` para `_to_` em termos de `_delta_`.'''
    return (_from_ - _to_) * _delta_


def draw_bounds(at: Surface, target_pos: array, extents: array,
                anchor: array, color: Color, fill=False) -> None:

    minor: array = target_pos - extents * anchor
    major: array = target_pos + extents * (1.0 - anchor)
    points: tuple = (
        (minor[X], minor[Y]), (major[X], minor[Y]),
        (major[X], major[Y]), (minor[X], major[Y])
    )

    # TODO -> Permitir alpha
    if fill:
        draw.polygon(at, color, points)
    else:
        for i in range(4):
            draw.line(at, color, points[i], points[(i + 1) % 4])
