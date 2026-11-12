from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass
class MemoryEntry:
    key: str
    value: str
    timestamp: datetime
    kind: str = "fact"  # "fact", "session_summary", "preference"


class MemoryStore(ABC):
    """Interfaz abstracta para el almacenamiento de memoria."""

    @abstractmethod
    async def save(self, entry: MemoryEntry) -> None:
        """Guarda una entrada en la memoria."""
        ...

    @abstractmethod
    async def recall(self, query: str, limit: int = 5) -> list[MemoryEntry]:
        """Busca entradas que coincidan con la query."""
        ...

    @abstractmethod
    def preamble(self, limit: int = 5) -> str:
        """Devuelve el preámbulo para inyectar en el system prompt."""
        ...

    @abstractmethod
    async def clear(self) -> None:
        """Limpia toda la memoria."""
        ...

    # 🔥 Obtener todas las entradas (para migración)
    @abstractmethod
    async def get_all(self) -> list[MemoryEntry]: ...
