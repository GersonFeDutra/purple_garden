from abc import abstractmethod
from typing import Callable, Iterator, Match

import pygame
from pygame import Color, Surface, Vector2
from pygame import sprite, draw, font
from pygame import color
from pygame.locals import *
from sys import exit, argv

# Other imports
import re
import warnings
import webbrowser
import pytweening as tween
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
    scale: array

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
        draw.line(root.screen, self._color,
                  (target_pos[X] - extents[X], target_pos[Y]),
                  (target_pos[X] + extents[X], target_pos[Y]))
        draw.line(root.screen, self._color,
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

    def set_color(self, value: Color) -> None:
        self._color = value

    def get_color(self) -> Color:
        return self._color

    def set_anchor(self, value: tuple[int, int]) -> None:
        self._anchor = array(value)

    def get_anchor(self) -> tuple[int, int]:
        return tuple(self._anchor)

    def __init__(self, coords: tuple[int, int] = VECTOR_ZERO) -> None:
        self.position = array(coords)
        self.scale = array(VECTOR_ONE)
        self._anchor = array(CENTER)
        self._color: Color = Color(0, 185, 225, 125)
        self._debug_fill_bounds: bool = False
        self._draw_cell = IS_DEBUG_ENABLED

    color: property = property(get_color, set_color)
    anchor: property = property(get_anchor, set_anchor)


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

    def _propagate(self, delta_time: float, parent_offset: array = array(VECTOR_ZERO),
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
        self._subpropagate(delta_time, target_pos, target_scale,
                           physics_helper.children, tree_pause)

        if not (tree_pause & Node.PauseModes.STOP or
                tree_pause & Node.PauseModes.TREE_PAUSED
                and not(self.pause_mode & Node.PauseModes.CONTINUE)):

            self._process(delta_time)

        return physics_helper.check_collisions()

    def _subpropagate(self, delta_time: float, target_pos: array, target_scale: array,
                      physics_helpers: deque, tree_pause: int) -> None:
        '''Método auxiliar para propagar métodos virtuais nos nós filhos.'''

        for child in self._children_index:
            physics_helpers.append(child._propagate(
                delta_time, target_pos, target_scale))

    def _process(self, delta: float) -> None:
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

    class Mouse(IntEnum):
        LEFT_CLICK = 1
        MIDDLE_CLICK = 2
        RIGHT_CLICK = 3
        SCROLL_UP = 4
        SCROLL_DOWN = 5

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
        '''Passo de captura dos inputs, mapeando-os nos eventos e executando-os.'''

        for event in pygame.event.get():

            if event.type == QUIT:
                pygame.quit()
                exit()

            event_type: dict = self.events.get(event.type, False)
            if not event_type:
                continue

            # TODO -> Support more PyGame event types
            event_code: int = {
                KEYDOWN: lambda e: e.key,
                KEYUP: lambda e: e.key,
                MOUSEBUTTONUP: lambda e: e.button,
                MOUSEBUTTONDOWN: lambda e: e.button,
            }.get(event.type)(event)

            if event_code is None:
                continue

            for event in event_type.get(event_code, ()):
                node: Node = event.target
                node._input_event(event)

    def __new__(cls):
        # Torna a classe em uma Singleton
        if cls._instance is None:
            # Criação do objeto
            cls._instance = super(Input, cls).__new__(cls)

        return cls._instance


class Tween():
    '''Helper class used to tween animations in the `SceneTree`.'''

    class EaseInOut():
        '''Data class with the EaseInOut methods.'''
        SINE: Callable = tween.easeInOutSine
        BOUNCE: Callable = tween.easeInOutBounce
        CIRC: Callable = tween.easeInOutCirc
        CUBIC: Callable = tween.easeInOutCubic
        EXPO: Callable = tween.easeInOutExpo
        QUAD: Callable = tween.easeInOutQuad
        QUART: Callable = tween.easeInOutQuart
        QUINT: Callable = tween.easeInOutQuint

    class EaseIn():
        '''Data class with the EaseIn methods.'''
        SINE: Callable = tween.easeInSine
        BOUNCE: Callable = tween.easeInBounce
        CIRC: Callable = tween.easeInCirc
        CUBIC: Callable = tween.easeInCubic
        EXPO: Callable = tween.easeInExpo
        QUAD: Callable = tween.easeInQuad
        QUART: Callable = tween.easeInQuart
        QUINT: Callable = tween.easeInQuint

    class EaseOut():
        '''Data class with the EaseOut methods.'''
        SINE: Callable = tween.easeOutSine
        BOUNCE: Callable = tween.easeOutBounce
        CIRC: Callable = tween.easeOutCirc
        CUBIC: Callable = tween.easeOutCubic
        EXPO: Callable = tween.easeOutExpo
        QUAD: Callable = tween.easeOutQuad
        QUART: Callable = tween.easeOutQuart
        QUINT: Callable = tween.easeOutQuint

    tween_finished: Entity.Signal

    target: Node
    name: str = ''
    ease_method: Callable = None

    from_value = None
    to_value = None
    _values_diff = None

    duration: float = 0.0
    _elapsed_time: float = 0.0

    def _process(self, delta: float) -> None:
        '''Process the easing method.'''
        global root

        self._elapsed_time += delta / root.fixed_fps

        if self._elapsed_time > self.duration:
            setattr(self.target, self.name, self.to_value)
            root._active_tweens.remove(self)
            self.tween_finished.emit()
            return

        time_factor: float = self._elapsed_time / self.duration
        plot: float = self.ease_method(time_factor)
        new_value = self._values_diff * plot + self.from_value
        setattr(self.target, self.name, new_value)

    def interpolate_attribute(self, name: str, from_value, to_value, duration: float,
                              ease_method: Callable = EaseInOut.SINE) -> None:
        '''Starts the interpolation of an attribute of `target`.

            Parameters:
                name (str): The name of the target's attribute.
                from_value: Value in the t0 (zero time);
                    - value's type must accept arithmetic operations.
                to_value: Value in the tn (final time).
                duration (float): How much the ease animation will last.
                ease_method (Callable): Must be a valid ease function stored as constants
                    in the `EaseIn` `EaseOut` and `EaseInOut` data classes.
        '''
        global root

        self.name = name
        self.from_value = from_value
        self.to_value = to_value
        self._values_diff = to_value - from_value

        self.duration = duration
        self.ease_method = ease_method
        self._process(self._elapsed_time)
        root._active_tweens.append(self)

    # TODO -> `interpolate_method()`
    # def interpolate_method(self, name: str, from_args: tuple = (), to_args: tuple = (),
    #                        args_ease: tuple[Callable] = (), from_kwargs: dict[str,] = {},
    #                        to_kwargs: dict[str,] = {}, kwargs_ease: dict[str, Callable])

    def __init__(self, target: Node) -> None:
        self.target = target
        self.tween_finished = Entity.Signal(self, 'tween_finished')


class Control(Node):
    '''Nó Base para subtipos de Interface Gráfica do Usuário (GUI).'''

    def get_cell(self) -> tuple[int, int]:
        return self.size

    def set_size(self, value: tuple[int, int]) -> None:
        self._size = array(value)

    def get_size(self) -> tuple[int, int]:
        return tuple(self._size)

    def __init__(self, name: str = 'Control', coords: tuple[int, int] = VECTOR_ZERO,
                 anchor: tuple[int, int] = TOP_LEFT) -> None:
        super().__init__(name=name, coords=coords)
        self.anchor = array(anchor)
        self._size: array = array(VECTOR_ZERO)

    size: property(get_size, set_size)


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
                 anchor: tuple[int, int] = TOP_LEFT, rows: int = 1) -> None:
        super().__init__(name=name, coords=coords, anchor=TOP_LEFT)
        self._rows: int = rows

    rows: property = property(get_rows, set_rows)


class HBox(Control):
    '''Contêiner que posiciona seus nós filhos lado-a-lada em um layout horizontal.'''
    DEFAULT_PADDING: tuple[int, int, int, int] = 4, 4, 4, 4
    padding: tuple[int, int, int, int]
    _rect_offset: tuple[int, int] = 0, 0

    def add_child(self, node: Node, at: int = -1) -> None:
        super().add_child(node, at=at)
        new_offset: array = (array(node.get_cell()) + (self.padding[X], self.padding[Y]) + (
            self.padding[W], self.padding[H])) * self.anchor

        self._rect_offset = self._rect_offset[X] + new_offset[X], max(
            self._rect_offset[Y], new_offset[Y])
        self.update_container()

    def remove_child(self, node: Node = None, at: int = -1) -> Node:
        node: Node = super().remove_child(node=node, at=at)

        if self._children_index:
            for child in self._children_index:
                self._rect_offset = max(self._rect_offset, (
                    child.get_cell()[X] + self.padding[X] + self.padding[W]) * self.anchor[X])
        else:
            self._rect_offset = 0

        self.update_container()

        return node

    def update_container(self) -> None:
        current_offset: int = 0

        for child in self._children_index:
            current_offset += self.padding[X]
            child.position = (
                current_offset, self.padding[Y]) - array(self._rect_offset)
            current_offset += child.get_cell()[X] + self.padding[W]

        self.size = self._rect_offset

    def __init__(self, name: str = 'HBox', coords: tuple[int, int] = VECTOR_ZERO,
                 anchor: tuple[int, int] = TOP_LEFT,
                 padding: tuple[int, int, int, int] = DEFAULT_PADDING) -> None:
        super().__init__(name=name, coords=coords, anchor=anchor)
        self.padding = padding


class VBox(Control):
    '''Contêiner que posiciona seus nós filhos lado-a-lada em um layout vertical.'''
    DEFAULT_PADDING: tuple[int, int, int, int] = HBox.DEFAULT_PADDING
    padding: tuple[int, int, int, int]

    def add_child(self, node: Node, at: int = -1) -> None:
        super().add_child(node, at=at)
        new_offset: array = (array(node.get_cell()) + (self.padding[X], self.padding[Y]) + (
            self.padding[W], self.padding[H])) * self.anchor

        self.size = max(
            self.size[X], new_offset[X]), self.size[Y] + new_offset[Y]
        self.update_container()

    def remove_child(self, node: Node = None, at: int = -1) -> Node:
        node: Node = super().remove_child(node=node, at=at)

        if self._children_index:
            for child in self._children_index:
                self.size = max(self.size, (
                    child.get_cell()[Y] + self.padding[Y] + self.padding[H]) * self.anchor[Y])
        else:
            self.size = 0

        self.update_container()

        return node

    def update_container(self) -> None:
        current_offset: int = 0

        for child in self._children_index:
            current_offset += self.padding[Y]
            child.position = (
                self.padding[X], current_offset) - array(self.size)
            current_offset += child.get_cell()[Y] + self.padding[H]

    def __init__(self, name: str = 'VBox', coords: tuple[int, int] = VECTOR_ZERO,
                 anchor: tuple[int, int] = TOP_LEFT,
                 padding: tuple[int, int, int, int] = DEFAULT_PADDING) -> None:
        super().__init__(name=name, coords=coords, anchor=anchor)
        self.padding = padding


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

        # Draw sprite in order
        root.screen.blit(self.atlas.image, self.atlas.rect)
        self.atlas.update()

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

    def _process(self, delta: float) -> None:
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

    class CollisionType(IntEnum):
        PHYSICS = 1  # Área usada para detecção de colisão entre corpos
        AREA = 2  # Área usada para mapeamento (renderização, ou localização).

    type: int = CollisionType.PHYSICS

    def _draw(self, target_pos: tuple[int, int], target_scale: tuple[float, float],
              offset: tuple[int, int]) -> None:
        super()._draw(target_pos, target_scale, offset)
        self._rect.size = self._base_size * target_scale
        self._rect.topleft = array(target_pos) - offset

    def get_cell(self) -> array:
        return array(self._base_size)

    def set_rect(self, value: Rect) -> None:
        self.base_size = array(value.size)
        self._rect = value
        self.rect_changed.emit(self)

    def get_rect(self) -> Rect:
        return self._rect

    def set_base_size(self, value: array) -> None:
        self._base_size = value
        self._rect.size = self._base_size * self.scale
        self.rect_changed.emit(self)

    def get_base_size(self) -> array:
        return self._base_size

    def bounds(self) -> Rect:
        '''Retorna a caixa delimitadora da forma.'''
        return self._rect

    def __init__(self, name: str = 'Shape', coords: tuple[int, int] = VECTOR_ZERO) -> None:
        super().__init__(name=name, coords=coords)
        self._rect: Rect = Rect(VECTOR_ZERO, VECTOR_ZERO)
        self._base_size = array(VECTOR_ZERO)
        self.rect_changed = Entity.Signal(self, 'rect_changed')
        self._debug_fill_bounds = True

    rect: property = property(get_rect, set_rect)
    base_size: property = property(get_base_size, set_base_size)


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


class Panel(Control):
    '''Base Control Node for GUI panels.'''
    DEFAULT_BORDERS: tuple[int, int, int, int] = 2, 2, 2, 2

    borders: Shape
    bg: Shape

    def set_size(self, value: array) -> None:
        super().set_size(value)
        value = array(value)
        self.borders.base_size = value

        self._inner_size = value - \
            (array((self._borders[X], self._borders[Y])
                   ) + (self._borders[W], self._borders[H]))
        self.bg.base_size = self._inner_size

    def get_size(self) -> array:
        return self._size

    def set_anchor(self, value: tuple[int, int]) -> None:
        super().set_anchor(value)
        self.bg.anchor = value
        self.borders.anchor = value
        self.bg.position = array(
            (self._borders[X], self._borders[Y])) * self.bg.anchor
        # self.set_size(self._size) # Updates

    def __init__(self, name: str = 'Panel', coords: tuple[int, int] = VECTOR_ZERO,
                 anchor: tuple[int, int] = TOP_LEFT,  bg_color: Color = colors.WHITE,
                 borders_color: Color = colors.GRAY, size: tuple[int, int] = (150, 75),
                 borders: tuple[int, int, int, int] = DEFAULT_BORDERS) -> None:
        super().__init__(name=name, coords=coords, anchor=anchor)
        self._size = array(size)
        self._borders: tuple[int, int, int, int] = borders

        # Determina o tamanho do retângulo interno (BackGround)
        topleft: array = array((borders[X], borders[Y]))
        base_size: array = size - (topleft + (borders[W], borders[H]))
        self._inner_size: array = base_size
        # offset: array = array(self.get_cell()) * - self.anchor

        # Set the border square
        bar: Shape = Shape(name='Borders')
        bar.color = borders_color
        bar.anchor = array(TOP_LEFT)
        bar.rect = Rect(VECTOR_ZERO, size)
        bar._draw_cell = True
        self.borders = bar
        self.add_child(bar)

        # Set the BackGround
        bar: Shape = Shape(name='BG', coords=topleft)
        bar.anchor = array(TOP_LEFT)
        bar.color = bg_color
        bar.rect = Rect(topleft, base_size)
        bar._draw_cell = True
        self.bg = bar
        self.add_child(bar)

        self.set_anchor(anchor)

    size: property = property(get_size, set_size)


class ProgressBar(Panel):
    bar: Shape

    def set_progress(self, value: float) -> None:
        self._progress = value
        self._update_progress(value)

    def update_progress(self, value: float) -> None:
        '''Atualiza o tamanho da barra de progresso de forma ascendente.'''
        self.bar.base_size[self._grow_coord] = self._inner_size[self._grow_coord] * value

    def update_progress_flip(self, value: float) -> None:
        '''Atualiza o tamanho da barra de progresso de forma descendente.'''
        base_size: int = self._inner_size[self._grow_coord]
        length: int = base_size * value

        self.bar.position[self._grow_coord] = base_size - length
        self.bar.base_size[self._grow_coord] = self._inner_size[self._grow_coord] * value

    def get_progress(self) -> float:
        return self._progress

    def __init__(self, name: str = 'ProgressBar', coords: tuple[int, int] = VECTOR_ZERO,
                 bg_color: Color = colors.BLUE, bar_color: Color = colors.GREEN,
                 borders_color: Color = colors.RED, size: tuple[int, int] = (125, 25),
                 borders: tuple[int, int, int, int] = Panel.DEFAULT_BORDERS,
                 v_grow: bool = False, flip: bool = False) -> None:
        super().__init__(name=name, coords=coords, bg_color=bg_color,
                         borders_color=borders_color, size=size, borders=borders)
        self.color = bg_color
        self.size = size

        self._progress: float = .5
        self._grow_coord: int = int(v_grow)
        self._update_progress: Callable = self.update_progress if (
            flip ^ (not v_grow)) else self.update_progress_flip

        # Set the Inner Bar
        topleft: tuple[int, int] = borders[X], borders[Y]
        bar: Shape = Shape(name='Bar', coords=topleft)
        bar.anchor = array(TOP_LEFT)
        bar.color = bar_color
        bar.rect = Rect(topleft, self._inner_size)
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

    def _process(self, delta: float) -> None:
        self._physics_process(delta)

    def _physics_process(self, delta: float) -> None:
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


class Popup(Panel):
    popup_finished: Node.Signal
    hided: Node.Signal
    pop_duration: float

    def add_child(self, node: Node, at: int = -1) -> None:

        if node.name == 'Borders' or node.name == 'BG':
            super().add_child(node, at=at)
            return

        if node == self or node._parent:
            raise Node.InvalidChild

        if self._children_refs.get(node.name, False):
            raise Node.DuplicatedChild

        if at == -1:
            self._hidden_children.append(node)
        else:
            self._hidden_children.insert(at, node)

    def remove_child(self, node: Node = None, at: int = -1) -> Node:
        node: Node = super().remove_child(node=node, at=at)

        if node in self._hidden_children:
            self._hidden_children.remove(node)

        return node

    def popup(self, do_ease: bool = None) -> None:

        if do_ease is None:
            do_ease = self._do_ease

        if do_ease:
            tween: Tween = Tween(self)
            tween.tween_finished.connect(tween, self, self._on_Popup)
            tween.interpolate_attribute(
                'size', self._size, self._base_size, self.pop_duration)
        else:
            self._on_Popup()

    def hide(self, do_ease: bool = None) -> None:
        '''Esconde o conteúdo do popup da tela'''

        if do_ease is None:
            do_ease = self._do_ease

        while self._children_index[-1].name != 'BG':
            self._hidden_children.append(
                self.remove_child(self._children_index[-1]))

        if do_ease:
            tween: Tween = Tween(self)
            tween.tween_finished.connect(tween, self, self._on_Hide)
            tween.interpolate_attribute(
                'size', self._size, array(VECTOR_ZERO), self.pop_duration)
        else:
            self._on_Hide()

    def _on_Popup(self) -> None:
        '''Apresenta o conteúdo do popup na tela.'''
        child: Node

        while self._hidden_children:
            child = self._hidden_children.pop()
            super().add_child(child)

        self.popup_finished.emit()

    def _on_Hide(self) -> None:
        self.hided.emit()

    def __init__(self, name: str = 'PopUp', coords: tuple[int, int] = VECTOR_ZERO,
                 anchor: tuple[int, int] = TOP_LEFT, do_ease: bool = True, pop_duration: float = .3,
                 bg_color: Color = colors.WHITE, borders_color: Color = colors.GRAY,
                 size: tuple[int, int] = (150, 75),
                 borders: tuple[int, int, int, int] = Panel.DEFAULT_BORDERS) -> None:
        self._hidden_children: list[Node] = []
        super().__init__(name=name, coords=coords, anchor=anchor, bg_color=bg_color,
                         borders_color=borders_color, size=size, borders=borders)
        self._do_ease = do_ease
        self._base_size: tuple[int, int] = size
        self.pop_duration = pop_duration
        self.popup_finished = Node.Signal(self, 'popup_finished')
        self.hided = Node.Signal(self, 'hided')

        if do_ease:
            self.size = array(VECTOR_ZERO)
            # self.bg.rect = Rect(VECTOR_ZERO, VECTOR_ZERO)
            # self.borders.rect = Rect(VECTOR_ZERO, VECTOR_ZERO)
            # self._size = array(VECTOR_ZERO)
        # else:
            # self.bg.rect = Rect(VECTOR_ZERO, size)
            # self._size = array(size)


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

        root.screen.blit(self._surface(), target_pos - offset)

    def get_cell(self) -> tuple[int, int]:
        return self.font.size(self.text)

    def set_color(self, value: Color) -> None:
        super().set_color(value)
        self._surface = self.update_surface

    def __init__(self, font: font.Font, name: str = 'Label', coords: tuple[int, int] = VECTOR_ZERO,
                 color: Color = colors.BLACK, text: str = '') -> None:
        super().__init__(name=name, coords=coords)
        self.font = font
        self.color = color
        self.anchor = array(TOP_LEFT)

        self._current_surface: Surface
        self._surface: Callable = self.update_surface
        self._text: str
        self.set_text(text)

    text: property = property(get_text, set_text)


class Text(Control):
    text_changed: Node.Signal
    font: font.Font

    _labels: list[Label]
    _text: str = ''

    def set_text(self, *text: str) -> None:
        txt: str = ''.join(text)
        newlines: deque[tuple[int, int]] = deque()
        self._text = txt

        for label in self._labels:
            self.remove_child(label)
        self._labels = []

        # Search for `\n` (newlines)
        matches: Iterator[Match] = re.finditer('[\n]', txt)
        match: Match
        parser_index: int = 0

        for match in matches:
            newlines.append((parser_index, match.start()))
            parser_index = match.end()

        if len(txt) > parser_index:
            newlines.append((parser_index, len(txt)))

        line_id: int = 0
        current_offset: tuple[int, int] = VECTOR_ZERO
        area: Rect = Rect(VECTOR_ZERO, VECTOR_ZERO)

        while newlines:
            # Make line
            span: tuple[int, int] = newlines.popleft()

            label: Label = Label(self.font, name=f'Label{line_id}', coords=(
                0, current_offset[Y]), color=self.color, text=txt[span[0]:span[1]])
            area = area.union(Rect((0, current_offset[Y]), label.get_cell()))
            current_offset += array(label.get_cell())
            self._labels.append(label)
            self.add_child(label)
            line_id += 1

        # Desloca o texto de acordo com a âncora da caixa de texto
        for label in self._labels:
            label.position = array(label.position) - \
                array(area.size, dtype=int) * self.anchor

        self.size = area.size
        self.text_changed.emit()

    def get_text(self) -> str:
        return self._text

    def set_color(self, value: Color) -> None:
        super().set_color(value)

        for label in self._labels:
            label.set_color(value)

    def __init__(self, font: font.Font, name: str = 'Text', coords: tuple[int, int] = VECTOR_ZERO,
                 anchor: tuple[int, int] = TOP_LEFT, color: Color = colors.BLACK) -> None:
        super().__init__(name=name, coords=coords, anchor=anchor)
        self.text_changed = Node.Signal(self, 'text_changed')
        self._labels = []
        self.font = font
        self.set_color(color)


class BaseButton(Control):
    HOLD_EVENT: str = 'hold'
    RELEASE_EVENT: str = 'released'

    focus_changed: Node.Signal
    is_pressed: bool = False
    label: Text
    _rect: Rect

    def _process(self, delta: float) -> None:
        self._mouse_input()

    def _input_event(self, event: InputEvent) -> None:

        def hold() -> None:
            global root
            nonlocal self

            if self._rect.collidepoint(pygame.mouse.get_pos()):
                self._hold()

        def release() -> None:
            global root
            nonlocal self

            if self.is_pressed and self._rect.collidepoint(pygame.mouse.get_pos()):
                self._release()

        {
            BaseButton.HOLD_EVENT: hold,
            BaseButton.RELEASE_EVENT: release,
        }[event.tag]()

    def _release(self) -> None:
        global root
        self._pressed()
        root.grab_focus(self)
        self.pressed.emit()

    def _hold(self) -> None:
        global root
        self._mouse_input = self._holding
        self._on_hold()
        self.is_pressed = True

    @abstractmethod
    def _on_hold(self) -> None:
        '''Método virtual chamado logo que o botão for pressionado.'''

    @abstractmethod
    def _pressed(self) -> None:
        '''Método virtual chamado após o botão ter sido pressionado.'''

    @abstractmethod
    def _focused_mouse_input(self) -> None:
        '''Método virtual chamado enquanto o botão está selecionado.'''

    @abstractmethod
    def _unfocused_mouse_input(self) -> None:
        '''Método virtual chamado enquanto o botão está fora de foco.'''

    @abstractmethod
    def _holding(self) -> None:
        '''Método virtual chamado enquanto o botão está sendo pressionado'''

    def _update_rect(self) -> None:
        area: array = array(self.get_cell()) * self.scale
        self._rect.topleft = self.position - area * self.anchor
        self._rect.size = area

    def set_anchor(self, value: tuple[int, int]) -> None:
        super().set_anchor(value)
        self.label.anchor = value

    def set_is_on_focus(self, value: bool) -> None:
        if value:
            root.grab_focus(self)
            return
        self._set_is_on_focus(value)

    def _set_is_on_focus(self, value: bool) -> None:
        self._is_on_focus = value
        self._mouse_input = self._focused_mouse_input if value else self._unfocused_mouse_input
        self.focus_changed.emit(value)

    def get_is_on_focus(self) -> bool:
        return self._is_on_focus

    def __init__(self, font: font.Font, name: str = 'BaseButton',
                 coords: tuple[int, int] = VECTOR_ZERO, anchor: tuple[int, int] = TOP_LEFT,
                 size: tuple[int, int] = None, padding: tuple[int, int] = (20, 5),
                 text: str = '') -> None:
        '''
        If `size` is not passed, the button `size` will be calculated
        based on the `padding`, the `text` and the `font`.
        '''
        self.label = Text(font, anchor=anchor)
        self.label.set_text(text)

        if size is None:
            self.size = array(self.label.size) + array(padding) * 2

        super().__init__(name=name, coords=coords, anchor=anchor)
        self.pressed = Node.Signal(self, 'pressed')
        self.focus_changed = Node.Signal(self, 'focus_changed')

        self.color = colors.BLUE
        self._rect = Rect(VECTOR_ZERO, VECTOR_ZERO)
        self._mouse_input: Callable[[], None] = self._unfocused_mouse_input
        self._is_on_focus = False

        self.add_child(self.label)

        # Registra os eventos de entrada do mouse
        input.register_event(
            self, MOUSEBUTTONDOWN, Input.Mouse.LEFT_CLICK, BaseButton.HOLD_EVENT)
        input.register_event(
            self, MOUSEBUTTONUP, Input.Mouse.LEFT_CLICK, BaseButton.RELEASE_EVENT)
        self._update_rect()

    is_on_focus: property = property(get_is_on_focus, set_is_on_focus)


class Link(BaseButton):
    normal_color: Color = colors.BLUE
    pressed_color: Color = colors.GREEN
    highlight_color: Color = colors.CYAN
    focus_color: Color = colors.PURPLE

    def _on_hold(self) -> None:
        self.set_color(self.pressed_color)

    def _focused_mouse_input(self) -> None:

        if self._rect.collidepoint(pygame.mouse.get_pos()):
            self.set_color(self.highlight_color.lerp(self.focus_color, .5))
        else:
            self.set_color(self.focus_color)

    def _unfocused_mouse_input(self) -> None:
        self._update_rect()

        if self._rect.collidepoint(pygame.mouse.get_pos()):
            self.set_color(self.highlight_color)
        else:
            self.set_color(self.normal_color)

    def open_link(self) -> None:
        webbrowser.open(self._action)

    def set_color(self, value: Color) -> None:
        super().set_color(value)
        self.label.set_color(value)

    def set_action(self, value: str) -> None:
        self._action = value

        if value.startswith('https://'):
            self._do_action = self.open_link
        else:
            self._do_action = lambda: None

    def get_action(self) -> None:
        return self._action

    def __init__(self, font: font.Font, name: str = 'Link', coords: tuple[int, int] = VECTOR_ZERO,
                 anchor: tuple[int, int] = TOP_LEFT, size: tuple[int, int] = None,
                 padding: tuple[int, int] = (20, 5), text: str = '', action: str = '') -> None:
        super().__init__(font, name=name, coords=coords,
                         anchor=anchor, size=size, padding=padding, text=text)
        self.set_color(self.color)
        self._do_action: Callable
        self._action: str
        self.set_action(action)

    action: property = property(get_action, set_action)


class TextureButton(BaseButton):
    normal_icon_id: int = 0
    pressed_icon_id: int = 1
    hover_icon_id: int = 2
    # Extras
    focus_icon_id: int = 1
    highlight_icon_id: int = 2  # Alternativa ao hover quando em foco

    _sprite: Sprite
    _icon: Icon

    class NoTexture(UserWarning):
        '''A lista de texturas passada ao nó está vazia.'''

    def _on_hold(self) -> None:
        self._icon.set_texture(self.pressed_icon_id)

    def _focused_mouse_input(self) -> None:

        if self._rect.collidepoint(pygame.mouse.get_pos()):
            self._icon.set_texture(self.highlight_icon_id)
        else:
            self._icon.set_texture(self.focus_icon_id)

    def _unfocused_mouse_input(self) -> None:

        if self._rect.collidepoint(pygame.mouse.get_pos()):
            self._icon.set_texture(self.hover_icon_id)
        else:
            self._icon.set_texture(self.normal_icon_id)

    def _update_rect(self) -> None:
        label_size: tuple[int, int] = self.label.get_cell()
        icon_size: tuple[int, int] = self._sprite.get_cell()
        self.size = max(label_size[X], icon_size[X]), max(
            label_size[Y], icon_size[Y])
        super()._update_rect()

    def __init__(self, font: font.Font, textures: list[Surface], name: str = 'TextureButton',
                 coords: tuple[int, int] = VECTOR_ZERO, size: tuple[int, int] = None,
                 padding: tuple[int, int] = (20, 5), text: str = '') -> None:
        super().__init__(font, name=name, coords=coords,
                         size=size, padding=padding, text=text)
        self._icon = Icon(textures)
        self._sprite = Sprite(atlas=self._icon)
        self._update_rect()
        self._sprite.position = array(
            (0, self.label.get_cell()[X])) - self.get_cell() * self.anchor

        if not textures:
            raise TextureButton.NoTexture

        # Fallback to normal
        if len(textures) < 2:
            self.highlight_icon_id = self.hover_icon_id = 0

            if len(textures) < 1:
                self.focus_icon_id = self.pressed_icon_id = 0


class RichTextLabel(Control):
    default_font: font.Font
    fonts: dict[str, font.Font]

    _content: list[Node]
    _text: str = ''

    def set_rich_text(self, *text: str) -> None:
        '''Faz o processamento da string via conversão de tags (parser)
        para renderizá-la numa caixa de texto inteligente.'''

        txt: str = ''.join(text)
        metadata: deque[dict[str, ]] = deque()

        # Busca por
        # `<a = path/link/or/event > ... <\a>` (links) or
        # <img = path/to/icon /> (icons)
        matches: Iterator[Match] = re.finditer(
            r'(<a.*>.*</a[ ]*>)|(<img.*>.*</img[ ]*>)', txt)

        def filter(match: Match) -> str:
            meta: str

            # TODO -> Adicionar dados anexos
            for tag, dtype in {'<a': 'link', '<img': 'icon'}.items():
                if txt[match.start():match.end()].startswith(tag):
                    meta = dtype
                    break

            return meta

        def add_text(start: int, end: int) -> None:
            nonlocal metadata
            metadata.append({'type': 'text', 'span': (start, end)})

        parser_index: int = 0
        match: Match
        # Divide as seções de acordo com as correspondências
        for match in matches:
            if match.start() != parser_index:
                add_text(parser_index, match.start())

            span: tuple = match.span()
            metadata.append({'type': filter(match), 'span': span})
            parser_index = span[1]

        if len(txt) > parser_index:
            add_text(parser_index, len(txt))

        # Processa o layout/ aparência de cada seção do texto
        section_id: int = 0
        current_offset: tuple[int, int] = VECTOR_ZERO
        current_color: Color = self.color
        current_font: font.Font = self.default_font
        area: Rect = Rect(VECTOR_ZERO, VECTOR_ZERO)

        def add_text(i: int, span: tuple[int, int]) -> Node:
            nonlocal self, txt, current_font, current_color, current_offset, area

            text: Text = Text(current_font, name=f'Text{i}', coords=(
                0, current_offset[Y]), anchor=self.anchor, color=current_color)
            text.set_text(txt[span[0]:span[1]])
            self._content.append(text)
            self.add_child(text)
            area = area.union(Rect((0, current_offset[Y]), text.get_cell()))
            current_offset = text.position + text.size

        def add_link(i: int, span: tuple[int, int]) -> None:
            nonlocal self, txt, current_font, current_color, current_offset
            text: str = txt[span[0]:span[1]]
            open_tag: Match = re.search(r'>', text)
            close_tag: Match = re.search(r'</a[ ]*>', text)

            link: Link = Link(
                current_font, name=f'Link{i}', coords=(0, current_offset[Y]),
                anchor=self.anchor, text=text[open_tag.end():close_tag.start()])
            self._content.append(link)
            self.add_child(link)
            area.union(Rect((0, current_offset[Y]), link.get_cell()))
            current_offset = link.position + link.size

        def add_icon(i: int, to_pos: tuple[int, int]) -> None:
            # TODO
            #icon: Icon()
            pass

        while metadata:
            content: dict[str, ] = metadata.popleft()
            {
                'text': add_text,
                'link': add_link,
                'icon': add_icon,
            }[content['type']](section_id, content['span'])
            section_id += 1

        # Desloca o conteúdo de acordo com a âncora da caixa de texto
        # for item in self._content:
        #     item.position[Y] = item.position[Y] - area.size[Y] * self.anchor[Y]

        self.size = area.size

    def get_rich_text(self) -> str:
        return self._text

    def __init__(self, default_font: font.Font, fonts: dict[str, font.Font] = None,
                 name: str = 'RichTextLabel', coords: tuple[int, int] = VECTOR_ZERO,
                 anchor: tuple[int, int] = TOP_LEFT, color: Color = colors.WHITE) -> None:
        super().__init__(name=name, coords=coords, anchor=anchor)
        self._content = []
        self.default_font = default_font
        self.color = color


class Button(BaseButton):
    normal_color: Color = colors.WHITE
    highlight_color: Color = colors.CYAN
    focus_color: Color = colors.BLUE
    pressed_color: Color = colors.GREEN

    pressed: Node.Signal
    panel: Panel
    _is_on_focus: bool = False

    def _pressed(self) -> None:
        self.color = self.pressed_color

    def _unfocused_mouse_input(self) -> None:

        if self._rect.collidepoint(pygame.mouse.get_pos()):
            self.panel.bg.color = self.highlight_color
        else:
            self.panel.bg.color = self.normal_color

    def _focused_mouse_input(self) -> None:
        if self._rect.collidepoint(pygame.mouse.get_pos()):
            self.panel.bg.color = self.highlight_color.lerp(
                self.focus_color, .5)
        else:
            self.panel.bg.color = self.focus_color

    def set_anchor(self, value: tuple[int, int]) -> None:
        super().set_anchor(value)
        self.panel.set_anchor(value)

    def _on_Label_text_changed(self) -> None:
        self.size = array(self.label.size) + array(self._padding) * 2
        self.panel.size = self.size

    def __init__(self, font: font.Font, name: str = 'BaseButton',
                 coords: tuple[int, int] = VECTOR_ZERO, anchor: tuple[int, int] = TOP_LEFT,
                 size: tuple[int, int] = None, padding: tuple[int, int] = (20, 5),
                 text: str = '') -> None:
        '''
        If `size` is not passed, the button `size` will be calculated
        based on the `padding`, the `text` and the `font`.
        '''
        self.panel = Panel()
        super().__init__(font, name=name, coords=coords, anchor=anchor,
                         size=size, padding=padding, text=text)
        self._padding: tuple[int, int] = padding
        self.panel.bg.color = self.color
        self.panel.size = self.size
        self.add_child(self.panel, 0)
        self.set_anchor(anchor)

        self.label.connect(self.label.text_changed, self,
                           self._on_Label_text_changed)


class PopupDialog(Popup):
    label: RichTextLabel

    def set_text(self, *value: str) -> None:
        self.label.set_rich_text(*value)
        self._base_size = array(self.label.size) + \
            (self._borders[X], self._borders[Y]) + \
            (self._borders[W], self._borders[H]) + \
            (self._padding[X], self._padding[Y]) + \
            (self._padding[W], self._padding[H])

    def set_anchor(self, value: tuple[int, int]) -> None:
        super().set_anchor(value)
        self.label.anchor = value

    def __init__(self, default_font: font.Font, fonts: dict[str, font.Font] = None,
                 name: str = 'PopUp', coords: tuple[int, int] = VECTOR_ZERO,
                 anchor: tuple[int, int] = TOP_LEFT, do_ease: bool = True,
                 pop_duration: float = 0.3, bg_color: Color = colors.WHITE,
                 borders_color: Color = colors.GRAY, size: tuple[int, int] = (150, 75),
                 borders: tuple[int, int, int, int] = Panel.DEFAULT_BORDERS,
                 padding: tuple[int, int, int, int] = (32, 32, 32, 32)) -> None:
        label: RichTextLabel = RichTextLabel(
            default_font, fonts, name='Dialog',  anchor=anchor)
        self.label = label
        self._padding: tuple[int, int, int, int] = padding
        size = array(size) + (padding[X], padding[Y]
                              ) + (padding[W], padding[H])
        super().__init__(name=name, coords=coords, anchor=anchor, do_ease=do_ease,
                         pop_duration=pop_duration,  bg_color=bg_color, borders_color=borders_color,
                         size=size, borders=borders)
        label.color = colors.BLACK
        self.add_child(label)


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
    locale_changed: Node.Signal

    # Default Screen - Onde os nós da árvore irão desenhar sobre.
    # Atualmente os valores não são sincronizados individualmente, ao invés disso,
    # a propriedade `screen_size`` é usado como interface para os mesmos.
    screen: Surface = None
    _screen_width: int = 640
    _screen_height: int = 480
    _screen_rect: Rect = Rect(VECTOR_ZERO, (_screen_width, _screen_height))
    screen_color: Color = colors.WHITE

    # PyGame Sprites Groups
    DEFAULT_GROUP: str = 'default'

    sprites_groups: dict[str, sprite.Group] = {
        DEFAULT_GROUP: sprite.Group(),
    }

    # Game Clock
    clock: pygame.time.Clock = None
    fixed_fps: int = 60  # Frames Per Second

    # Tweening
    _active_tweens: list[Tween] = []

    _instance = None
    tree_pause: int = 0
    groups: dict[str, list[Node]] = {}

    _locale: str = 'en'
    _locales: dict[str, ]
    _current_scene: Node = None
    _last_time: float = 0.0

    FOCUS_ACTION_DOWN: str = 'focus_action_down'
    FOCUS_ACTION_UP: str = 'focus_action_up'
    _current_focus: BaseButton = None

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

        if self.current_scene is None:
            warnings.warn('The Game needs an active scene to be able to run.')
            return

        while True:
            # tick = self.clock.tick(self.fixed_fps)
            self.clock.tick(self.fixed_fps)
            delta: float = self.clock.get_fps() / self.fixed_fps
            # print(self.clock.get_fps() / self.fixed_fps)
            # print(tick / self.fixed_fps)
            # print(tick / max(0.0001, self.clock.get_fps()))

            self.screen.fill(self.screen_color)
            # Preenche a tela

            input._tick()
            # Propaga as entradas

            # Processa os tweens ativos na lista
            for tween in self._active_tweens:
                tween._process(delta)

            self._propagate(delta)
            # Propaga o processamento
            # `Sprites` e `Labels`` aplicam blit individualmente no método `_draw``

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

    def grab_focus(self, node: BaseButton) -> None:

        if not self._current_focus is None:
            self._current_focus._set_is_on_focus(False)

        node._set_is_on_focus(True)
        self._current_focus = node

    def get_fps(self) -> float:
        return self.clock.get_fps()

    def set_load_method(self, method: Callable[[str, str], dict[str, ]], dir: str) -> None:
        self._locale_load_method = method
        self._locales_dir = dir

    def set_locale(self, to: str) -> None:

        if to in self._cached_locales:
            self._locales = self._cached_locales[to]
        else:
            if self._locale:
                self._cached_locales[self._locale] = self._locales

            self._locales = self._locale_load_method(self._locales_dir, to)

        if self._locale != to:
            self.locale_changed.emit(to)

        self._locale = to

    def tr(self, key: str) -> None:
        '''Retorna uma string de acordo com a locale (tradução) carregada no momento'''
        return self._locales[key]

    def clear_cached_locales(self) -> None:
        '''Remove as locales que não estão sendo usadas da memória.'''
        del self._cached_locales
        self._cached_locales = {}

    def set_screen_size(self, value: tuple[int, int]) -> None:
        self._screen_width, self._screen_height = value
        self._screen_rect.topleft = value

    def get_screen_size(self) -> tuple[int, int]:
        return self._screen_width, self._screen_height

    # def set_current_scene(self, scene: object, *args, **kwargs) -> None:
    #     self._current_scene = scene(args, kwargs)

    def set_current_scene(self, scene: Node) -> None:

        if self._current_scene:
            self.remove_child(self._current_scene)

        self._current_scene = scene
        self.add_child(scene)

    def get_current_scene(self) -> Node:
        return self._current_scene

    def _input_event(self, event: InputEvent) -> None:
        # FOCUS_ACTION
        if not self._current_focus:
            return

        if event.tag is SceneTree.FOCUS_ACTION_DOWN:
            self._current_focus._hold()
        else:
            self._current_focus._release()

    def __new__(cls):
        # Torna a classe em uma Singleton
        if cls._instance is None:
            # Criação do objeto
            cls._instance = super(SceneTree, cls).__new__(cls)

        return cls._instance

    def __init__(self, name: str = 'root', coords: tuple[int, int] = VECTOR_ZERO) -> None:
        super().__init__(name=name, coords=coords)
        self._is_on_tree = True
        self._locales = {}
        self._locales_dir: str = ''
        self._cached_locales: dict[str, dict[str, ]] = {}
        self._locale_load_method: Callable[[str, str], dict[str, ]] = None

        # Events
        self.pause_toggled = Node.Signal(self, 'pause_toggled')
        self.locale_changed = Node.Signal(self, 'locale_changed')

        for key in (K_RETURN, K_SPACE, K_KP_ENTER):
            input.register_event(self, KEYDOWN, key, SceneTree.FOCUS_ACTION_UP)
            input.register_event(self, KEYUP, key, SceneTree.FOCUS_ACTION_DOWN)

    screen_size: property = property(get_screen_size, set_screen_size)
    current_scene: property = property(get_current_scene, set_current_scene)


# Singletons
input: Input = Input()  # Singleton usado na captura de inputs
# Nó Singleton que constitui a raiz da árvore da cena.
root: SceneTree = SceneTree()
