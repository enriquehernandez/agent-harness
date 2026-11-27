"""Aislamiento temporal de las rutas de datos para los scripts de diagnóstico.

Todas las rutas de memoria, caché de pricing, sesiones y logs derivan de
``settings.DATA_DIR``. Los scripts de diagnóstico redirigen esa ruta a un
directorio temporal para que sus pruebas nunca escriban ni borren datos reales.
"""

from contextlib import contextmanager
from pathlib import Path
import tempfile

from app.core.config import settings


@contextmanager
def isolated_data_dir(data_dir: Path | None = None):
    """Redirige ``DATA_DIR`` y lo restaura siempre, incluso si hay excepción.

    Si no se pasa ``data_dir``, se crea un directorio temporal que se elimina
    al salir. Si se pasa, se usa ese directorio (útil para sembrar datos en los
    tests) sin borrarlo.
    """
    original = settings.DATA_DIR
    temp = None
    if data_dir is None:
        temp = tempfile.TemporaryDirectory()
        data_dir = Path(temp.name)
    settings.DATA_DIR = data_dir
    try:
        yield data_dir
    finally:
        settings.DATA_DIR = original
        if temp is not None:
            temp.cleanup()
