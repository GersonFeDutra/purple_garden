from os import getenv, path
from sys import platform

# Carrega variáveis de ambiente mantendo a compatibilidade com as diferentes plataformas
# (apenas Linux e Windows)
USER_DIR: str # Player's game data
SHARED_DIR: str # Shared game data
TMP_DIR: str # Temporary game data

# Nota: não acessar a raiz desses caminhos diretamente, usar um subdiretório relacionado ao seu game.
# A SceneTree disponibiliza métodos correspondentes para tal.
# More info at <https://gamedev.stackexchange.com/a/35701> (Windows) <https://gamedev.stackexchange.com/a/35703> (Linux)
if platform.startswith('linux'):
    USER_DIR = getenv('XDG_DATA_HOME')
    if USER_DIR is None: USER_DIR = path.expanduser('~/.local/share')
    SHARED_DIR = '/var/games'
    TMP_DIR = '/tmp'
elif platform.startswith('win32'):
    USER_DIR = getenv('APPDATA')
    SHARED_DIR = getenv('PROGRAMDATA')
    TMP_DIR = getenv('TEMP')
