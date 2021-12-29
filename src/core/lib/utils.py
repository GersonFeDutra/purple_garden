from pygame import draw
from pygame import Surface
from pygame import Color
from numpy import ndarray

import typing
from typing import Generic
from warnings import warn as push_warning
from .vectors import X, Y


T = typing.TypeVar('T') # TypeVar usado na metaclasse `Generic`.
# Ao definir o sub-tipo da classe genérica, usando a sintaxe de tipagem `[T]`,
# a IDE responderá aquele tipo associado.


# Global Helper "Static" Methods
def lerp(_from_: float, _to_: float, _delta_: float) -> float:
    '''Realiza uma interpolação linear de `_from_` para `_to_` em termos de `_delta_`.'''
    return (_from_ - _to_) * _delta_


def clamp(from_min, value, to_max):
    return min(max(from_min, value), to_max)


def draw_bounds(at: Surface, target_pos: ndarray, extents: ndarray,
                anchor: ndarray, color: Color, fill=False) -> None:

    minor: ndarray = target_pos - extents * anchor
    major: ndarray = target_pos + extents * (1.0 - anchor)
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
