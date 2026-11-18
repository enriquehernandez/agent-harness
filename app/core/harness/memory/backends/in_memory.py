from collections import deque
from app.core.harness.memory.base import MemoryStore, MemoryEntry


class InMemoryRingStore(MemoryStore):
    def __init__(self, capacity: int = 50):
        self.capacity = capacity
        self.entries: deque[MemoryEntry] = deque(maxlen=capacity)

    async def save(self, entry: MemoryEntry) -> None:
        self.entries.append(entry)

    async def recall(self, query: str, limit: int = 5) -> list[MemoryEntry]:
        results = [
            e for e in self.entries
            if query.lower() in e.key.lower() or query.lower() in e.value.lower()
        ]
        return results[-limit:]

    def preamble(self, limit: int = 5) -> str:
        latest = list(self.entries)[-limit:]
        if not latest:
            return ""
        lines = ["# Short-Term Memory (In-Memory)\n"]
        for e in latest:
            lines.append(f"- **{e.key}**: {e.value}")
        return "\n".join(lines)

    async def clear(self) -> None:
        self.entries.clear()

    async def get_all(self) -> list[MemoryEntry]:
        """Devuelve todas las entradas de memoria."""
        return list(self.entries)
