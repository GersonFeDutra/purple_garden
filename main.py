from src.core.nodes import *
from src.game.objects.chars import *
from src.game.objects.props import *
from src.game.gui.ui import *
from src.game.consts import *

# Setup the Engine
root.start(TITLE)

# %%
# Setup Game's Content

# Loading Resources
ROOT_DIR: str = path.dirname(__file__)
ASSETS_DIR: str = path.join(ROOT_DIR, 'assets')
SPRITES_DIR: str = path.join(ASSETS_DIR, 'sprites')
SOUNDS_DIR: str = path.join(ASSETS_DIR, 'sounds')

root.sprites_groups = {
    root.DEFAULT_GROUP: sprite.Group(),
    PLAYER_GROUP: sprite.Group(),
    ENEMY_GROUP: sprite.Group(),
}

spritesheet: Surface = pygame.image.load(
    path.join(SPRITES_DIR, 'dino.png'))

# Sound Streams
death_sfx: Sound = Sound(path.join(SOUNDS_DIR, 'death.wav'))
jump_sfx: Sound = Sound(path.join(SOUNDS_DIR, 'jump.wav'))
score_sfx: Sound = Sound(path.join(SOUNDS_DIR, 'score.wav'))


# %%
# Nodes Setup
FLOOR_COORD: float = root._screen_height - CELL_SIZE * SPRITES_SCALE[Y]

bg: BackGround = BackGround(spritesheet, 3)
spawner: Spawner = Spawner(FLOOR_COORD, spritesheet, speed=bg.scroll_speed)
# spawn: Spawn = Spawn(coords=(randint(0, root._screen_width), randint(0, root._screen_height)))

player: Player = Player(score_sfx, death_sfx, spritesheet, coords=array(
    [root._screen_width // 2, FLOOR_COORD + CELL_SIZE // 2]) + (16, 16))
# player: Player = Player(coords=(root._screen_width // 2, root._screen_height // 2))
player.scale = array(SPRITES_SCALE)

# GUI
label: Label = Label((40, 40), color=colors.BLACK, text='Points: 0')
display: GameOverDisplay = GameOverDisplay()


# %%
# Construção da árvore
root.add_child(bg)
# root.add_child(spawn)
root.add_child(player)
root.add_child(spawner)
root.add_child(label)
root.add_child(display)

# Conexões
# spawn.connect(spawn.collected, score_sfx, score_sfx.play)
player.connect(player.points_changed, label, label.set_text)
player.connect(player.scored, bg, bg.speed_up)
player.connect(player.scored, spawner, spawner.speed_up)
player.connect(player.died, display, display.show)
display.connect(display.game_resumed, spawner, spawner._on_Game_resumed)
display.connect(display.game_resumed, player, player._on_Game_resumed)


# %%
# Runs the Engine
root.run()
