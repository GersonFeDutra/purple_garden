from typing import Callable

import pygame
from pygame import Color, Surface, Vector2
from pygame import sprite, draw, font
from pygame.locals import *
from sys import exit, argv

# Other imports
import warnings
from enum import IntEnum
from numpy import array
from numpy.linalg import norm
from collections import deque

# Constants & Utils
from .lib.vectors import *
from .lib import colors
from .lib.utils import *

# Debug Mode Flags & Tools
IS_DEBUG_ENABLED: bool = '-t' in argv
IS_DEV_MODE_ENABLED: bool = IS_DEBUG_ENABLED and '-d' in argv
GIZMO_RADIUS: int = 2

# Inicializa os módulos do PyGame
pygame.init()


class InputEvent:
    '''Data-Class usada como registro de um evento de entrada no sistema do jogo.'''
    input_type: int
    key: int
    tag: str
    target: object

    def __init__(self, input_type: int, key: int, tag: str, target) -> None:
        self.type = input_type
        self.key = key
        self.tag = tag
        self.target = target


class Entity:
    '''Entidade básica do jogo, que contém informações de espaço (2D).'''
    position: array
    color: Color
    scale: array
    anchor: array

    class SignalNotExists(Exception):
        pass

    class Signal:
        '''Classe responsável por gerenciar o envio de "eventos"/ "mensagens" entre nós.
        Baseado no padrão do observador, inspirado na sua implementação no motor Godot.'''
        owner = None
        name: str  # Metadata # Apenas para auxiliar no debug

        class NotOwner(Exception):
            '''Lançado ao tentar operar o sinal para um objeto que não a pertence'''
            pass

        class AlreadyConnected(Exception):
            '''Lançada ao tentar conectar um sinal a um mesmo observador'''
            pass

        class NotConnected(Exception):
            '''Lançado ao tentar desconectar um sinal de um objeto que não é observador'''
            pass

        # Permitir kwargs?
        def connect(self, owner, observer, method: Callable, *args) -> None:
            '''Conecta o sinal ao método indicado. O mesmo será chamado quando o nó for emitido.'''
            if owner != self.owner:
                raise Entity.Signal.NotOwner

            if self._observers.get(observer) != None:
                raise Entity.Signal.AlreadyConnected

            self._observers[observer] = (method, args)

        def disconnect(self, owner, observer) -> None:
            '''Desconecta o método pertencente ao nó indicado desse sinal.'''
            if owner != self.owner:
                raise Entity.Signal.NotOwner

            if self._observers.pop(observer) == None:
                raise Entity.Signal.NotConnected

        def emit(self, *args) -> None:
            '''Emite o sinal, propagando chamadas aos métodos conectados.
            Os argumentos passados para as funções conectadas são, respectivamente:
            os argumentos passados ao conectar a função, em seguida,
            os argumentos passados na emissão.'''

            for observer, data in self._observers.items():
                data[0](*(data[1] + args))

        def __init__(self, owner, name: str) -> None:
            self.owner = owner
            self.name = name
            self._observers: dict[Entity, tuple[Callable, ]] = {}

    def _draw(self, target_pos: tuple[int, int] = None, target_scale: tuple[float, float] = None,
              offset: tuple[int, int] = None) -> None:
        '''Atualiza as pinturas na tela.
        Recebe uma posição, escala e deslocamento pré-calculados.'''
        global root

        if not self._draw_cell:
            return

        cell: array = self.get_cell()

        if target_pos is None:
            target_pos = self.position

        if target_scale is None:
            target_scale = self.scale

        # Desenha o Gizmo
        extents: array = GIZMO_RADIUS * target_scale
        draw.line(root.screen, self.color,
                  (target_pos[X] - extents[X], target_pos[Y]),
                  (target_pos[X] + extents[X], target_pos[Y]))
        draw.line(root.screen, self.color,
                  (target_pos[X], target_pos[Y] - extents[Y]),
                  (target_pos[X], target_pos[Y] + extents[Y]))

        if cell[X] != 0 or cell[Y] != 0:
            # Desenha as bordas da caixa delimitadora
            extents = cell * target_scale

            anchor: array = array(self.anchor)
            draw_bounds(root.screen, target_pos, extents, anchor,
                        self.color, fill=self._debug_fill_bounds)

    def set_cell(self, value: tuple[int, int]) -> None:
        '''Método virtual para determinar um tamanho/ espaço customizado para a célula.'''
        return

    def get_cell(self) -> tuple[int, int]:
        '''Retorna o tamanho/espaço da célula que envolve o nó.'''
        return VECTOR_ZERO

    def connect(self, signal, observer, method, *args) -> None:
        '''Realiza a conexão de um sinal que pertence ao nó.'''
        try:
            signal.connect(self, observer, method, *args)
        except Entity.Signal.NotOwner:
            raise Entity.SignalNotExists

    def disconnect(self, signal, observer) -> None:
        '''Desconecta um sinal pertencente ao nó.'''
        try:
            signal.disconnect(self, observer)
        except Entity.Signal.NotOwner:
            raise Entity.SignalNotExists

    def get_x(self) -> int:
        return self.position[X]

    def get_y(self) -> int:
        return self.position[Y]

    def __init__(self, coords: tuple[int, int] = VECTOR_ZERO) -> None:
        self.position = array(coords)
        self.scale = array(VECTOR_ONE)
        self.anchor = array(CENTER)
        self.color = Color(0, 185, 225, 125)
        self._debug_fill_bounds: bool = False
        self._draw_cell = IS_DEBUG_ENABLED


class Node(Entity):
    '''Classe fundamental que representa um objeto quaisquer do jogo.
    Permite a composição desses objetos em uma estrutura de árvore.
    Sua principal vantagem é a propagação de ações e eventos.'''

    class PauseModes(IntEnum):
        '''Bit-flags para verificação do modo de parada no processamento da árvore.'''
        # Flag para alterar o processamento da árvore (1 == em pausa, 0 == ativo).
        TREE_PAUSED: int = 1
        STOP: int = 2  # Interrompe o processamento do nó e seus filhos
        # Interrompe o processamento do nó, mas continua processando os filhos.
        CONTINUE: int = 4
        IGNORE: int = 8  # Mantém o processando o nó.

    pause_mode: int = PauseModes.IGNORE

    class EmptyName(Exception):
        pass

    class InvalidChild(Exception):
        '''Lançado ao tentar adicionar um filho que já tem um pai, ou, a si mesmo'''
        pass

    class DuplicatedChild(InvalidChild):
        '''Lançado ao tentar inserir um filho de mesmo nome.'''
        pass

    def add_child(self, node, at: int = -1) -> None:
        '''Registra um nó na árvore como filho do nó atual.'''
        if node == self or node._parent:
            raise Node.InvalidChild

        if self._children_refs.get(node.name, False):
            raise Node.DuplicatedChild

        if at == -1:
            self._children_index.append(node)
        else:
            self._children_index.insert(at, node)

        self._children_refs[node.name] = node
        node._parent = self

        if self._is_on_tree:
            node._enter_tree()

    def remove_child(self, node=None, at: int = -1):
        '''Remove os registros do nó, se for filho.'''

        if not self._children_refs:
            return None

        if node == None:
            node = self._children_index.pop(at)
        else:
            self._children_index.remove(node)

        node = self._children_refs.pop(node.name, None)
        node._parent = None

        if self._is_on_tree:
            node._exit_tree()

        return node

    def toggle_process(self) -> None:
        self.pause_mode = self.pause_mode ^ Node.PauseModes.TREE_PAUSED

    def pause(self, do_pause: bool = False) -> None:

        if do_pause:
            # Adiciona a flag de pausa, se já não inserida.
            self.pause_mode = self.pause_mode | Node.PauseModes.TREE_PAUSED
        else:
            # Remove a flag de pausa, se estiver inserida.
            self.pause_mode = self.pause_mode & ~Node.PauseModes.TREE_PAUSED

    def get_child(self, name: str = '', at: int = -1):
        '''Busca um nó filho, por nome ou índice.'''

        if name:
            return self._children_refs.get(name, None)
        else:
            return self._children_index[at]

    def get_parent(self):
        return self._parent

    def get_global_position(self) -> tuple[int, int]:
        '''Calcula a posição do nó, considerando a hierarquia
        (posições relativas aos nós ancestrais.'''

        if self._parent:
            return self._parent.get_global_position() + self.position
        else:
            return tuple(self.position)

    # def _parent

    def _enter_tree(self) -> None:
        '''Método virtual que é chamado logo após o nó ser inserido a árvore.
        Chamado após este nó ou algum antecedente ser inserido como filho de outro nó na árvore.'''
        self._is_on_tree = True

        for child in self._children_index:
            child._enter_tree()

    def _exit_tree(self) -> None:
        '''Método virtual que é chamado logo após o nó ser removido da árvore.
        Chamado após este nó ou algum antecedente ser removido de outro nó na árvore.'''
        self._is_on_tree = False

        for child in self._children_index:
            child._exit_tree()

    def _draw(self, target_pos: tuple[int, int], target_scale: tuple[float, float],
              offset: tuple[int, int]) -> None:
        '''Método virtual chamado no passo de renderização dos nós.
        Os argumentos passados são: a posição global do objeto, a escala global,
        e o deslocamento na célula (sobre seu ponto de ancoragem).'''
        super()._draw(target_pos, target_scale, offset)

    def _input(self) -> None:
        '''Método virtual chamado no passo de captura de entradas dos nós.'''
        pass

    def _input_event(self, event: InputEvent) -> None:
        '''Método virtual chamado quando um determinado evento de entrada ocorrer.'''
        pass

    def _propagate(self, parent_offset: array = array(VECTOR_ZERO),
                   parent_scale: array = array(VECTOR_ONE), tree_pause: int = 0):
        '''Propaga os métodos virtuais na hierarquia da árvore, da seguinte forma:
        Primeiro as entradas são tomadas e então os desenhos são renderizados na tela.
        Logo em seguida, após a propagação nos filhos, o método `_process` é executado.'''
        global root

        target_scale: array = self.scale * parent_scale
        target_pos: array = self.position + parent_offset
        offset: array = self.get_cell() * target_scale * self.anchor
        physics_helper: PhysicsHelper = PhysicsHelper(self)

        self._input()
        self._draw(target_pos, target_scale, offset)

        tree_pause = tree_pause | root.tree_pause | self.pause_mode
        self._subpropagate(target_pos, target_scale,
                           physics_helper.children, tree_pause)

        if not (tree_pause & Node.PauseModes.STOP or
                tree_pause & Node.PauseModes.TREE_PAUSED
                and not(self.pause_mode & Node.PauseModes.CONTINUE)):

            self._process()

        return physics_helper.check_collisions()

    def _subpropagate(self, target_pos: array, target_scale: array,
                      physics_helpers: deque, tree_pause: int) -> None:
        '''Método auxiliar para propagar métodos virtuais nos nós filhos.'''

        for child in self._children_index:
            physics_helpers.append(child._propagate(target_pos, target_scale))

    def _process(self):
        '''Método virtual para processamento de dados em cada passo/ frame.'''
        pass

    def __init__(self, name: str = 'Node', coords: tuple[int, int] = VECTOR_ZERO) -> None:
        super().__init__(coords=coords)

        if not name:
            raise Node.EmptyName

        self.name: str = name
        self._is_on_tree: bool = False
        self._children_index: list[Node] = []
        self._children_refs: dict[str, Node] = {}
        self._parent: Node = None
        self._current_groups: list[str] = []


class Input:
    '''Classe responsável por gerenciar eventos de entrada.'''
    _instance = None
    events: dict = {}

    class NotANode(Exception):
        '''Lançado ao tentar registrar um evento em um objeto que não e do tipo `Node`.'''
        pass

    def register_event(self, to: Node, input_type: int, key: int, tag: str = "") -> None:

        if not isinstance(to, Node):
            raise Input.NotANode

        event_type: dict = self.events.get(input_type)
        if not event_type:
            event_type = {}
            self.events[input_type] = event_type

        event_key: list = event_type.get(key)
        if not event_key:
            event_key = []
            event_type[key] = event_key

        event_key.append(InputEvent(input_type, key, tag, to))

    def get_input_strength() -> array:
        '''Método auxiliar para calcular um input axial.'''
        is_pressed = pygame.key.get_pressed()
        keys: dict = {K_w: 0.0, K_a: 0.0, K_s: 0.0, K_d: 0.0}
        strength: array

        for key in keys:
            keys[key] = 1.0 if is_pressed[key] else 0.0

        strength = array([keys[K_d] - keys[K_a], keys[K_s] - keys[K_w]])
        strength_norm = norm(strength)

        if strength_norm:
            strength /= strength_norm

        return strength

    def _tick(self) -> None:
        '''Passo de captura dos inputs, convertendo-os em eventos.'''

        for event in pygame.event.get():
            if event.type == QUIT:
                pygame.quit()
                exit()

            event_type: dict = self.events.get(event.type, False)
            if not event_type:
                continue

            event_key: list = event_type.get(event.key)
            if not event_key:
                continue

            for event in event_key:
                node: Node = event.target
                node._input_event(event)

    def __new__(cls):
        # Torna a classe em uma Singleton
        if cls._instance is None:
            # Criação do objeto
            cls._instance = super(Input, cls).__new__(cls)

        return cls._instance


class Control(Node):
    '''Nó Base para subtipos de Interface Gráfica do Usuário (GUI).'''
    size: tuple[int, int]

    def get_cell(self) -> tuple[int, int]:
        return self.size

    def __init__(self, name: str = 'Control', coords: tuple[int, int] = VECTOR_ZERO) -> None:
        super().__init__(name=name, coords=coords)
        self.anchor = array(TOP_LEFT)


class Grid(Control):
    '''Contêiner que posiciona seus nós filhos em layout de grade.'''
    rows: int = 1
    cell_space: tuple[int, int] = VECTOR_ZERO

    def add_child(self, node: Node, at: int = -1) -> None:
        super().add_child(node, at=at)

        self.cell_space = max(self.cell_space[X], node.get_cell()[X]), max(
            self.cell_space[Y], node.get_cell()[Y])
        self.update_container()

        # Updates the size
        self.size = array(self.cell_space)
        self.size[X] *= self.rows
        self.size[Y] *= len(self._children_index) // self.rows

    def remove_child(self, node=None, at: int = -1) -> Node:
        node: Node = super().remove_child(node=node, at=at)
        self.update_container()

        return node

    def update_container(self) -> None:
        current_pos: array = array(VECTOR_ZERO)
        counter: int = 0

        for child in self._children_index:
            child.position = current_pos
            counter += 1
            current_pos = array(current_pos)

            if counter < self.rows:
                current_pos[X] += self.cell_space[X]
            else:
                counter = 0
                current_pos[X] = 0
                current_pos[Y] += self.cell_space[Y]

    def set_rows(self, value: int) -> None:
        self._rows = value

        # Updates the size
        self.size = array(self.cell_space)
        self.size[X] *= value
        self.size[Y] *= len(self._children_index) // value

    def get_rows(self) -> int:
        return self._rows

    def __init__(self, name: str = 'Grid', coords: tuple[int, int] = VECTOR_ZERO,
                 rows: int = 1) -> None:
        super().__init__(name=name, coords=coords)
        self._rows: int = rows

    rows: property = property(get_rows, set_rows)


class TextureSequence:
    '''Data Resource (apenas armazena os dados) para animações sequenciais simples.'''
    frame: int = 0
    speed: float
    DEFAULT_SPEED: float = 0.06

    def add_spritesheet(self, texture: Surface, h_slice: int = 1, v_slice: int = 1,
                        coords: tuple[int, int] = VECTOR_ZERO,
                        sprite_size: tuple[int, int] = None) -> None:
        '''Realiza o fatiamento da textura de uma spritesheet como a sequencia de sprites.'''

        if sprite_size is None:
            sprite_size = (texture.get_width() / h_slice,
                           texture.get_height() / v_slice)

        for i in range(h_slice):
            for j in range(v_slice):
                self.textures.append(texture.subsurface(
                    array(coords) + (i, j) * array(sprite_size), sprite_size))

    def add_texture(self, *paths: str) -> None:

        for path in paths:
            self.textures.append(pygame.image.load(path))

    def set_textures(self, value: list) -> None:
        self._textures = value
        self.frame = 0

    def get_textures(self) -> list:
        return self._textures

    def get_frames(self) -> int:
        return len(self._textures)

    def get_texture(self) -> Surface:
        return self._textures[self.frame]

    def __init__(self, speed: float = DEFAULT_SPEED) -> None:
        self._textures: list[Surface] = []
        self.speed = speed

    textures: property = property(get_textures, set_textures)


class BaseAtlas(sprite.Sprite):
    '''Classe do PyGame responsável por gerenciar sprites e suas texturas.'''
    base_size: array

    def __init__(self) -> None:
        super().__init__()
        self.base_size = array(VECTOR_ZERO)


class Icon(BaseAtlas):
    '''Atlas básico para imagens estáticas. Pode comportar múltiplas texturas,
    requer manipulação externa da lista.'''
    textures: list[Surface]

    @staticmethod
    def get_spritesheet(texture: Surface, h_slice: int = 1, v_slice: int = 1,
                        coords: tuple[int, int] = VECTOR_ZERO,
                        sprite_size: tuple[int, int] = None) -> list[Surface]:
        '''Realiza o fatiamento da textura de uma spritesheet como a sequencia de surfaces.'''
        sheet: list[Surface] = []

        if sprite_size is None:
            sprite_size = (texture.get_width() / h_slice,
                           texture.get_height() / v_slice)

        for i in range(h_slice):
            for j in range(v_slice):
                sheet.append(texture.subsurface(array(coords) +
                             (i, j) * array(sprite_size), sprite_size))

        return sheet

    def set_texture(self, id: int) -> None:
        self.image: Surface = self.textures[id]
        self.rect = self.image.get_rect()
        self.base_size = array(self.image.get_size())

    def __init__(self, textures: list[Surface]) -> None:
        super().__init__()
        self.textures = textures
        self.set_texture(len(textures) - 1)


class Atlas(BaseAtlas):
    '''Atlas com uma única sequência simples de animação, ou único sprite estático.'''
    sequence: TextureSequence
    is_paused: bool = False

    _static: bool = True
    _current_time: float = 0.0

    def update(self) -> None:
        '''Processamento dos quadros da animação.'''

        if self._static or self.is_paused:
            return

        self._current_time = (
            self._current_time + self.sequence.speed) % self.sequence.get_frames()
        self.sequence.frame = int(self._current_time)
        self.__update_frame()

    def _update_frame(self) -> None:
        '''Método auxiliar para atualização dos quadros.'''

        if self.sequence.textures:
            self.__update_frame()

    def __update_frame(self) -> None:
        ''''Atualiza um frame da animação.'''
        self.image: Surface = self.sequence.get_texture()
        self.rect = self.image.get_rect()
        self.base_size = array(self.image.get_size())

    def add_texture(self, *paths: str) -> None:
        '''Adciona uma textura ao atlas.'''
        self.sequence.add_texture(paths)

        if self.sequence.get_frames() > 1:
            self._static = False

        self._update_frame()

    def add_spritesheet(self, texture: Surface, h_slice: int = 1, v_slice: int = 1,
                        coords: tuple[int, int] = VECTOR_ZERO,
                        sprite_size: tuple[int, int] = None) -> None:
        '''Realiza o fatiamento da textura de uma spritesheet como sprites de uma animação.'''
        self.sequence.add_spritesheet(
            texture, h_slice, v_slice, coords, sprite_size)

        if self.sequence.get_frames() > 1:
            self._static = False

        self._update_frame()

    def load_spritesheet(self, path: str, h_slice: int = 1, v_slice: int = 1,
                         coords: tuple[int, int] = VECTOR_ZERO,
                         sprite_size: tuple[int, int] = None) -> None:
        '''Faz o carregamento de uma textura como uma spritesheet, com o devido fatiamento.'''
        self.add_spritesheet(pygame.image.load(
            path), h_slice=h_slice, v_slice=v_slice, coords=coords, sprite_size=sprite_size)

    def set_textures(self, value: list) -> None:
        self.sequence.textures = value
        self._static = self.sequence.get_frames() <= 1
        self._update_frame()

    def get_textures(self) -> list:
        return self.sequence._textures

    def set_frame(self, value: int) -> None:

        if value > self.sequence.get_frames():
            return

        self.sequence.frame = value
        self._current_time = float(value)
        self._update_frame()

    def get_frame(self) -> int:
        return self.sequence.frame

    def __init__(self) -> None:
        super().__init__()
        self.sequence = TextureSequence()

    frame: property = property(get_frame, set_frame)
    textures: property = property(get_textures, set_textures)


class AtlasBook(BaseAtlas):
    '''Atlas composto por múltiplas animações de sprites.'''
    is_paused: bool = False
    animations: dict[str, TextureSequence]
    _current_sequence: TextureSequence = None

    _static: bool = True
    _current_time: float = 0.0

    def update(self) -> None:
        '''Processamento dos quadros da animação.'''

        if self._static or self.is_paused:
            return

        self._current_time = (
            self._current_time + self._current_sequence.speed) % self._current_sequence.get_frames()
        self._current_sequence.frame = int(self._current_time)
        self.__update_frame()

    def _update_frame(self) -> None:
        '''Método auxiliar para atualização dos quadros.'''

        if self._current_sequence.textures:
            self.__update_frame()

    def __update_frame(self) -> None:
        ''''Atualiza um frame da animação.'''
        self.image: Surface = self._current_sequence.get_texture()
        self.rect = self.image.get_rect()
        self.base_size = array(self.image.get_size())

    def add_animation(self, name: str, texture: Surface, h_slice: int = 1, v_slice: int = 1,
                      coords: tuple[int, int] = VECTOR_ZERO, sprite_size: tuple[int, int] = None,
                      speed: float = TextureSequence.DEFAULT_SPEED) -> None:
        '''Adciona uma animação ao atlas, com base em uma spritesheet
        (aplicando o fatiamento indicado).'''
        sequence: TextureSequence = TextureSequence(speed)
        sequence.add_spritesheet(
            texture, h_slice, v_slice, coords, sprite_size)
        self.animations[name] = sequence
        self._current_sequence = sequence

        if sequence.get_frames() > 1:
            self._static = False

        self._update_frame()

    def append_animation_frames(self, name: str, texture: Surface, h_slice: int = 1,
                                v_slice: int = 1, coords: tuple[int, int] = VECTOR_ZERO,
                                sprite_size: tuple[int, int] = None) -> None:

        if name in self.animations:
            self.animations[name].add_spritesheet(
                texture, h_slice, v_slice, coords, sprite_size)
        else:
            self.add_animation(name, texture, h_slice,
                               v_slice, coords, sprite_size)

    def set_current_animation(self, name: str) -> None:
        '''Determina a animação atual, se a animação indicada
        não for encontrada resultará em erro.'''

        self._current_sequence = self.animations[name]
        self._static = self._current_sequence.get_frames() <= 1
        self._update_frame()

    def set_frame(self, value: int) -> None:

        if value > self._current_sequence.get_frames():
            return

        self._current_sequence.frame = value
        self._current_time = float(value)
        self._update_frame()

    def get_frame(self) -> int:
        return self._current_sequence.frame

    def __init__(self) -> None:
        super().__init__()
        self.animations = {}

    frame: property = property(get_frame, set_frame)


class Sprite(Node):
    '''Nó que configura um sprite do Pygame como um objeto de jogo
    (que pode ser inserido na árvore da cena).'''
    atlas: BaseAtlas
    group: str

    def _enter_tree(self) -> None:
        global root

        root.sprites_groups[self.group].add(self.atlas)
        super()._enter_tree()

    def _exit_tree(self) -> None:
        global root

        root. sprites_groups[self.group].remove(self.atlas)
        super()._exit_tree()

    def _draw(self, target_pos: tuple[int, int], target_scale: tuple[float, float],
              offset: tuple[int, int]) -> None:
        super()._draw(target_pos, target_scale, offset)

        # REFACTOR -> Fazer as transforms serem recalculadas _JIT_ (Just In Time).
        self.atlas.image = pygame.transform.scale(
            self.atlas.image, (self.atlas.base_size * target_scale).astype('int'))
        self.atlas.rect.topleft = array(target_pos) - offset

    def get_cell(self) -> array:
        return array(self.atlas.base_size)

    def __init__(self, name: str = 'Sprite', coords: tuple[int, int] = VECTOR_ZERO,
                 atlas: BaseAtlas = None) -> None:
        global root
        super().__init__(name=name, coords=coords)

        # REFACTOR -> Tornar o tipo de atlas mandatório, ou alterar o tipo default para `AtlasBook`.`
        if atlas:
            self.atlas = atlas
        else:
            self.atlas = Atlas()

        self.group = root.DEFAULT_GROUP


# TODO -> Make Parallax Background using Surfaces
'''
class ParallaxBackground(Node):
    offset: array
    distance: float = 1.0

    def _process(self):
        self.offset[0] = self.offset[0] + self.distance

    def _subpropagate(self, target_pos: array, target_scale: array, rect: pygame.Rect, children_data: list[dict]):
        return super()._subpropagate(target_pos, target_scale, rect, children_data)

    def __init__(self, name: str = 'Node', coords: tuple[int, int] = VECTOR_ZERO) -> None:
        super().__init__(name=name, coords=coords)
        self.offset = array([0.0, 0.0])
'''


class Shape(Node):
    '''Nó que representa uma forma usada em cálculos de colisão.
    Deve ser adicionada como filha de um `KinematicBody`.'''
    rect_changed: Entity.Signal
    base_size: array([int, int])

    class CollisionType(IntEnum):
        PHYSICS = 1  # Área usada para detecção de colisão entre corpos
        AREA = 2  # Área usada para mapeamento (renderização, ou localização).

    type: int = CollisionType.PHYSICS

    def _draw(self, target_pos: tuple[int, int], target_scale: tuple[float, float],
              offset: tuple[int, int]) -> None:
        super()._draw(target_pos, target_scale, offset)
        self._rect.size = self.base_size * target_scale
        self._rect.topleft = array(target_pos) - offset

    def get_cell(self) -> array:
        return array(self.base_size)

    def set_rect(self, value: Rect) -> None:
        self.base_size = array(value.size)
        self._rect = value
        self.rect_changed.emit(self)

    def get_rect(self) -> Rect:
        return self._rect

    def bounds(self) -> Rect:
        '''Retorna a caixa delimitadora da forma.'''
        return self._rect

    def __init__(self, name: str = 'Shape', coords: tuple[int, int] = VECTOR_ZERO) -> None:
        super().__init__(name=name, coords=coords)
        self._rect: Rect = None
        self.rect_changed = Entity.Signal(self, 'rect_changed')
        self._debug_fill_bounds = True

    rect: property = property(get_rect, set_rect)


class VisibilityNotifier(Shape):
    screen_entered: Node.Signal
    screen_exited: Node.Signal
    is_on_screen: bool = None

    def _draw(self, target_pos: tuple[int, int],
              target_scale: tuple[float, float], offset: tuple[int, int]) -> None:
        global root
        super()._draw(target_pos, target_scale, offset)

        is_colliding: bool = self._rect.colliderect(root._screen_rect)

        if is_colliding != self.is_on_screen:
            self._shift(is_colliding)

    def shift_on_screen(self, _to: bool = None) -> None:

        if self.is_on_screen:
            self.screen_exited.emit()
        else:
            self.screen_entered.emit()

        self.is_on_screen = not self.is_on_screen

    def set_on_screen(self, to: bool = None) -> None:
        self.is_on_screen = to
        self._shift = self.shift_on_screen

    def __init__(self, name: str = 'VisibilityNotifier',
                 coords: tuple[int, int] = VECTOR_ZERO) -> None:
        super().__init__(name=name, coords=coords)
        self.type = Shape.CollisionType.AREA
        self.color = Color(118, 10, 201)

        self.screen_exited = Node.Signal(self, 'screen_exited')
        self.screen_entered = Node.Signal(self, 'screen_entered')
        self._was_draw_once: bool = False
        self._shift: Callable = self.set_on_screen


class ProgressBar(Control):
    bar: Shape
    bg: Shape
    borders: Shape

    def set_progress(self, value: float) -> None:
        self._progress = value
        self.bar.base_size[self._grow_coord] = self._base_size[self._grow_coord] * value

    def get_progress(self) -> float:
        return self._progress

    def __init__(self, name: str = 'ProgressBar', coords: tuple[int, int] = VECTOR_ZERO,
                 bg_color: Color = colors.BLUE, bar_color: Color = colors.GREEN,
                 borders_color: Color = colors.RED, v_grow: bool = False,
                 size: tuple[int, int] = (125, 25),
                 borders: tuple[int, int, int, int] = (2, 2, 2, 2)) -> None:
        super().__init__(name=name, coords=coords)
        self.color = bg_color
        self.size = size

        self._progress: float = .5
        self._grow_coord: int = int(v_grow)

        topleft: array = array((borders[X], borders[Y]))
        base_size: array = size - (topleft + (borders[W], borders[H]))
        self._base_size: array = base_size

        # Set the border square
        bar: Shape = Shape(name='Borders')
        bar.anchor = array(TOP_LEFT)
        bar.color = borders_color
        bar.rect = Rect(VECTOR_ZERO, size)
        bar._draw_cell = True
        self.borders = bar
        self.add_child(bar)

        # Set the BG
        bar: Shape = Shape(name='BG', coords=topleft)
        bar.anchor = array(TOP_LEFT)
        bar.color = bg_color
        bar.rect = Rect(topleft, base_size)
        bar._draw_cell = True
        self.bg = bar
        self.add_child(bar)

        # Set the Inner Bar
        bar: Shape = Shape(name='Bar', coords=topleft)
        bar.anchor = array(TOP_LEFT)
        bar.color = bar_color
        bar.rect = Rect(topleft, base_size)
        bar._draw_cell = True
        self.bar = bar
        self.add_child(bar)

        # Updates the progress
        self.set_progress(self._progress)

    progress: property = property(get_progress, set_progress)


class KinematicBody(Node):
    '''Nó com capacidades físicas (permite colisão).'''
    collided: Entity.Signal

    def add_child(self, node: Node, at: int = -1) -> None:
        super().add_child(node, at=at)

        if isinstance(node, Shape) and node.type & Shape.CollisionType.PHYSICS:
            self._on_Shape_rect_changed(node)
            node.connect(node.rect_changed, self, self._on_Shape_rect_changed)

    def remove_child(self, node=None, at: int = -1):
        super().remove_child(node=node, at=at)

        if node is Shape:
            self._on_Shape_rect_changed(node)
            node.disconnect(node.rect_changed, self,
                            self._on_Shape_rect_changed)

    def _enter_tree(self) -> None:
        super()._enter_tree()

        if not self.has_shape():
            warnings.warn(
                "A `Shape` node must be added as a child to process collisions.", category=Warning)

    def _process(self) -> None:
        self._physics_process()

    def _physics_process(self) -> None:
        pass

    def _on_Shape_rect_changed(self, _shape: Shape) -> None:

        if _shape.bounds():
            self._active_shapes.append(_shape)
            self._was_shapes_changed = True

    # def _expand_bounds(self, with_shape: Rect) -> None:
    #     '''Método auxiliar para expandir a caixa delimitadora desse corpo físico.'''
    #
    #     if self._bounds:
    #         self._bounds = self._bounds.union(with_shape)

    def has_shape(self) -> bool:
        return bool(self._active_shapes)

    def is_colliding(self, target) -> bool:
        ''''Verifica colisões com o corpo indicado.'''

        for a in self._active_shapes:
            for b in target._active_shapes:
                if a.rect.colliderect(b.rect):
                    return True

        return False

    def bounds(self) -> Rect:
        '''Retorna a caixa delimitadora do corpo.'''

        if self._was_shapes_changed:
            self._cached_bounds = None
            self._was_shapes_changed = False

        if self._cached_bounds:
            return self._cached_bounds

        elif self._active_shapes:
            # Calcula novas fronteiras
            self._cached_bounds = self._active_shapes[0].rect

            for shape in self._active_shapes[1:]:
                self._cached_bounds.union(shape.bounds())

        return self._cached_bounds

    def __init__(self, name: str = 'KinematicBody', coords: tuple[int, int] = VECTOR_ZERO,
                 color: Color = Color(46, 10, 115)) -> None:
        super().__init__(name, coords=coords)
        self.color = color
        self.collided = Entity.Signal(self, 'collided')
        self._active_shapes: list[Shape] = []

        self._bounds: Rect = None

        self._was_shapes_changed: False
        self._cached_bounds: Rect = None


# TODO -> Tornar a Label um Nó Control
class Label(Node):
    '''Nó usado para apresentar texto na tela.'''
    font: font.Font

    def set_text(self, value: str) -> None:
        self._text = value
        self._surface = self.update_surface

    def get_text(self) -> None:
        return self._text

    def get_surface(self) -> Surface:
        return self._current_surface

    def update_surface(self) -> Surface:
        self._current_surface = self.font.render(self.text, True, self.color)
        self._surface = self.get_surface

        return self._current_surface

    def _draw(self, target_pos: tuple[int, int] = None, target_scale: tuple[float, float] = None,
              offset: tuple[int, int] = None) -> None:
        global root

        super()._draw(target_pos, target_scale, offset)
        root.render_queue.append(
            (self._surface(), target_pos - offset))

    def get_cell(self) -> tuple[int, int]:
        return self._surface().get_size()

    def __init__(self, font: font.Font, name: str = 'Label', coords: tuple[int, int] = VECTOR_ZERO,
                 color: Color = colors.WHITE, text: str = '') -> None:
        super().__init__(name=name, coords=coords)
        self.font = font
        self.color = color
        self.anchor = array(TOP_LEFT)

        self._current_surface: Surface
        self._surface: Callable = self.update_surface
        self._text: str
        self.set_text(text)

    text: property = property(get_text, set_text)


class PhysicsHelper():
    '''Objeto responsável pelo tratamento de colisões entre corpos físicos.'''
    _container_type: int = 0
    rect: Rect = None
    head: Node
    children = None

    class ContainerTypes(IntEnum):
        '''Enum para classificação dos nós entre contêineres ou corpos.'''
        EMPTY = 0  # Sem conteúdo
        SOLID = 1  # Corpo físico
        SHELL = 2  # Não é um corpo físico, mas contém filhos que o são

    def __init__(self, head: Node) -> None:
        self.head = head
        helper: PhysicsHelper = self
        self.children: deque[PhysicsHelper] = deque()

    def check_collisions(self):
        '''Verifica as colisões entre nós colisores. Retorna um auxiliar para permitir a construção
        de contêineres delimitadores em formato de árvore.'''
        is_solid: bool = isinstance(
            self.head, KinematicBody) and self.head.has_shape()
        self._container_type = int(is_solid)

        content: list = []  # Estrutura auxiliar para indexar os elementos posteriormente
        content_n: int = 0  # Quantidade de elementos do contêiner
        # Contêiner que armazenará nós colisores e outros contêineres
        container: PhysicsHelper = PhysicsHelper(self.head)
        # um contêiner é uma "casca/ invólucro" quando comporta elementos (nó interno ou raiz).
        container._container_type = PhysicsHelper.ContainerTypes.SHELL

        def non_empty(c: PhysicsHelper) -> Rect:
            '''O corpo/ contêiner é adicionado à fila do novo contêiner.
            retorna seu colisor/ caixa delimitadora, respectivamente.'''
            nonlocal content, content_n, container

            content.append(c)
            container.children.append(c)
            content_n += 1

            return c.rect

        # def empty(c: PhysicsHelper) -> None:
        #     return None

        _match: dict[int, Callable[[PhysicsHelper], Rect]] = {
            # Nada será feito, o conteúdo se perde.
            PhysicsHelper.ContainerTypes.EMPTY: lambda c: None,
            PhysicsHelper.ContainerTypes.SOLID: non_empty,
            PhysicsHelper.ContainerTypes.SHELL: non_empty,
        }

        if is_solid:
            # Se for sólido, se adiciona no topo da fila (para mantê-lo como uma folha na árvore).
            self.rect = self.head.bounds()
            container.rect = non_empty(self)

        while self.children and not container.rect:
            # Busca o primeiro nó para iniciar a caixa delimitadora do contêiner.
            child: PhysicsHelper = self.children.popleft()
            container.rect = _match[child._container_type](child)

        while self.children:
            # Adiciona os nós restantes.
            child: PhysicsHelper = self.children.popleft()
            rect: Rect = _match[child._container_type](child)

            if rect:
                container.rect = container.rect.union(rect)

        # Finaliza a configuração da raiz.
        if content_n > 1:
            # Verifica colisões nos filhos
            PhysicsHelper._check_collisions(container.children, content_n)
        elif content_n == 1:
            # Caso o contêiner tenha apenas um elemento, este não será necessário.
            container = container.children[0]
        else:
            # Retornará a si mesmo (um contêiner vazio).
            # Note que jamais será sólido pois, se assim fosse, teria sido adicionado no contêiner
            # e o bloco acima seria aplicada.
            container = self

        return container

    @staticmethod
    def _check_collisions(helpers: list, helpers_n: int) -> None:
        '''Algoritmo iterativo que checa as colisões nos filhos do nó passado.
        Sempre em direção às folhas.'''
        next_children: deque[dict[str, list]] = deque()

        # Verifica as combinações de elementos.
        for i in range(helpers_n):
            for j in range(i + 1, helpers_n):
                PhysicsHelper._check_collision(
                    helpers[i], helpers[j], next_children)

        while next_children:
            next: dict = next_children.popleft()

            for a in next['a']:
                for b in next['b']:
                    PhysicsHelper._check_collision(a, b, next_children)

    @staticmethod
    def _check_collision(a, b, next_children: deque[dict[str, list]]) -> None:
        '''Função auxiliar que verifica a colisão entre nós
        (verifica intersecção dos colisores dos contêineres aos corpos físicos).'''

        if a.rect.colliderect(b.rect):
            is_all_leaf: bool = True

            # Se o nó tiver filhos, fazemos a verificação entre eles e o outro nó colisor.
            if a.children:
                next_children.append({
                    'a': a.children,
                    'b': [b],
                })
                is_all_leaf = False

            elif b.children:
                next_children.append({
                    'a': [a],
                    'b': b.children
                })
                is_all_leaf = False

            if is_all_leaf:
                node_a: KinematicBody = a.head
                node_b: KinematicBody = b.head

                # Quando houver colisão nas folhas, o sinal `collided` é emitido para cada colisor.
                if node_a.is_colliding(node_b):
                    node_a.collided.emit(node_b)
                    node_b.collided.emit(node_a)


# root
class SceneTree(Node):
    '''Nó singleton usado como a rais da árvore da cena.
    Definido dessa forma para facilitar acessos globais.'''
    pause_toggled: Node.Signal

    # Default Screen - Onde os nós da árvore irão desenhar sobre.
    # Atualmente os valores não são sincronizados individualmente, ao invés disso,
    # a propriedade `screen_size`` é usado como interface para os mesmos.
    screen: Surface = None
    _screen_width: int = 640
    _screen_height: int = 480
    _screen_rect: Rect = Rect(VECTOR_ZERO, (_screen_width, _screen_height))
    screen_color: Color = colors.WHITE

    # Fila de renderização (para labels e outras superfícies)).
    render_queue: deque[Surface, tuple[int, int]] = deque()

    # PyGame Sprites Groups
    DEFAULT_GROUP: str = 'default'

    sprites_groups: dict[str, sprite.Group] = {
        DEFAULT_GROUP: sprite.Group(),
    }

    # Game Clock
    clock: pygame.time.Clock = None
    fixed_fps: int = 60  # Frames Per Second

    _instance = None
    tree_pause: int = 0
    groups: dict[str, list[Node]] = {}

    class AlreadyInGroup(Exception):
        '''Chamado ao tentar adicionar o nó a um grupo ao qual já pertence.'''
        pass

    def start(self, title: str = 'Game', screen_size: tuple[int, int] = None) -> None:
        '''Setups the basic settings.'''
        self.clock = pygame.time.Clock()

        if not (screen_size is None):
            self.screen_size = screen_size

        self.screen = pygame.display.set_mode(self.screen_size)
        #alpha_layer = Surface(SCREEN_SIZE, pygame.SRCALPHA)
        pygame.display.set_caption(title)

    def run(self) -> None:
        '''Game's Main Loop.'''
        while True:
            self.clock.tick(self.fixed_fps)
            self.screen.fill(self.screen_color)
            # Preenche a tela

            input._tick()
            # Propaga as entradas

            self._propagate()
            # Propaga o processamento

            for id, sprites in self.sprites_groups.items():
                # Desenha os sprites
                sprites.draw(self.screen)
                sprites.update()

            while self.render_queue:
                # Desenha a GUI
                self.screen.blit(*self.render_queue.pop())

            pygame.display.update()

    def pause_tree(self, pause_mode: int = Node.PauseModes.TREE_PAUSED) -> None:
        self.tree_pause = pause_mode
        self.pause_toggled.emit(
            bool((pause_mode ^ self.pause_mode) & Node.PauseModes.TREE_PAUSED))

    def add_to_group(self, node: Node, group: str) -> None:
        '''Adciona o nó a um grupo determinado.
        Se o grupo não existir, cria um novo.'''

        if node in node._current_groups:
            raise SceneTree.AlreadyInGroup

        nodes: list[Node] = self.groups.get(group)  # Stack

        if nodes:
            nodes.append(node)
        else:
            self.groups[group] = [node]

        node._current_groups.append(group)

    def remove_from_group(self, node: Node, group: str) -> None:
        '''Remove o nó do grupo determinado.
        Remove o grupo, caso o nó seja o único elemento deste.'''
        nodes: dict[Node, ] = self.groups.get(group)

        if nodes:
            nodes.pop(node, None)  # Remove silenciosamente

    def call_group(self, group: str, method_name: str, *args) -> deque[tuple[Node, ]]:
        '''Faz uma chamada de método em todos os nós pertencentes a um determinado grupo.
        Retorna uma fila de tuplas com os respectivos nós e seus retornos.'''
        queue: deque[tuple[Node, ]] = deque()

        for node in self.groups.get(group, ()).keys():
            deque.append((node, getattr(node, method_name)(*args)))

        return queue

    def is_on_group(self, node: Node, group: str) -> bool:
        '''Verifica se o nó pertence a um grupo determinado.'''
        return group in node._current_groups

    def set_screen_size(self, value: tuple[int, int]) -> None:
        self._screen_width, self._screen_height = value
        self._screen_rect.topleft = value

    def get_screen_size(self) -> tuple[int, int]:
        return self._screen_width, self._screen_height

    def __new__(cls):
        # Torna a classe em uma Singleton
        if cls._instance is None:
            # Criação do objeto
            cls._instance = super(SceneTree, cls).__new__(cls)

        return cls._instance

    def __init__(self, name: str = 'root', coords: tuple[int, int] = VECTOR_ZERO) -> None:
        super().__init__(name=name, coords=coords)
        self._is_on_tree = True

        # Events
        self.pause_toggled = Node.Signal(self, 'pause_toggled')

    screen_size: property = property(get_screen_size, set_screen_size)


# Singletons
input: Input = Input()  # Singleton usado na captura de inputs
# Nó Singleton que constitui a raiz da árvore da cena.
root: SceneTree = SceneTree()
