from abc import ABC, abstractmethod
from functools import wraps
from typing import Callable, Iterator, Match, Union

import pygame
from pygame import Color, Surface, Vector2
from pygame import sprite, draw, font, mouse, transform
from pygame.locals import *
from sys import exit, argv
from os import path

# Other imports
import re
import webbrowser
import pytweening as tween
from enum import IntEnum
from math import inf, log2, sqrt
from numpy import array, ndarray
from numpy.linalg import norm
from collections import deque

# Constants & Utils
from .lib.vectors import *
from .lib.env import *
from .lib import colors
from .lib.utils import *

# Debug Mode Flags & Tools
IS_DEBUG_ENABLED: bool = '-t' in argv
IS_DEV_MODE_ENABLED: bool = IS_DEBUG_ENABLED and '-d' in argv
GIZMO_RADIUS: int = 2
NONE_CALL: Callable[..., None] = lambda *args, **kwargs: None

# Inicializa os módulos do PyGame
pygame.init()


def debug_call(cls: Callable, dbg_alt: Callable = None):
    '''Decorador que faz o redirecionamento de uma chamada quando em modo de debug.'''

    if IS_DEBUG_ENABLED:
        return dbg_alt if dbg_alt else NONE_CALL
    else:
        return cls

# Decorator
def debug_method(dbg_alt: Callable = None):
    '''Decorador que faz o redirecionamento de uma função quando em modo de debug.
        Se o modo de debug não está ativo, retorna um método vazio, por padrão.
        Caso desejado usar um método alternativo passe a callback como parâmetro da annotation. Ex.:
            # Emite uma mensagem de log, direcionada de acordo com o modo de execução.
            @debug_method(print)
            def log(s: str) -> None:
                ...
    '''
    def inner_function(function):
        if dbg_alt:
            # Redireciona para o alternativo.
            if IS_DEBUG_ENABLED:
                return dbg_alt
        else:
            # Desabilita a função.
            if not IS_DEBUG_ENABLED:
                return NONE_CALL

        # Retorna um invólucro para a função decorada.
        # @wraps(function)
        # def wrapper(*args, **kwargs):
        #     return function(*args, **kwargs)
        # return wrapper
        return function
    return inner_function


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
    position: ndarray

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

        def connect(self, owner, observer, method: Callable, *args) -> None:
            '''Conecta o sinal ao método indicado. O mesmo será chamado quando o nó for emitido.'''
            if owner != self.owner:
                raise Entity.Signal.NotOwner

            if self._observers.get(observer) != None:
                raise Entity.Signal.AlreadyConnected

            self._observers[observer] = (method, args)

        def disconnect(self, owner, observer) -> None:
            '''Desconecta o método pertencente ao nó indicado desse sinal.'''
            if self._is_emitting:
                self._cache_disconnections.append((owner, observer))
                return

            if owner != self.owner:
                raise Entity.Signal.NotOwner

            if self._observers.pop(observer, None) == None:
                raise Entity.Signal.NotConnected

        def disconnect_all(self, owner) -> None:
            for observer, _ in self._observers:
                self.disconnect(owner, observer)

        def emit(self, *args) -> None:
            '''Emite o sinal, propagando chamadas aos métodos conectados.
            Os argumentos passados para as funções conectadas são, respectivamente:
            os argumentos passados ao conectar a função, em seguida,
            os argumentos passados na emissão.'''
            self._is_emitting = True

            for observer, data in self._observers.items():
                data[0](*(data[1] + args))

            self._is_emitting = False
            # Desconecta os sinais colocados na fila durante a emissão.
            while self._cache_disconnections:
                self.disconnect(*self._cache_disconnections.popleft())

        def __init__(self, owner, name: str) -> None:
            self.owner = owner
            self.name = name
            self._is_emitting: bool = False
            self._observers: dict[Entity, tuple[Callable, ]] = {}
            self._cache_disconnections: deque[tuple[Node, Node]] = deque()

    # Decorador
    def debug(dbg_alt: Callable = None):
        '''Decorador que habilita ou substitui uma função da classe quando em modo de debug.
        Observe que se a função alternativa não for passada, a função será desabilitada
        **quando o modo de debug estiver desabilitado.**'''
        def inner_function(function):
            if dbg_alt:
                # Redireciona para o alternativo.
                if IS_DEBUG_ENABLED:
                    return dbg_alt
            else:
                # Desabilita a função.
                if not IS_DEBUG_ENABLED:
                    return NONE_CALL
            return function

        return inner_function

    def _draw(self, target_pos: tuple[int, int] = None, target_scale: tuple[float, float] = None,
              offset: tuple[int, int] = None) -> None:
        '''Atualiza as pinturas na tela.
        Recebe uma posição, escala e deslocamento pré-calculados.'''
        self._draw_cell(target_pos, target_scale, offset)

    def _draw_cell_(self, target_pos: tuple[int, int] = None,
                    target_scale: tuple[float, float] = None,
                    offset: tuple[int, int] = None) -> None:
        '''Desenha o espaço da célula do nó atual. Útil para visualização em modo de testes.'''
        global root
        cell: ndarray = self.get_cell()

        if target_pos is None:
            target_pos = self.position

        if target_scale is None:
            target_scale = self.scale

        target_pos = target_pos + array(self._layer.offset())

        # Desenha o Gizmo
        extents: ndarray = GIZMO_RADIUS * target_scale
        draw.line(root.screen, self._color,
                  (target_pos[X] - extents[X], target_pos[Y]),
                  (target_pos[X] + extents[X], target_pos[Y]))
        draw.line(root.screen, self._color,
                  (target_pos[X], target_pos[Y] - extents[Y]),
                  (target_pos[X], target_pos[Y] + extents[Y]))

        if cell[X] != 0 or cell[Y] != 0:
            # Desenha as bordas da caixa delimitadora
            extents = cell * target_scale

            anchor: ndarray = array(self.anchor)
            draw_bounds(root.screen, target_pos, extents, anchor,
                        self.color, fill=self._debug_fill_bounds)

    def set_cell(self, value: tuple[int, int]) -> None:
        '''Método virtual para determinar um tamanho/ espaço customizado para a célula.'''
        return

    def get_cell(self) -> tuple[int, int]:
        '''Retorna o tamanho/espaço da célula que envolve o nó.'''
        return VECTOR_ZERO

    def connect(self, signal, observer, method: Callable, *args) -> None:
        '''Realiza a conexão de um sinal que pertence ao nó.'''
        try:
            signal.connect(self, observer, method, *args)
        except Entity.Signal.NotOwner:
            raise Entity.SignalNotExists

    def connects(self, observer, connections: tuple[Signal, Callable, list]) -> None:
        '''Um método de atalho para realizar múltiplas conexões num mesmo alvo.'''

        for signal, method, args in connections:
            self.connect(signal, observer, method, *args)

    def disconnect(self, signal: Signal, observer) -> None:
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

    def set_scale(self, value: ndarray) -> None:
        self._scale = value

    def get_scale(self) -> ndarray:
        return self._scale

    def set_can_draw_cell(self, value: bool) -> None:
        self._can_draw_cell = value
        self._draw_cell = self._draw_cell_ if value else NONE_CALL

    def __init__(self, coords: tuple[int, int] = VECTOR_ZERO):
        self.position = array(coords)
        self._scale = array(VECTOR_ONE)
        self._anchor = array(CENTER)
        self._color: Color = Color(0, 185, 225, 125)
        self._debug_fill_bounds: bool = False
        self._layer: CanvasLayer = None
        self.set_can_draw_cell(IS_DEBUG_ENABLED)

    color: Color = property(get_color, set_color)
    scale: ndarray = property(get_scale, set_scale)
    anchor: tuple[int, int] = property(get_anchor, set_anchor)
    can_draw_cell: bool = property(
        lambda self: self._can_draw_cell, set_can_draw_cell)


class Node(Entity):
    '''Classe fundamental que representa um objeto quaisquer do jogo.
    Permite a composição desses objetos em uma estrutura de árvore.
    Sua principal vantagem é a propagação de ações e eventos.'''
    freed: Entity.Signal

    class PauseModes(IntEnum):
        '''Bit-flags para verificação do modo de parada no processamento da árvore.'''
        # Flag para alterar o processamento da árvore (1 == em pausa, 0 == ativo).
        TREE_PAUSED: int = 1
        STOP: int = 2  # Interrompe o processamento do nó e seus filhos
        # Interrompe o processamento do nó, mas continua processando os filhos.
        CONTINUE: int = 4
        IGNORE: int = 8  # Mantém o processando o nó.

    class EmptyName(Exception):
        pass

    class InvalidChild(Exception):
        '''Lançado ao tentar adicionar um filho que já tem um pai, ou, a si mesmo'''
        pass

    class DuplicatedChild(InvalidChild):
        '''Lançado ao tentar inserir um filho de mesmo nome.'''
        pass

    pause_mode: int = PauseModes.IGNORE

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

    def free(self) -> None:
        if self._parent is not None:
            self._parent.remove_child(self)

        # Faz uma cópia pois o vetor será esvaziado durante a iteração.
        children: list[Node] = self._children_index.copy()
        for child in children:
            child.free()

        self.freed.emit(self)

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

        if self._is_on_tree:
            return self._global_position

        if self._parent:
            return self._parent.get_global_position() + self.position

        return tuple(self.position)

    def get_global_scale(self) -> tuple[int, int]:
        '''Calcula a escala do nó, considerando a hierarquia
        (escalas coeficientes dos nós ancestrais.'''

        if self._is_on_tree:
            return self._global_scale

        if self._parent:
            return self._parent.get_global_scale() * self.scale

        return tuple(self.scale)

    def _enter_tree(self) -> None:
        '''Método virtual que é chamado logo após o nó ser inserido a árvore.
        Chamado após este nó ou algum antecedente ser inserido como filho de outro nó na árvore.'''
        self._global_position = self.get_global_position()
        self._global_scale = self.get_global_scale()
        self._is_on_tree = True
        self._layer = self._parent._layer

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

    def _draw_tree(self, parent_offset: ndarray = array(VECTOR_ZERO),
                   parent_scale: ndarray = array(VECTOR_ONE)) -> None:
        target_scale: ndarray = self.scale * parent_scale
        target_pos: ndarray = self.position + parent_offset
        offset: ndarray = self.get_cell() * target_scale * self.anchor

        self._global_position = tuple(target_pos)
        self._global_scale = tuple(target_scale)
        self._draw_order(target_pos, target_scale, offset)

    def _draw_hierarchy(self, target_pos: tuple[int, int], target_scale: tuple[float, float],
                        offset: tuple[int, int]) -> None:
        self._draw(target_pos, target_scale, offset)

        for child in self._children_index:
            child._draw_tree(target_pos, target_scale)

    def _draw_y_sorted(self, target_pos: tuple[int, int], target_scale: tuple[float, float],
                       offset: tuple[int, int]) -> None:
        self._draw(target_pos, target_scale, offset)
        children: list[Node] = self._children_index.copy()

        def partition(children: list[Node], low: int, high: int) -> int:
            i: int = low - 1
            y: int = children[high]._global_position[Y]

            for j in range(low, high):
                if children[j]._global_position[Y] <= y:
                    # Incrementa o índice do menor elemento
                    i = i + 1
                    children[i], children[j] = children[j], children[i]

            _swap_id: int = i + 1
            children[_swap_id], children[high] = children[high], children[_swap_id]

            return _swap_id

        def quick_sort(children: list[Node], low: int, high: int) -> None:
            '''Ordena os nós, iterativamente, de acordo com a posição Y.
                children[] --> Vetor a ser ordenado,
                `low`  --> Índice inicial,
                `high`  --> Índice final.
            '''
            # Cria uma pilha auxiliar
            size = high - low + 1
            stack = [0] * (size)

            # Inicializa o topo da pilha
            top = - 1

            # Empurra os valores iniciais de `low` e `high` para pilha
            top = top + 1
            stack[top] = low
            top = top + 1
            stack[top] = high

            # Continua removendo da pilha enquanto não estiver vazio.
            while top >= 0:
                # Remove `high` e `low`
                high = stack[top]
                top = top - 1
                low = stack[top]
                top = top - 1

                # Define o elemento pivô na sua posição correta da lista ordenada
                pivot_id: int = partition(children, low, high)

                # Se houver um nó no lado esquerdo do pivô,
                # coloca o da esquerda na pilha.
                if pivot_id - 1 > low:
                    top = top + 1
                    stack[top] = low
                    top = top + 1
                    stack[top] = pivot_id - 1

                # Se há elementos no lado direito do pivô,
                # coloca o da direita na pilha.
                if pivot_id + 1 < high:
                    top = top + 1
                    stack[top] = pivot_id + 1
                    top = top + 1
                    stack[top] = high

        @debug_method
        def log(children: list[Node]) -> None:
            l: list[int] = []
            for child in children:
                l.append(child.position[Y])
            return

        quick_sort(children, 0, len(children) - 1)
        log(children)

        for child in children:
            child._draw_tree(target_pos, target_scale)

    def _input(self) -> None:
        '''Método virtual chamado no passo de captura de entradas dos nós.'''
        for child in self._children_index:
            child._input()

    def _input_event(self, event: InputEvent) -> None:
        '''Método virtual chamado quando um determinado evento de entrada ocorrer.'''
        pass

    def _propagate(self, tree_pause: int = 0) -> None:
        '''Propaga os métodos virtuais na hierarquia da árvore, da seguinte forma:
        Primeiro as entradas são tomadas e então os desenhos são renderizados na tela.
        Logo em seguida, após a propagação nos filhos, o método `_process` é executado.'''
        global root
        tree_pause = tree_pause | root.tree_pause | self.pause_mode

        # Propaga os métodos virtuais nos nós filhos.
        for child in self._children_index:
            child._propagate(tree_pause)

        if not (tree_pause & Node.PauseModes.STOP or
                tree_pause & Node.PauseModes.TREE_PAUSED
                and not(
                    self.pause_mode & Node.PauseModes.CONTINUE)):

            self._process()

    def _process(self) -> None:
        '''Método virtual para processamento de dados em cada passo/ frame.
        Para obter o tempo decorrido desde o último frame use: `root.delta`.'''
        pass

    def set_use_y_sort(self, value: bool) -> None:
        self._use_y_sort = value
        self._draw_order = self._draw_y_sorted if value else self._draw_hierarchy

    def __repr__(self) -> str:
        return f'{self.name}: {type(self)}'

    def __init__(self, name: str = 'Node', coords: tuple[int, int] = VECTOR_ZERO) -> None:
        global root
        super().__init__(coords=coords)

        if not name:
            raise Node.EmptyName

        self.freed = Entity.Signal(self, 'freed')
        self.name: str = name
        self._is_on_tree: bool = False
        self._global_position: tuple[int, int] = tuple(coords)
        self._global_scale: tuple[float, float] = VECTOR_ONE
        self._current_groups: list[str] = []
        self._children_index: list[Node] = []
        self._children_refs: dict[str, Node] = {}
        self._parent: Node = None
        self._use_y_sort: bool = False
        self._draw_order: Callable[[tuple[int, int], tuple[float, float], tuple[int, int]], None] =\
            self._draw_hierarchy

    use_y_sort: bool = property(lambda self: self._use_y_sort, set_use_y_sort)


class Camera(Node):

    class ScrollNotDefined(UserWarning):
        '''Warning emitido se nenhum método de rolagem for passado.'''

    class Scroll(ABC):
        '''Classe abstrata usado para definir o método de rolagem da câmera.
        Implementação inspirada na strategy pattern.'''
        target: Node

        @abstractmethod
        def scroll(self) -> None:
            '''Método virtual responsável pela rolagem da câmera.'''

        def __init__(self, target: Node) -> None:
            super().__init__()
            self.target = target
            self._camera: Camera = None

    class Follow(Scroll):

        def scroll(self) -> None:
            self._camera.raw_offset.xy = \
                array(self.target.get_global_position())

            self._camera.raw_offset -= self.target.get_cell() + \
                (self._camera.get_cell() * array(self._camera.anchor) +
                 self.target.get_cell() * array(self.target.anchor))
            self._camera.offset = int(self._camera.raw_offset.x), int(
                self._camera.raw_offset.y)

        def __init__(self, target: Node) -> None:
            super().__init__(target)

    class FollowLimit(Follow):
        limit: tuple[int, int, int, int]

        def scroll(self) -> None:
            super().scroll()
            self._camera.offset = clamp(self.limit[X], self._camera.offset[X], self.limit[W]), \
                clamp(self.limit[Y], self._camera.offset[Y], self.limit[H])
            return

        def set_camera(self, value) -> None:
            self._camera = value

            cell: tuple[int, int] = self._camera.get_cell(
            ) * array(self._camera._global_scale)
            # anchor: ndarray = array(self._camera.anchor)
            xy: ndarray = self.limit[:2]
            wh: ndarray = self.limit[2:] - cell
            self.limit = xy[X], xy[Y], wh[X], wh[Y]
            return

        def __init__(self, target: Node, limit: tuple[int, int, int, int]) -> None:
            super().__init__(target)
            self.limit = limit

        camera: property = property(lambda self: self._camera, set_camera)

    offset: tuple[int, int]
    raw_offset: Vector2
    scroll: Scroll = None

    def _process(self) -> None:
        self.scroll.scroll()

    def get_cell(self) -> tuple[int, int]:
        global root
        return root.screen_size

    def __init__(self, scroll: Scroll, name: str = 'Camera', coords: tuple[int, int] = VECTOR_ZERO) -> None:
        super().__init__(name=name, coords=coords)

        if scroll is None:
            raise Camera.ScrollNotDefined()
        else:
            self.scroll = scroll
            scroll.camera = self

        self.offset = coords
        self.raw_offset = Vector2(*coords)


class CanvasLayer(Node):
    NO_CAMERA_OFFSET: Callable[[], tuple[int, int]] = lambda: VECTOR_ZERO

    def _enter_tree(self) -> None:
        self._is_on_tree = True
        self._layer = self

        for child in self._children_index:
            child._enter_tree()

    def _get_camera_offset(self) -> None:
        return -array(self.active_camera.offset)

    def set_active_camera(self, value: Camera) -> None:
        self._active_camera = value

        if value:
            self.offset = self._get_camera_offset
        else:
            self.offset = CanvasLayer.NO_CAMERA_OFFSET

    def get_active_camera(self) -> Camera:
        return self._active_camera

    def __init__(self, name: str = 'CanvasLayer', coords: tuple[int, int] = VECTOR_ZERO) -> None:
        super().__init__(name=name, coords=coords)
        self.offset: Callable[[], tuple[int, int]] = \
            CanvasLayer.NO_CAMERA_OFFSET
        self._active_camera: Camera = None

    active_camera: Camera = property(get_active_camera, set_active_camera)


class Input:
    '''Classe responsável por gerenciar eventos de entrada.'''
    _instance = None
    events: dict[int, dict[int, list[InputEvent]]] = {}

    class Mouse(IntEnum):
        LEFT_CLICK = 1
        MIDDLE_CLICK = 2
        RIGHT_CLICK = 3
        SCROLL_UP = 4
        SCROLL_DOWN = 5

    class NotANode(Exception):
        '''Lançado ao tentar registrar um evento em um objeto que não e do tipo `Node`.'''
        pass

    class EventNotExists(UserWarning):
        '''Lançado ao tentar remover um evento que não existe.'''

    class EventTypeNotExists(EventNotExists):
        '''Lançado ao tentar remover um evento cujo tipo que não foi registrado.'''

    class EventKeyNotExists(EventNotExists):
        '''Lançado ao tentar remover um evento cujo chave não foi registrada.'''

    class EventTagNotExists(EventNotExists):
        '''Lançado ao tentar remover um evento cujo chave não foi registrada.'''

    def register_event(self, to: Node, input_type: int, key: int, tag: str = '') -> None:

        if not isinstance(to, Node):
            raise Input.NotANode

        event_type: dict[int, list[InputEvent]] = self.events.get(input_type)
        if not event_type:
            event_type = {}
            self.events[input_type] = event_type

        event_key: list[InputEvent] = event_type.get(key)
        if not event_key:
            event_key = []
            event_type[key] = event_key

        event_key.append(InputEvent(input_type, key, tag, to))

    def remove_event(self, to: Node, input_type: int, key: int, tag: str = '') -> None:

        if not isinstance(to, Node):
            raise Input.NotANode

        event_type: dict[int, list[InputEvent]] = self.events.get(input_type)
        if not event_type:
            raise Input.EventTypeNotExists

        event_key: list[InputEvent] = event_type.get(key)
        if not event_key:
            raise Input.EventKeyNotExists

        # TODO -> Optimizar usando um dicionário com base nos nós-alvo.
        target_events: list[InputEvent] = []
        for input_event in event_key:
            if input_event.target == to:
                target_events.append(input_event)

        if not target_events:
            raise Input.EventNotExists

        # TODO -> Optimizar usando um dicionário com base nas tags.
        if tag:
            n_removed_events: int = 0
            for target_event in target_events:
                if target_event.tag == tag:
                    event_key.remove(target_event)
                    n_removed_events += 1

            if n_removed_events == 0:
                raise Input.EventTagNotExists
        else:
            for target_event in target_events:
                event_key.remove(target_event)

    def get_input_strength() -> ndarray:
        '''Método auxiliar para calcular um input axial.'''
        is_pressed = pygame.key.get_pressed()
        keys: dict = {K_w: 0.0, K_a: 0.0, K_s: 0.0, K_d: 0.0}
        strength: ndarray

        for key in keys:
            keys[key] = 1.0 if is_pressed[key] else 0.0

        strength = array([keys[K_d] - keys[K_a], keys[K_s] - keys[K_w]])
        strength_norm = norm(strength)

        if strength_norm:
            strength /= strength_norm

        return strength

    def _tick(self) -> bool:
        '''Passo de captura dos inputs, mapeando-os nos eventos e executando-os.
        Se alguma entrada tiver ocorrido retorna `true`, ou então `falso` caso ocioso.'''
        input_events = pygame.event.get()

        for event in input_events:

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

        return len(input_events) > 0

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
        self._elapsed_time += delta

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
        self._process(root.delta)
        root._active_tweens.append(self)

    # TODO -> `interpolate_method()`
    # def interpolate_method(self, name: str, from_args: tuple = (), to_args: tuple = (),
    #                        args_ease: tuple[Callable] = (), from_kwargs: dict[str,] = {},
    #                        to_kwargs: dict[str,] = {}, kwargs_ease: dict[str, Callable])

    def __init__(self, target: Node) -> None:
        self.target = target
        self.tween_finished = Entity.Signal(self, 'tween_finished')


class Timer():
    '''Helper class to create time-sensitive events.'''
    timeout: Node.Signal
    elapsed_time: float = 0.0
    target_time: float

    def _process(self, delta: float) -> None:
        self.elapsed_time += delta

        if self.elapsed_time >= self.target_time:
            self.timeout.emit(self)

    def __init__(self, time: int) -> None:
        self.target_time = time
        self.timeout = Entity.Signal(self, 'timeout')


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
        self._size: ndarray = array(VECTOR_ZERO)

    size: tuple[int, int] = property(get_size, set_size)


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
        size: ndarray = array(self.cell_space)
        size[X] *= self.rows
        size[Y] *= len(self._children_index) // self.rows
        self.size = size

    def remove_child(self, node=None, at: int = -1) -> Node:
        node: Node = super().remove_child(node=node, at=at)
        self.update_container()

        return node

    def update_container(self) -> None:
        current_pos: ndarray = array(VECTOR_ZERO)
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

    rows: int = property(get_rows, set_rows)


class HBox(Control):
    '''Contêiner que posiciona seus nós filhos lado-a-lada em um layout horizontal.'''
    DEFAULT_PADDING: tuple[int, int, int, int] = 4, 4, 4, 4
    padding: tuple[int, int, int, int]
    _rect_offset: tuple[int, int] = 0, 0

    def add_child(self, node: Node, at: int = -1) -> None:
        super().add_child(node, at=at)
        new_offset: ndarray = (array(node.get_cell()) + (self.padding[X], self.padding[Y]) + (
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
        new_offset: ndarray = (array(node.get_cell()) + (self.padding[X], self.padding[Y]) + (
            self.padding[W], self.padding[H])) * self.anchor

        self.size = max(
            self.size[X], new_offset[X]), self.size[Y] + new_offset[Y]
        self.update_container()

    def remove_child(self, node: Node = None, at: int = -1) -> Node:
        node: Node = super().remove_child(node=node, at=at)

        if self._children_index:
            # FIXME
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
    DEFAULT_SPEED: float = 6.0  # frames/ sec
    frame: int = 0
    speed: float
    _textures: list[Surface]

    def add_spritesheet(self, texture: Surface, h_slice: int = 1, v_slice: int = 1,
                        coords: tuple[int, int] = VECTOR_ZERO,
                        sprite_size: tuple[int, int] = None) -> None:
        '''Realiza o fatiamento da textura de uma spritesheet como a sequencia de sprites.'''

        if sprite_size is None:
            sprite_size = (texture.get_width() / h_slice,
                           texture.get_height() / v_slice)

        for i in range(h_slice):
            for j in range(v_slice):
                self._textures.append(texture.subsurface(
                    array(coords) + (i, j) * array(sprite_size), sprite_size))

    def add_texture(self, *paths: str) -> None:

        for path in paths:
            self._textures.append(pygame.image.load(path))

    def set_textures(self, value: list[Surface]) -> None:
        self._textures = value
        self.set_frame(0)

    def get_frames(self) -> int:
        return len(self._textures)

    def get_texture(self) -> Surface:
        return self._textures[self.frame]

    def __init__(self, speed: float = DEFAULT_SPEED) -> None:
        self._textures = []
        self.speed = speed
        self.textures: list[Surface] = property(
            lambda _self: _self._textures, self.set_textures)


class BaseAtlas(sprite.Sprite):
    '''Classe do PyGame responsável por gerenciar sprites e suas texturas.'''
    base_size: ndarray
    rect: Rect
    image: Surface

    def flip(self) -> None:
        self._flip_h = not self._flip_h
        self._update_flipped()

    def _update_flipped(self) -> None:
        '''Atualiza a imagem com base em seu valor `_flip_h`.'''
        if self._flip_h:
            self._set_rotated(self._angle, transform.flip(
                self._base_texture, True, False))
        else:
            self._set_rotated(self._angle, self._base_texture)

    def _set_rotated(self, angle: float, base_texture: Surface) -> None:
        """Atualiza a imagem para uma textura base rotacionada mantendo o seu centro."""
        # TODO -> Permitir a mudança do ponto âncora.
        rect: Rect = base_texture.get_rect()

        self._base_rect = rect
        self._angle = angle
        self.image = pygame.transform.rotate(base_texture, angle)
        self.rect = self.image.get_rect(center=rect.center)
        self.base_size = array(base_texture.get_size())

    def set_flip(self, value: bool) -> None:
        self._flip_h = value
        self._update_flipped()

    def set_base_texture(self, value: Surface) -> None:
        self._base_texture = value
        self._update_flipped()

    def set_angle(self, value: float) -> None:
        self._angle = value
        self._update_flipped()

    def __init__(self) -> None:
        super().__init__()
        self.base_size = array(VECTOR_ZERO)
        self._flip_h: bool = False
        self._angle: float = 0.0
        self._base_rect: Rect = None
        self._base_texture: Surface = None

    flip_h: bool = property(
        lambda _self: _self._flip_h, set_flip)
    angle: float = property(
        lambda _self: _self._angle, set_angle)
    base_texture: Surface = property(
        lambda _self: _self._base_texture, set_base_texture)


class Icon(BaseAtlas):
    '''Atlas básico para imagens estáticas. Pode comportar múltiplas texturas,
    requer manipulação externa da lista.'''
    textures: list[Surface]
    texture_id: int = 0

    @staticmethod
    def get_spritesheet(texture: Surface, h_slice: int = 1, v_slice: int = 1,
                        coords: tuple[int, int] = VECTOR_ZERO,
                        sprite_size: tuple[int, int] = None) -> list[Surface]:
        '''Realiza o fatiamento da textura de uma spritesheet como uma sequencia de surfaces.'''
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
        self.texture_id = id
        self.set_base_texture(self.textures[id])

    def __init__(self, textures: list[Surface]) -> None:
        super().__init__()
        self.textures = textures
        self.set_texture(len(textures) - 1)


class Atlas(BaseAtlas, ABC):
    _is_static: bool = True
    _is_paused: bool = False
    _play: Callable[[], None] = NONE_CALL
    _current_time: float = 0.0

    def update(self) -> None:
        self._play()

    @abstractmethod
    def _play_sequence(self) -> None:
        '''Processamento dos quadros da animação.'''

    @abstractmethod
    def _update_frame(self) -> None:
        '''Método auxiliar para atualizar um frame da animação.'''

    def set_is_paused(self, value: bool) -> None:
        self._is_paused = value
        self._reset_play()

    def _reset_play(self) -> None:
        self._play = NONE_CALL if self._is_static or self._is_paused else self._play_sequence

    @abstractmethod
    def get_frame(self) -> int:
        '''Retorna o frame atual da sequência sendo tocada.'''

    @abstractmethod
    def set_frame(self, value: int) -> None:
        '''Determina o frame atual da sequência sendo tocada.'''

    def __init__(self) -> None:
        super().__init__()
        self.frame: int = property(self.get_frame, self.set_frame)
        self.is_paused: bool = property(
            lambda _self: _self._is_paused, self.set_is_paused)


class AtlasPage(Atlas):
    '''Atlas com uma única sequência simples de animação, ou único sprite estático.'''
    sequence: TextureSequence

    def _play_sequence(self) -> None:
        global root
        self._current_time = (
            self._current_time + self.sequence.speed * root.delta)\
            % self.sequence.get_frames()
        new_frame: int = int(self._current_time)

        if new_frame != self.sequence.frame:
            # WATCH -> Prevenir frame skip?
            self.sequence.frame = new_frame
            self.set_base_texture(self.sequence.get_texture())

    def _update_frame(self) -> None:

        if self.sequence.textures:
            self.set_base_texture(self.sequence.get_texture())

    def add_texture(self, *paths: str) -> None:
        '''Adiciona uma textura ao atlas.'''
        self.sequence.add_texture(paths)

        if self.sequence.get_frames() > 1:
            self._is_static = False

            if not self._is_paused:
                self._play = self._play_sequence

        self._update_frame()

    def add_spritesheet(self, texture: Surface, h_slice: int = 1, v_slice: int = 1,
                        coords: tuple[int, int] = VECTOR_ZERO,
                        sprite_size: tuple[int, int] = None) -> None:
        '''Realiza o fatiamento da textura de uma spritesheet como sprites de uma animação.'''
        self.sequence.add_spritesheet(
            texture, h_slice, v_slice, coords, sprite_size)

        if self.sequence.get_frames() > 1:
            self._is_static = False

            if not self._is_paused:
                self._play = self._play_sequence

        self._update_frame()

    def load_spritesheet(self, path: str, h_slice: int = 1, v_slice: int = 1,
                         coords: tuple[int, int] = VECTOR_ZERO,
                         sprite_size: tuple[int, int] = None) -> None:
        '''Faz o carregamento de uma textura como uma spritesheet, com o devido fatiamento.'''
        self.add_spritesheet(pygame.image.load(
            path), h_slice=h_slice, v_slice=v_slice, coords=coords, sprite_size=sprite_size)

    def set_textures(self, value: list[Surface]) -> None:
        self.sequence.textures = value
        self._is_static = self.sequence.get_frames() <= 1
        self._reset_play()
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
        self.textures: list[Surface] = property(
            self.get_textures, self.set_textures)


class AtlasBook(Atlas):
    '''Atlas composto por múltiplas animações de sprites.'''
    animations: dict[str, TextureSequence]
    _current_sequence: TextureSequence = None

    def _play_sequence(self) -> None:
        '''Processamento dos quadros da animação.'''
        global root
        self._current_time = (
            self._current_time + self._current_sequence.speed *
            root.delta) % self._current_sequence.get_frames()
        new_frame: int = int(self._current_time)

        if new_frame != self._current_sequence.frame:
            # WATCH -> Prevenir frame-skip?
            self._current_sequence.frame = new_frame
            self.set_base_texture(self._current_sequence.get_texture())

    def _update_frame(self) -> None:
        '''Método auxiliar para atualizar um frame da animação.'''

        if self._current_sequence.textures:
            self.set_base_texture(self._current_sequence.get_texture())

    def _play_once(self) -> None:
        '''Similar a `_play_sequence`, processa a animação, porém para ao atingir
        o último frame da sequência (Muda para o estado "estático").'''
        global root
        new_time: float = self._current_time + self._current_sequence.speed * root.delta
        new_frame: int = int(new_time)
        frames: int = self._current_sequence.get_frames()
        self._current_time = new_time

        if new_time >= self._time_event:
            # Dispara um dos eventos de tempo da fila.
            self._owner.anim_event_triggered.emit(self._time_event)
            self._next_time_event()

        # Paramos *após* o último quadro, para permitir o "delay" visual.
        # Caso contrário ele apareceria por um único frame de jogo.
        if new_frame == frames:
            return
        if new_frame > frames:
            self._is_static = True
            self._reset_play()
            if self._owner:
                self._owner.animation_finished.emit()
            return

        self._current_sequence.frame = new_frame
        self.set_base_texture(self._current_sequence.get_texture())

    def play_once(self, name: str, owner=None, time_events: deque[float] = None,
                  from_time: float = 0.0) -> None:
        '''Toca a animação determinada.─ Veja: `set_current_animation`.
        Opcionalmente recebe o `Sprite` associado a este atlas:
         -> Quando a animação for finalizada emite o sinal
            `animation_finished` no `owner` indicado;
         -> O sinal `anim_event_triggered` será emitido no `owner`
            sempre que um dos tempos de `time_events` forem atingidos.
            Note que os tempos devem ser ordenados em
            uma fila para funcionar devidamente.
        Se `from_time` for indicado, começa a animação daquele ponto.
         -> Note que a velocidade determina o tempo de passagem para cada
            frame da animação. Logo o tempo total == `speed * frames`.
        '''  # WATCH -> Usar frames/segundo?
        self._current_time = from_time
        self._current_sequence = self.animations[name]
        self._current_sequence.frame = int(from_time)
        self._owner = owner
        self._play = self._play_once
        self._update_frame()
        self._time_events = time_events
        self._next_time_event()

    def add_animation(self, name: str, texture: Surface, h_slice: int = 1, v_slice: int = 1,
                      coords: tuple[int, int] = VECTOR_ZERO, sprite_size: tuple[int, int] = None,
                      speed: float = TextureSequence.DEFAULT_SPEED) -> None:
        '''Adiciona uma animação ao atlas, com base em uma spritesheet
        (aplicando o fatiamento indicado).'''
        sequence: TextureSequence = TextureSequence(speed)
        sequence.add_spritesheet(
            texture, h_slice, v_slice, coords, sprite_size)
        self.animations[name] = sequence
        self._current_sequence = sequence

        if sequence.get_frames() > 1:
            self._is_static = False

            if not self._is_paused:
                self._play = self._play_sequence

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
        self._is_static = self._current_sequence.get_frames() <= 1
        self._reset_play()
        self._update_frame()

    def set_frame(self, value: int) -> None:

        if value > self._current_sequence.get_frames():
            return

        self._current_sequence.frame = value
        self._current_time = float(value)
        self._update_frame()

    def get_frame(self) -> int:
        return self._current_sequence.frame

    def _next_time_event(self) -> None:
        self._time_event = self._time_events.popleft() if self._time_events else inf

    def __init__(self) -> None:
        super().__init__()
        self.animations = {}
        self._owner: Sprite = None
        self._time_event: float = inf
        self._time_events: deque[float] = deque()


class Sprite(Node):
    '''Nó que configura um sprite do Pygame como um objeto de jogo
    (que pode ser inserido na árvore da cena).'''
    atlas: BaseAtlas
    group: str
    animation_finished: Node.Signal
    anim_event_triggered: Node.Signal

    def _enter_tree(self) -> None:
        global root

        root.sprites_groups[self.group].add(self.atlas)
        super()._enter_tree()

    def _exit_tree(self) -> None:
        global root

        root. sprites_groups[self.group].remove(self.atlas)
        super()._exit_tree()

    def _process(self) -> None:
        self.atlas.update()

    def _draw(self, target_pos: tuple[int, int], target_scale: tuple[float, float],
              offset: tuple[int, int]) -> None:
        global root
        super()._draw(target_pos, target_scale, offset)

        # REFACTOR -> Fazer as transforms serem recalculadas _JIT_ (Just In Time).
        self.atlas.image = pygame.transform.scale(
            self.atlas.image, (self.atlas.base_size * target_scale).astype('int'))
        self.atlas.rect.topleft = array(target_pos) - offset

        # Draw sprite in order
        root.screen.blit(self.atlas.image, Rect(array(
            self.atlas.rect.topleft) + self._layer.offset(), self.atlas.rect.size))

    def get_cell(self) -> ndarray:
        return array(self.atlas.base_size)

    def __init__(self, name: str = 'Sprite', coords: tuple[int, int] = VECTOR_ZERO,
                 atlas: BaseAtlas = None) -> None:
        global root
        super().__init__(name=name, coords=coords)
        self.animation_finished = Node.Signal(self, 'animation_finished')
        self.anim_event_triggered = Node.Signal(self, 'anim_event_triggered')

        # REFACTOR -> Tornar o tipo de atlas mandatório, ou alterar o tipo default para `AtlasBook`.`
        if atlas:
            self.atlas = atlas
        else:
            self.atlas = AtlasPage()

        self.group = root.DEFAULT_GROUP


class Shape(Node):
    '''Nó que representa uma forma usada em cálculos de colisão.
    Deve ser adicionada como filha de um `Body`.'''
    rect_changed: Entity.Signal

    class CollisionType(IntEnum):
        PHYSICS = 1  # Área usada para detecção de colisão entre corpos
        AREA = 2  # Área usada para mapeamento (renderização, ou localização).

    type: int = CollisionType.PHYSICS

    if IS_DEBUG_ENABLED:
        _normal_color: Color = None
        _overlap_color: Color = None

    def _draw(self, target_pos: tuple[int, int], target_scale: tuple[float, float],
              offset: tuple[int, int]) -> None:
        super()._draw(target_pos, target_scale, offset)
        self._rect.size = self._base_size * target_scale
        self._rect.topleft = array(target_pos) - offset

    def get_cell(self) -> ndarray:
        return array(self._base_size)

    def set_rect(self, value: Rect) -> None:
        self.base_size = array(value.size)
        self._rect = value
        self.rect_changed.emit(self)

    def get_rect(self) -> Rect:
        return self._rect

    def set_base_size(self, value: ndarray) -> None:
        self._base_size = value
        self._rect.size = self._base_size * self.scale
        self.rect_changed.emit(self)

    def get_base_size(self) -> ndarray:
        return self._base_size

    def bounds(self) -> Rect:
        '''Retorna a caixa delimitadora da forma.'''
        return self._rect

    @Node.debug()
    def _shift_color(self, *args) -> None:
        self.color = self._overlap_color if args[0] else self._normal_color

    @Node.debug()
    def _setup_overlap(self, parent) -> None:
        '''Método chamado por um nó pai do tipo "corpo físico", para auxiliar
        na visualização de colisões durante os testes em modo de debug.'''
        self._normal_color = self.color
        self._overlap_color = Color(
            255 - self.color.a, 255 - self.color.g, 255 - self.color.b, self.color.a)
        parent.connect(parent.body_entered, self, self._shift_color, True)
        parent.connect(parent.body_exited, self, self._shift_color, False)

    def __init__(self, name: str = 'Shape', coords: tuple[int, int] = VECTOR_ZERO) -> None:
        super().__init__(name=name, coords=coords)
        self.rect_changed = Entity.Signal(self, 'rect_changed')

        self._rect: Rect = Rect(VECTOR_ZERO, VECTOR_ZERO)
        self._base_size = array(VECTOR_ZERO)
        self._debug_fill_bounds = True

    rect: Rect = property(get_rect, set_rect)
    base_size: ndarray = property(get_base_size, set_base_size)


class CircleShape(Shape):

    def _enter_tree(self) -> None:
        super()._enter_tree()
        self._scaled_radius = self._radius * self._global_scale[X]

    def _draw_cell_(self, target_pos: tuple[int, int] = None,
                    target_scale: tuple[float, float] = None,
                    offset: tuple[int, int] = None) -> None:
        global root
        # super()._draw(target_pos, target_scale, offset)
        draw.circle(root.screen, self.color, target_pos +
                    self._layer.offset(), self._radius * target_scale[X], self._debug_line_width)

    def set_scale(self, value: ndarray) -> None:
        super().set_scale(value)
        self._scaled_radius = self._radius * self._global_scale[X]

    def set_radius(self, value: float) -> None:
        self._radius = value
        self._scaled_radius = self._radius * self._global_scale[X]

        offset: ndarray = array((value, value), int)
        self.set_rect(Rect(self.position - offset, offset * 2))

    def __init__(self, name: str = 'CircleShape', coords: tuple[int, int] = VECTOR_ZERO,
                 radius: float = 1.0) -> None:
        super().__init__(name=name, coords=coords)
        self._debug_fill_bounds = True
        # self._debug_length: Union[int, None] = 1 if self._debug_fill_bounds else None
        self._debug_line_width: int = 1
        self._radius: float = radius
        self._scaled_radius: float = radius * self.scale[X]

        self.set_radius(radius)

    radius: float = property(lambda self: self._radius, set_radius)


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


class TileMap(Node):
    _Tile: type[Icon] = Icon
    width: int = 0
    height: int = 0
    grid: list[list[int]]
    tiles: list[_Tile]
    textures: list[Surface]
    _map: Surface = None
    _map_scaled: Surface = None

    def _enter_tree(self) -> None:
        super()._enter_tree()

        if self.tiles:
            self._update_scaled_map()

    def _draw(self, target_pos: tuple[int, int], target_scale: tuple[float, float],
              offset: tuple[int, int]) -> None:
        global root
        super()._draw(target_pos, target_scale, offset)
        root.screen.blit(self._map_scaled, Rect(
            self._layer.offset(), self._map_scaled.get_size()))

    def screen_to_map(self, x: int, y: int) -> tuple[int, int]:
        '''Converte uma posição na tela em um ponto do mapa.'''
        tile_size: ndarray = array(self.tile_size) * self._global_scale

        return array(((x, y) + (
            array(self._global_position) - self._layer.offset())) // tile_size, int)

    def world_to_map(self, x: int, y: int) -> tuple[int, int]:
        '''Converte uma posição global em um ponto do mapa.'''
        tile_size: ndarray = array(self.tile_size) * self._global_scale

        return array((array((x, y)) - self._global_position) // tile_size, int)

    def get_cell(self) -> tuple[int, int]:
        return array(self.get_size()) * self.scale

    def set_tile(self, tile: _Tile, col: int, row: int) -> None:
        last_column: int = len(self.grid) - 1

        if last_column < col:
            # Grow X
            diff: int = col - last_column

            for i in range(diff):
                self.grid.append([])

            self.width = len(self.grid)
            self._map = Surface(array(self.get_size()) *
                                self.get_tile_size(), SRCALPHA)

        row_tiles: list[int] = self.grid[col]
        last_row: int = len(row_tiles) - 1

        if last_row < row:
            diff: int = row - last_row

            for j in range(diff):
                row_tiles.append(None)

            # Grow Y
            new_height: int = len(row_tiles)
            if self.height < new_height:
                self.height = new_height

                self._map = Surface(
                    array(self.get_size()) * self.get_tile_size(), SRCALPHA)

        row_tiles[row] = len(self.tiles)
        self.tiles.append(tile)

        tile.rect.topleft = (
            self._tile_size * self._global_scale).astype('int') * (col, row)

    def get_tile(self, col: int, row: int) -> _Tile:
        tile: Icon

        try:
            id: int = self.grid[col][row]

            if id is None:
                tile = id
            else:
                tile = self.tiles[id]

        except IndexError:
            tile = None

        return tile

    def del_tile(self, col: int, row: int) -> None:

        if len(self.grid) < col:
            return

        row_tiles: list[int] = self.grid[col]
        if len(row_tiles) < row:
            return

        id: int = row_tiles[row]
        if id is None:
            return

        tile: Icon = self.tiles.pop(id)
        row_tiles[row] = None

        if tile:
            tile_coord: tuple[int, int] = self._tile_size * (col, row)

            for x in range(tile_coord[X], tile_coord[X] + self._tile_size[X]):
                for y in range(tile_coord[Y], tile_coord[Y] + self._tile_size[Y]):
                    self._map.set_at((x, y), colors.TRANSPARENT)

        while row_tiles:
            if row_tiles[-1] is None:
                row_tiles.pop()
            else:
                return

        while self.grid:
            if self.grid[-1]:
                return
            else:
                self.grid.pop()

    def set_tile_id(self, col: int, row: int, id: int) -> None:
        try:
            i: int = self.grid[col][row]
            self.tiles[i].set_texture(id)
            tile: Icon = self.tiles[i]

            if self._is_on_tree:
                tile.rect.topleft = self._tile_size * (col, row)

                self._map.blit(tile.image, tile.rect)
                self._update_scaled_map()
        except IndexError:
            self.del_tile(col, row)

    def set_tile_area(
            self, tile: _Tile, from_col: int,  from_row: int, to_col: int, to_row: int) -> None:
        id: int = tile.texture_id

        for i in range(from_col, to_col):
            for j in range(from_row, to_row):
                new_tile: Icon = self._Tile(tile.textures)
                new_tile.set_texture(id)
                self.set_tile(new_tile, i, j)

        self._update_tiles()

    def set_tile_size(self, value: tuple[int, int]) -> None:
        self._tile_size = array(value)

    def get_tile_size(self) -> tuple[int, int]:
        return tuple(self._tile_size)

    def get_size(self) -> tuple[int, int]:
        return self.width, self.height

    def _update_tiles(self) -> None:
        '''Atualiza o mapa em uma única chamada.
        Chamado automaticamente ao entrar na árvore.'''

        for i, column in enumerate(self.grid):
            for j, id in enumerate(column):
                tile: Icon = self.tiles[id]
                tile.rect.topleft = self._tile_size * (i, j)
                tile.rect.size = tuple(self._tile_size)

        for tile in self.tiles:
            tile.image.set_alpha()
            self._map.blit(tile.image, tile.rect)

        self._update_scaled_map()

    def _update_scaled_map(self) -> None:
        new_size: tuple[int, int] = array(
            self._map.get_size()) * self._global_scale
        self._map_scaled = transform.scale(self._map, array(new_size, int))

    def __init__(self, tile_size: tuple[int, int], name: str = 'TileMap',
                 coords: tuple[int, int] = VECTOR_ZERO) -> None:
        super().__init__(name=name, coords=coords)
        self.tiles = []
        self.grid = []
        self.textures = []
        self._tile_size: ndarray = array(tile_size)

    tile_size: tuple[int, int] = property(get_tile_size, set_tile_size)


class Panel(Control):
    '''Base Control Node for GUI panels.'''
    DEFAULT_BORDERS: tuple[int, int, int, int] = 2, 2, 2, 2

    borders: Shape
    bg: Shape

    def set_size(self, value: ndarray) -> None:
        super().set_size(value)
        value = array(value)
        self.borders.base_size = value

        self._inner_size = value - \
            (array((self._borders[X], self._borders[Y])
                   ) + (self._borders[W], self._borders[H]))
        self.bg.base_size = self._inner_size

    def get_size(self) -> ndarray:
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
        topleft: ndarray = array((borders[X], borders[Y]))
        base_size: ndarray = size - (topleft + (borders[W], borders[H]))
        self._inner_size: ndarray = base_size
        # offset: ndarray = array(self.get_cell()) * - self.anchor

        # Set the border square
        bar: Shape = Shape(name='Borders')
        bar.color = borders_color
        bar.anchor = array(TOP_LEFT)
        bar.rect = Rect(VECTOR_ZERO, size)
        bar.can_draw_cell = True
        self.borders = bar
        self.add_child(bar)

        # Set the BackGround
        bar: Shape = Shape(name='BG', coords=topleft)
        bar.anchor = array(TOP_LEFT)
        bar.color = bg_color
        bar.rect = Rect(topleft, base_size)
        bar.can_draw_cell = True
        self.bg = bar
        self.add_child(bar)

        self.set_anchor(anchor)

    size: ndarray = property(get_size, set_size)


class ProgressBar(Panel):
    bar: Shape

    def _update_progress(self, value: float) -> None:
        '''Atualiza o tamanho da barra de progresso de forma ascendente.'''
        self.bar.base_size[self._grow_coord] = self._inner_size[self._grow_coord] * value

    def _update_progress_flip(self, value: float) -> None:
        '''Atualiza o tamanho da barra de progresso de forma descendente.'''
        base_size: int = self._inner_size[self._grow_coord]
        length: int = base_size * value

        self.bar.position[self._grow_coord] = base_size - length
        self.bar.base_size[self._grow_coord] = self._inner_size[self._grow_coord] * value

    def _filter_progress(self, value: float) -> float:
        return clamp(0.0, value, 1.0)

    def set_progress(self, value: float) -> None:
        self._progress = value
        self._progress_update(self._progress_filter(value))

    def get_progress(self) -> float:
        return self._progress

    def __init__(self, name: str = 'ProgressBar', coords: tuple[int, int] = VECTOR_ZERO,
                 bg_color: Color = colors.BLUE, bar_color: Color = colors.GREEN,
                 borders_color: Color = colors.RED, size: tuple[int, int] = (125, 25),
                 borders: tuple[int, int, int, int] = Panel.DEFAULT_BORDERS,
                 v_grow: bool = False, flip: bool = False, allow_overflow: bool = False,
                 progress: int = .5) -> None:
        super().__init__(name=name, coords=coords, bg_color=bg_color,
                         borders_color=borders_color, size=size, borders=borders)
        self.color = bg_color
        self.size = size

        self._progress: float = progress
        self._grow_coord: int = int(v_grow)

        self._progress_filter: Callable[[float], float] = \
            (lambda f: f) if allow_overflow else self._filter_progress
        self._progress_update: Callable[[float], None] = \
            self._update_progress if (
                flip ^ (not v_grow)) else self._update_progress_flip

        # Set the Inner Bar
        topleft: tuple[int, int] = borders[X], borders[Y]
        bar: Shape = Shape(name='Bar', coords=topleft)
        bar.anchor = array(TOP_LEFT)
        bar.color = bar_color
        bar.rect = Rect(topleft, self._inner_size)
        bar.can_draw_cell = True
        self.bar = bar
        self.add_child(bar)

        # Updates the progress
        self.set_progress(self._progress)

    progress: float = property(get_progress, set_progress)


class Body(Node, ABC):
    '''Nó com capacidades físicas (permite colisão: interação entre objetos
    de acordo com propriedades físicas, tais como, posição e tamanho).'''
    body_entered: Node.Signal
    body_exited: Node.Signal

    # TODO -> Atualizar os valores no `PhysicsServer` conforme forem alterados.
    collision_layer: int = 1
    # Uma camada de colisão permite que o objeto receba colisão apenas de objetos
    # cujo máscara tenha um bit compatível a si (veja: 'operações bitwise').
    collision_mask: int = 1
    # Uma máscara de colisão determina quais camadas o objeto pode colidir.

    def add_child(self, node: Node, at: int = -1) -> None:
        super().add_child(node, at=at)

        if isinstance(node, Shape) and node.type & Shape.CollisionType.PHYSICS:
            node.color = node.color.lerp(self.color, .5)
            node._setup_overlap(self)
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

        if self.has_shape():
            root.physics_server.insert_body(self, self._BodyType)
        else:
            push_warning("A `Shape` node must be added as a child to process collisions.",
                         category=Warning)

    def _process(self) -> None:
        global root
        self._physics_process(root.factor_fps)

        for body in self._last_colliding_bodies:
            if body in self._colliding_bodies:
                continue
            self.body_exited.emit(body)

        # Limpa os últimos corpos colisores e armazena os atuais.
        self._last_colliding_bodies.clear()
        tmp: list[Body] = self._last_colliding_bodies
        self._last_colliding_bodies = self._colliding_bodies
        self._colliding_bodies = tmp

    def _physics_process(self, factor: float) -> None:
        '''Método virtual chamado no passo de processamento físico do nó físico.'''

    def _on_Shape_rect_changed(self, _shape: Shape) -> None:

        if _shape.bounds():
            self._active_shapes.append(_shape)
            self._was_shapes_changed = True

    def _collide(self, body) -> None:
        '''Método auxiliar chamado ao decorrer duma colisão.'''
        self._colliding_bodies.append(body)

        if body in self._last_colliding_bodies:
            return

        self.body_entered.emit(body)

    def has_shape(self) -> bool:
        return bool(self._active_shapes)

    @staticmethod
    def check_CC_collision(a: CircleShape, b: CircleShape) -> bool:
        '''Colisão entre círculos'''
        a_radius: float = a._scaled_radius
        b_radius: float = b._scaled_radius
        dx: float = (a._global_position[X] + a_radius) - \
            (b._global_position[X] + b_radius)
        dy: float = (a._global_position[Y] + a_radius) - \
            (b._global_position[Y] + b_radius)
        distance: float = sqrt(dx * dx + dy * dy)

        return distance < a_radius + b_radius

    @staticmethod
    def check_CR_collision(circle: CircleShape, shape: Shape) -> bool:
        '''Colisão entre círculo-retângulo'''
        rect: Rect = shape.rect
        radius: float = circle._scaled_radius
        dx: int = abs(circle._global_position[X] - shape._global_position[X])
        dy: int = abs(circle._global_position[Y] - shape._global_position[Y])

        if dx > rect.width / 2 + radius:
            return False

        if dy > rect.height / 2 + radius:
            return False

        if dx <= rect.width / 2:
            return True

        if dy <= rect.height / 2:
            return True

        corner_distance_squared: float = (
            dx - rect.width / 2) ** 2 + (dy - rect.height / 2) ** 2
        return corner_distance_squared <= radius ** 2

    # @Benchmarked: tabela de dispersão mais rápida que indexação.
    COLLISION_TABLE: list[Callable[[Shape, Shape], bool]] = {
        (True, True): check_CC_collision,
        (True, False): check_CR_collision,
        (False, False): lambda shape_a, shape_b: shape_a.rect.colliderect(shape_b.rect),
        (False, True): lambda rect, circle: Body.check_CR_collision(circle, rect),
    }

    def is_colliding(self, target) -> bool:
        ''''Verifica colisões com o corpo indicado.'''

        for a in self._active_shapes:
            for b in target._active_shapes:

                if Body.COLLISION_TABLE[
                        isinstance(a, CircleShape),
                        isinstance(b, CircleShape)](a, b):
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

    def __init__(self, name: str = 'Body', coords: tuple[int, int] = VECTOR_ZERO,
                 color: Color = Color(46, 10, 115)) -> None:
        super().__init__(name, coords=coords)
        self.color = color
        self.body_entered = Node.Signal(self, 'body_entered')
        self.body_exited = Node.Signal(self, 'body_exited')

        self._was_shapes_changed: bool = False
        self._bounds: Rect = None
        self._cached_bounds: Rect = None
        self._active_shapes: list[Shape] = []
        self._layers_ids: dict[int, int] = {}
        self._colliding_bodies: list[Body] = []
        self._last_colliding_bodies: list[Body] = []
        self._BodyType: type[Body] = Body


class Area(Body):
    '''Colisor genérico para detectar contato (não aplica física).'''

    def __init__(self, name: str = 'Area', coords: tuple[int, int] = VECTOR_ZERO,
                 color: Color = Color(11, 145, 145)) -> None:
        super().__init__(name=name, coords=coords, color=color)
        self._BodyType = Area


class StaticBody(Body):
    '''Colisor estático usado primariamente para receber contato. Diferente de
    um corpo cinemático. Não é atualizado automaticamente conforme se move.'''

    def __init__(self, name: str = 'StaticBody', coords: tuple[int, int] = VECTOR_ZERO,
                 color: Color = Color(79, 10, 125)) -> None:
        super().__init__(name=name, coords=coords, color=color)
        self._BodyType = StaticBody
        # Por padrão, corpos estáticos não recebem colisão.
        self.collision_layer = 0
        # Veja o algoritmo de verificação de colisões na classe `PhysicsServer`.


class KinematicBody(Body):
    '''Colisor dinâmico usado para aplicação de física
    (atualiza a colisão conforme se movimenta).'''
    _was_collided: bool = False
    _last_motion: tuple[float, float]
    _cache_motion: Vector2

    def _physics_process(self, factor: float) -> None:
        # Move
        motion: Vector2 = self._cache_motion * factor  # \
        # * (1 - int(self._was_collided) * 2)  # Velocity * Direction
        # (Inverte a direção se colidir)
        self.position += array(motion, int)
        # self._was_collided = False
        self._last_motion = tuple(motion)
        self._cache_motion -= motion

    def move_and_collide(self, velocity: Vector2) -> None:
        self._cache_motion += velocity

    def __init__(self, name: str = 'KinematicBody', coords: tuple[int, int] = VECTOR_ZERO,
                 color: Color = Color(160, 25, 125)) -> None:
        super().__init__(name=name, coords=coords, color=color)
        self._BodyType = KinematicBody
        self._last_motion = VECTOR_ZERO
        self._cache_motion = Vector2(self._last_motion)

        # TODO -> Physics collision
        # self.connect(self.body_entered, self, self)


class Popup(Panel):
    ESCAPE_EVENT: str = 'esc'

    popup_finished: Node.Signal
    hided: Node.Signal

    pop_duration: float
    _on_focus: bool = False
    _on_pause_game: bool = False
    # TODO -> Tornar o focus algo global dos nós do tipo control

    def _input_event(self, event: InputEvent) -> None:
        if event.tag is Popup.ESCAPE_EVENT:
            self.hide(self._do_ease)

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

    # WATCH -> Default focus to True
    def popup(self, do_ease: bool = None, do_focus: bool = False, do_pause: bool = False) -> None:
        self._on_focus = do_focus
        self._on_pause_game = do_pause

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

        if self._on_focus:
            input.register_event(
                self, KEYDOWN, K_ESCAPE, Popup.ESCAPE_EVENT)

        if self._on_pause_game:
            self.pause_mode = SceneTree.PauseModes.IGNORE
            root.pause(True)
        else:
            self.pause_mode = SceneTree.PauseModes.STOP

    def _on_Hide(self) -> None:
        self.hided.emit()

        if self._on_focus:
            input.remove_event(
                self, KEYDOWN, K_ESCAPE, Popup.ESCAPE_EVENT)

        if self._on_pause_game:
            root.pause(False)

    def set_on_focus(self, value: bool) -> None:
        self._on_focus = value

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

    def get_text(self) -> str:
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

    text: str = property(get_text, set_text)


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

    def _process(self) -> None:
        self._mouse_input()

    def _input_event(self, event: InputEvent) -> None:

        def hold() -> None:
            global root
            nonlocal self

            if self._rect.collidepoint(mouse.get_pos()):
                self._hold()

        def release() -> None:
            global root
            nonlocal self

            if self.is_pressed and self._rect.collidepoint(mouse.get_pos()):
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
        area: ndarray = array(self.get_cell()) * self.scale
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

    is_on_focus: bool = property(get_is_on_focus, set_is_on_focus)


class Link(BaseButton):
    normal_color: Color = colors.BLUE
    pressed_color: Color = colors.GREEN
    highlight_color: Color = colors.CYAN
    focus_color: Color = colors.PURPLE

    def _on_hold(self) -> None:
        self.set_color(self.pressed_color)

    def _focused_mouse_input(self) -> None:

        if self._rect.collidepoint(mouse.get_pos()):
            self.set_color(self.highlight_color.lerp(self.focus_color, .5))
        else:
            self.set_color(self.focus_color)

    def _unfocused_mouse_input(self) -> None:
        self._update_rect()

        if self._rect.collidepoint(mouse.get_pos()):
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

    def get_action(self) -> str:
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

    action: str = property(get_action, set_action)


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

        if self._rect.collidepoint(mouse.get_pos()):
            self._icon.set_texture(self.highlight_icon_id)
        else:
            self._icon.set_texture(self.focus_icon_id)

    def _unfocused_mouse_input(self) -> None:

        if self._rect.collidepoint(mouse.get_pos()):
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

        # Limpa o conteúdo atual
        children: list[Node] = self._children_index.copy()
        for child in children:
            child.free()

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

            span: tuple[int, int] = match.span()
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

        if self._rect.collidepoint(mouse.get_pos()):
            self.panel.bg.color = self.highlight_color
        else:
            self.panel.bg.color = self.normal_color

    def _focused_mouse_input(self) -> None:
        if self._rect.collidepoint(mouse.get_pos()):
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
        self._update_rect()

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
                 name: str = 'PopUpDialog', coords: tuple[int, int] = VECTOR_ZERO,
                 anchor: tuple[int, int] = TOP_LEFT, do_ease: bool = True,
                 pop_duration: float = 0.3, bg_color: Color = colors.DEFAULT_POPUP,
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
        label.color = colors.WHITE
        self.add_child(label)


class PhysicsServer():
    '''Singleton responsável pelo registro de corpos físicos
    (colisores) e tratamento das colisões entre eles.'''
    _instance = None

    '''Um objeto físico serve de contêiner para outros objetos físicos.
    No caso do nó do tipo `Body`, este contém listas ordenadas (de acordo
    com o tipo e critério de cada lista) de todos os primeiros nós
    descendentes que são do tipo `Body`.'''

    class PhysicsSpace(Generic[T]):
        def __init__(self) -> None:
            self.masks: list[T] = []  # Espaço que gera colisões.
            self.layers: list[T] = []  # Espaço que recebe colisões.

    def _on_Body_freed(self, _type: type[Body], body: Body) -> None:
        '''Remove um nó dos registros do espaço físico.'''
        # WATCH -> Adicionar uma fila de remoção para prevenir bugs?
        _PS: type = PhysicsServer.PhysicsSpace
        layers: list[int] = PhysicsServer.get_bitflags(body.collision_layer)
        masks: list[int] = PhysicsServer.get_bitflags(body.collision_mask)
        space: list[_PS[Body]] = self.MATCH[_type]
        body.disconnect(body.freed, self)

        # Remove o corpo das camadas selecionadas.
        for layer in layers:
            space[int(log2(layer))].layers.remove(body)

        # Remove o corpo das máscaras selecionadas.
        for mask in masks:
            space[int(log2(mask))].masks.remove(body)

    def process_collisions(self) -> None:

        for space in self.areas:
            # Colisão entre áreas
            PhysicsServer._check_collisions(space.masks, space.layers)

        min_len: int = min(len(self.kinematic_bodies), len(self.static_bodies))
        for i, space in enumerate(self.kinematic_bodies[:min_len]):
            # Colisão entre corpos dinâmicos
            PhysicsServer._check_collisions(space.masks, space.layers)
            # Colisão com corpo estático
            PhysicsServer._check_collisions(
                self.static_bodies[i].masks, space.layers)
            # PhysicsServer._check_collisions(space.masks, self.static_bodies[i].layers)
            # WATCH -> Permite que o corpo estático receba colisões.

        # Colisões restantes
        for space in self.kinematic_bodies[min_len:]:
            PhysicsServer._check_collisions(space.masks, space.layers)

    def insert_body(self, body: Body, _type: type[Body]) -> None:
        '''Insere um nó ordenadamente nos registros do espaço físico.'''
        # bounds: Rect = body.bounds()
        _PS: type = PhysicsServer.PhysicsSpace
        layers: list[int] = PhysicsServer.get_bitflags(body.collision_layer)
        masks: list[int] = PhysicsServer.get_bitflags(body.collision_mask)
        space: list[_PS[Body]] = self.MATCH[_type]
        body.connect(body.freed, self, self._on_Body_freed, _type)

        if layers:
            space_max: int = len(space) - 1
            _higher_layer: int = int(log2(layers[-1]))
            # Se a camada maior ao qual o corpo será adicionado for um valor
            # maior do que o espaço existente, mais espaço é adicionado.
            if _higher_layer > space_max:
                new_layers: int = _higher_layer - space_max

                for _ in range(new_layers):
                    space.append(_PS())

            # Insere o corpo às camadas selecionadas.
            for layer in layers:
                space[int(log2(layer))].layers.append(body)

        if masks:
            space_max: int = len(space) - 1
            _higher_mask: int = int(log2(masks[-1]))

            if _higher_mask > space_max:
                new_masks: int = _higher_mask - space_max

                for _ in range(new_masks):
                    space.append(_PS())

            # Insere o corpo às máscaras selecionadas.
            for mask in masks:
                space[int(log2(mask))].masks.append(body)

    @staticmethod
    def _check_collisions(masks: list[Body], layers: list[Body]):
        _bounds: type = list[tuple[Body, Rect]]
        mask_bounds: _bounds = []
        layer_bounds: _bounds = []

        for mask in masks:
            mask_bounds.append((mask, mask.bounds()))
        for layer in layers:
            layer_bounds.append((layer, layer.bounds()))

        # Verifica as combinações de elementos.
        for mask, m_bounds in mask_bounds:
            for layer, l_bounds in layer_bounds:
                if m_bounds.colliderect(l_bounds) and mask.is_colliding(layer):
                    layer._collide(mask)

    @staticmethod
    def get_bitflags(from_value: int) -> list[int]:
        tmp: int = from_value
        counter: int = 1
        layers: list[int] = []

        while tmp > 0:
            layer: int = from_value & counter
            counter *= 2

            if layer != 0:
                layers.append(layer)
                tmp -= layer

        return layers

    def __new__(cls):
        # Torna a classe em uma Singleton
        if cls._instance is None:
            # Criação do objeto
            cls._instance = super(PhysicsServer, cls).__new__(cls)

        return cls._instance

    def __init__(self) -> None:
        _PS: type[PhysicsServer.PhysicsSpace] = PhysicsServer.PhysicsSpace
        self.areas: list[_PS[Area]] = [
            # _PS(), # Camada 1 (ímpar)
            # _PS(), # Camada 2 (par)
            # _PS(), # Camada 4 (2²)
            # _PS(), # Camada 8 (2³)
            # _PS(), # Camada 16 (2^4)
            # _PS(), # Camada 32 (2^5)
            # _PS(), # Camada 64 (2^6)
            # _PS(), # Camada 128 (2^7)
            # ...
        ]
        self.static_bodies: list[_PS[StaticBody]] = []
        self.kinematic_bodies: list[_PS[KinematicBody]] = []
        self.MATCH: dict[type[Body], _PS] = {
            Area: self.areas,
            StaticBody: self.static_bodies,
            KinematicBody: self.kinematic_bodies,
        }


# root
class SceneTree(CanvasLayer):
    '''Nó singleton usado como a rais da árvore da cena.
    Definido dessa forma para facilitar acessos globais.'''
    pause_toggled: Node.Signal
    locale_changed: Node.Signal

    # Motor de física.
    physics_server: PhysicsServer = PhysicsServer()

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
    factor_fps: float = 0.0  # O Fator entre o fps atual e o fps fixo
    delta: float = 0.0  # O tempo decorrido desde o último frame

    # Tweening
    _active_tweens: list[Tween] = []
    # Timings
    _active_timers: list[Timer] = []

    _instance = None
    tree_pause: int = 0
    groups: dict[str, list[Node]] = {}
    gui_font: font.Font = None

    _locale: str = 'en'
    _locales: dict[str, ]
    _current_scene: Node = None
    _last_time: float = 0.0

    FOCUS_ACTION_DOWN: str = 'focus_action_down'
    FOCUS_ACTION_UP: str = 'focus_action_up'
    _current_focus: BaseButton = None
    
    # Caminhos para os diretórios de usuário
    user_dir: str # Diretório de save-data
    shared_dir: str # Diretório de dados compartilhados
    tmp_dir: str # Diretório de arquivos temporários

    class AlreadyInGroup(Exception):
        '''Chamado ao tentar adicionar o nó a um grupo ao qual já pertence.'''
        pass

    def start(self, title: str = 'GamePy', screen_size: tuple[int, int] = None,
              gui_font: font.Font = None, window_title: str = None) -> None:
        '''Setups the basic settings.'''
        self.clock = pygame.time.Clock()

        if window_title is None:
            window_title = title
        if screen_size is not None:
            self.screen_size = screen_size

        self.gui_font = font.SysFont('roboto', 20, False, False)\
            if gui_font is None else gui_font

        self._setup_log()
        self.screen = pygame.display.set_mode(self.screen_size)
        #alpha_layer = Surface(SCREEN_SIZE, pygame.SRCALPHA)
        pygame.display.set_caption(window_title)
        
        # Filtra mantendo apenas caracteres alfanuméricos da string passada como title
        # Substitui espaços do título por _ (underscore)
        dir_name: str = re.sub(r'[^a-zA-Z0-9_]*', '', title.replace(' ', '_'))

        if not dir_name:
            dir_name = 'GamePy'

        self.user_dir = path.join(USER_DIR, dir_name)
        self.shared_dir = path.join(SHARED_DIR, dir_name)
        self.tmp_dir = path.join(TMP_DIR, dir_name)

    def run(self) -> None:
        '''Game's Main Loop.'''

        if self.current_scene is None:
            push_warning('The Game needs an active scene to be able to run.')
            return

        while True:
            # tick = self.clock.tick(self.fixed_fps)
            self.clock.tick(self.fixed_fps)
            factor_fps: float = self.clock.get_fps() / self.fixed_fps
            self.factor_fps = factor_fps
            delta = factor_fps / 60.0
            self.delta = delta

            self.screen.fill(self.screen_color)
            # Preenche a tela

            # Propaga as entradas
            if input._tick():
                self._input()

            # Processa os timers ativos na lista
            for timer in self._active_timers:
                timer._process(delta)

            # Processa os tweens ativos na lista
            for tween in self._active_tweens:
                tween._process(delta)

            self._propagate()
            # Propaga o processamento

            self._draw_tree()
            # Desenha a árvore.
            # `Sprite`s e `Label`s aplicam blit individualmente no método `_draw`

            pygame.display.update()
            # Verifica as colisões antes da próxima iteração.
            self.physics_server.process_collisions()

    def pause_tree(self, pause_mode: int = Node.PauseModes.TREE_PAUSED) -> None:
        self.tree_pause = pause_mode
        self.pause_toggled.emit(
            bool((pause_mode ^ self.pause_mode) & Node.PauseModes.TREE_PAUSED))

    def add_to_group(self, node: Node, group: str) -> None:
        '''Adiciona o nó a um grupo determinado.
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

    def _on_Timer_timeout(self, timer: Timer) -> None:
        timer.timeout.disconnect_all(timer)
        self._active_timers.remove(timer)

    def create_timer(self, time: float, node: Node, callback: Callable, *args) -> None:
        timer: Timer = Timer(time)
        self._active_timers.append(timer)
        timer.timeout.connect(timer, self, self._on_Timer_timeout)
        timer.timeout.connect(timer, node, callback, *args)

    @Node.debug()
    def log(self, message: str) -> None:
        self._log.text = message

    @Node.debug()
    def _setup_log(self) -> None:
        self._log: Label = Label(
            self.gui_font, 'Log', color=Color('#ffffff'))
        self.add_child(self._log)

    def get_delta_time(self) -> float:
        '''Calculates and returns the current delta time-step.'''
        return self.clock.get_fps() / self.fixed_fps

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
            self._current_scene.free()

        self._current_scene = scene
        self.add_child(scene, 0)

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
        self._layer = self

        # Events
        self.pause_toggled = Node.Signal(self, 'pause_toggled')
        self.locale_changed = Node.Signal(self, 'locale_changed')

        for key in (K_RETURN, K_SPACE, K_KP_ENTER):
            input.register_event(self, KEYDOWN, key, SceneTree.FOCUS_ACTION_UP)
            input.register_event(self, KEYUP, key, SceneTree.FOCUS_ACTION_DOWN)

    # WATCH
    @Node.debug()
    def _get_tree(self) -> dict[str, Union[Node, list[Node]]]:

        def get_child(node: Node) -> Node:
            return node._children_index[0] if node._children_index else None

        # pointers
        tree: dict[str, Union[Node, list[dict]]] = {
            'root': self,
            'children': []
        }
        next: dict[str, Union[dict, list[Node]]]
        child = get_child(self)

        if child:
            next = {
                'root': child,
                'children': [],
            }
            tree['children'].append(next)
        else:
            return tree

        parent: dict[str, Union[dict, list[Node]]] = tree
        # stacks
        previous_parent: list[dict] = [parent]
        previous_siblings: list[list[Node]] = []

        while next:
            root: Node = next['root']
            child = get_child(root)
            cache: dict = next
            next = None

            if child:
                next = {
                    'root': child,
                    'children': [],
                }
                cache['children'].append(next)
                parent = cache
                previous_parent.append(parent)
                previous_siblings.append(root._children_index[1:])

            else:
                while previous_siblings:
                    siblings: list[Node] = previous_siblings.pop()

                    if siblings:
                        sibling: Node = siblings.pop()
                        next = {
                            'root': sibling,
                            'children': [get_child(sibling)],
                        }
                        cache = {
                            'root': sibling,
                            'children': [next],
                        }
                        parent['children'].append(cache)
                        previous_siblings.append(siblings)
                        break

                    parent = previous_parent.pop()

        return tree

    screen_size: tuple[int, int] = property(get_screen_size, set_screen_size)
    current_scene: Node = property(get_current_scene, set_current_scene)


# Singletons
input: Input = Input()  # Singleton usado na captura de inputs
# Nó Singleton que constitui a raiz da árvore da cena.
root: SceneTree = SceneTree()
