from app.core.harness.memory.base import MemoryStore, MemoryEntry


class FanoutStore(MemoryStore):
    """Escribe en dos backends a la vez. Útil para redundancia."""

    def __init__(self, primary: MemoryStore, secondary: MemoryStore):
        self.primary = primary
        self.secondary = secondary

    async def save(self, entry: MemoryEntry) -> None:
        await self.primary.save(entry)
        await self.secondary.save(entry)

    async def recall(self, query: str, limit: int = 5) -> list[MemoryEntry]:
        # Devuelve los resultados del primario (o combina ambos)
        return await self.primary.recall(query, limit)

    def preamble(self, limit: int = 5) -> str:
        return self.primary.preamble(limit)

    async def clear(self) -> None:
        await self.primary.clear()
        await self.secondary.clear()

    async def get_all(self) -> list[MemoryEntry]:
        return await self.primary.get_all()
