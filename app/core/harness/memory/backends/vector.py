import sqlite3
import sqlite_vec
from datetime import datetime
from pathlib import Path
from fastembed import TextEmbedding
from app.core.harness.memory.base import MemoryStore, MemoryEntry
from app.core.config import settings
from app.core.logger import logger


class VectorStore(MemoryStore):
    """Backend de memoria con búsqueda semántica usando sqlite-vec + fastembed."""

    _model = None  # Singleton para no recargar el modelo

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or settings.vector_db
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Cargamos el modelo de embeddings (ONNX)
        if VectorStore._model is None:
            logger.info(
                "Cargando modelo de embeddings (fastembed BAAI/bge-small-en-v1.5)...")
            VectorStore._model = TextEmbedding(
                model_name="BAAI/bge-small-en-v1.5")
        self.model = VectorStore._model

        # Conexión a SQLite y carga de sqlite-vec
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.enable_load_extension(True)
        sqlite_vec.load(self.conn)
        self.conn.enable_load_extension(False)

        self._init_db()

    def _init_db(self):
        with self.conn:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT UNIQUE,
                    value TEXT,
                    kind TEXT,
                    timestamp TEXT
                )
            """)
            self.conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS vec_memories USING vec0(
                    memory_id INTEGER PRIMARY KEY,
                    embedding FLOAT[384]
                )
            """)

    def _embed(self, text: str) -> list[float]:
        """fastembed devuelve un generador, lo convertimos a lista."""
        return list(self.model.embed([text]))[0].tolist()

    async def save(self, entry: MemoryEntry) -> None:
        embedding = self._embed(entry.value)

        with self.conn:
            # 1. Insertamos/actualizamos el recuerdo y obtenemos su ID
            cursor = self.conn.execute("""
                INSERT INTO memories (key, value, kind, timestamp)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value=excluded.value,
                    kind=excluded.kind,
                    timestamp=excluded.timestamp
                RETURNING id
            """, (entry.key, entry.value, entry.kind, entry.timestamp.isoformat()))

            memory_id = cursor.fetchone()[0]

            # 2. Borramos el vector viejo (si existía) para evitar la UNIQUE constraint
            self.conn.execute(
                "DELETE FROM vec_memories WHERE memory_id = ?", (memory_id,)
            )

            # 3. Insertamos el nuevo vector
            self.conn.execute("""
                INSERT INTO vec_memories (memory_id, embedding)
                VALUES (?, ?)
            """, (memory_id, sqlite_vec.serialize_float32(embedding)))

    async def recall(self, query: str, limit: int = 5) -> list[MemoryEntry]:
        query_embedding = self._embed(query)

        cursor = self.conn.execute("""
            SELECT m.key, m.value, m.kind, m.timestamp
            FROM vec_memories v
            JOIN memories m ON m.id = v.memory_id
            WHERE v.embedding MATCH ? AND k = ?
            ORDER BY distance
        """, (sqlite_vec.serialize_float32(query_embedding), limit))

        results = []
        for row in cursor.fetchall():
            results.append(MemoryEntry(
                key=row[0], value=row[1], kind=row[2],
                timestamp=datetime.fromisoformat(row[3])
            ))
        return results

    async def clear(self) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM memories")
            self.conn.execute("DELETE FROM vec_memories")

    async def get_all(self) -> list[MemoryEntry]:
        cursor = self.conn.execute(
            "SELECT key, value, kind, timestamp FROM memories")
        return [
            MemoryEntry(
                key=row[0], value=row[1], kind=row[2],
                timestamp=datetime.fromisoformat(row[3])
            )
            for row in cursor.fetchall()
        ]

    def preamble(self, limit: int = 10) -> str:
        cursor = self.conn.execute(
            "SELECT key, value FROM memories ORDER BY timestamp DESC LIMIT ?", (
                limit,)
        )
        rows = cursor.fetchall()
        if not rows:
            return ""

        lines = ["Hechos recordados:"]
        for key, value in rows:
            lines.append(f"- {key}: {value}")
        return "\n".join(lines)
