from ..utils import animation_slice
from ..consts import PhysicsLayers
from src.core.nodes import *


def make_sprite(spritesheet: Surface, spritesheet_data: dict[str, list[dict]], color: Color, name='Sprite') -> Sprite:
    atlas: AtlasPage = AtlasPage()
    sprite: Sprite = Sprite(atlas=atlas, name=name)
    animation_slice(spritesheet, spritesheet_data, color, atlas)
    return sprite


class Prop(StaticBody):
    sprite: Sprite

    def __init__(self, spritesheet: Surface, spritesheet_data: dict[str, list[dict]],
                 name: str = 'Prop', coords: tuple[int, int] = VECTOR_ZERO,
                 color: Color = Color('#0d89c6')) -> None:
        super().__init__(name=name, coords=coords, color=color)
        self.collision_mask = PhysicsLayers.NATIVES_BODIES
        # Set the Sprite
        self.sprite = make_sprite(spritesheet, spritesheet_data, color)
        self.add_child(self.sprite)


class Ship(Prop):
    
    def __init__(self, spritesheet: Surface, spritesheet_data: dict[str, list[dict]],
                 name: str = 'Ship', coords: tuple[int, int] = VECTOR_ZERO,
                 color: Color = Color('#394b5a')) -> None:
        super().__init__(spritesheet, spritesheet_data, name=name, coords=coords, color=color)
        
        # Set `Sprite` child
        antenna: Sprite = make_sprite(spritesheet, spritesheet_data, Color('#323f4a'), name='Antenna')
        antenna.position = array((100, -120))
        self.add_child(antenna)
        self.sprite.anchor = array(TOP_LEFT)
        antenna.anchor = array(TOP_LEFT)

        # Set `Shape` child
        shape: Shape = Shape()
        shape.anchor = array(TOP_LEFT)
        shape.set_rect(Rect(VECTOR_ZERO, self.sprite.atlas.base_size))
        self.add_child(shape, 0)
