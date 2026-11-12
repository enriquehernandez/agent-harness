from app.core.harness.memory.backends.fanout import FanoutStore
from app.core.harness.memory.base import MemoryStore
from app.core.harness.memory.backends.session_files import SessionFilesStore
from app.core.harness.memory.backends.sqlite import SQLiteStore
from app.core.harness.memory.backends.in_memory import InMemoryRingStore


def create_memory_store(backend: str = "sqlite") -> MemoryStore:
    if backend == "sqlite":
        return SQLiteStore()
    elif backend == "files":
        return SessionFilesStore()
    elif backend == "memory":
        return InMemoryRingStore()
    elif backend == "fanout":
        # Ejemplo: escribe en archivos Y en SQLite a la vez
        return FanoutStore(
            primary=SessionFilesStore(),
            secondary=SQLiteStore()
        )
    else:
        raise ValueError(f"Backend desconocido: {backend}")
