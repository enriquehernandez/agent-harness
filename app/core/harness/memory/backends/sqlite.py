import sqlite3
from datetime import datetime
from app.core.config import settings
from app.core.harness.memory.base import MemoryStore, MemoryEntry


class SQLiteStore(MemoryStore):
    def __init__(self, db_path: str | None = None):
        if db_path is None:
            db_path = str(settings.memory_db)  # 🔥 Usa la ruta centralizada
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._init_db()

    def _init_db(self):
        self.conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS memories 
            USING fts5(key, value, kind, timestamp)
        """)
        self.conn.commit()

    async def save(self, entry: MemoryEntry) -> None:
        self.conn.execute(
            "INSERT INTO memories (key, value, kind, timestamp) VALUES (?, ?, ?, ?)",
            (entry.key, entry.value, entry.kind, entry.timestamp.isoformat())
        )
        self.conn.commit()

    async def recall(self, query: str, limit: int = 5) -> list[MemoryEntry]:
        cursor = self.conn.execute(
            "SELECT key, value, kind, timestamp FROM memories WHERE memories MATCH ? LIMIT ?",
            (query, limit)
        )
        return [
            MemoryEntry(key=k, value=v, kind=kd,
                        timestamp=datetime.fromisoformat(ts))
            for k, v, kd, ts in cursor.fetchall()
        ]

    def preamble(self, limit: int = 5) -> str:
        cursor = self.conn.execute(
            "SELECT key, value FROM memories ORDER BY rowid DESC LIMIT ?", (
                limit,)
        )
        results = cursor.fetchall()
        if not results:
            return ""
        lines = ["# Long-Term Memory Summary (SQLite)\n"]
        for k, v in results:
            lines.append(f"- **{k}**: {v}")
        return "\n".join(lines)

    async def clear(self) -> None:
        self.conn.execute("DELETE FROM memories")
        self.conn.commit()

    async def get_all(self) -> list[MemoryEntry]:
        """Devuelve todas las entradas de memoria."""
        cursor = self.conn.execute(
            "SELECT key, value, kind, timestamp FROM memories ORDER BY rowid"
        )
        return [
            MemoryEntry(key=k, value=v, kind=kd,
                        timestamp=datetime.fromisoformat(ts))
            for k, v, kd, ts in cursor.fetchall()
        ]
