import re
from pathlib import Path
from datetime import datetime
from app.core.config import settings
from app.core.harness.memory.base import MemoryStore, MemoryEntry


def _parse_memory_file(content: str) -> MemoryEntry | None:
    """Parsea el contenido de un archivo .md de memoria."""
    try:
        lines = content.split("\n")
        if not lines or not lines[0].startswith("# "):
            return None
        key = lines[0][2:].strip()
        body = "\n".join(lines[2:]).strip()
        match = re.search(r"_\[(\w+)\]\s+(.+?)_\s*$", body, re.DOTALL)
        if match:
            kind = match.group(1)
            timestamp_str = match.group(2).strip()
            body = body[: match.start()].strip()
            try:
                timestamp = datetime.fromisoformat(timestamp_str)
            except ValueError:
                timestamp = datetime.now()
        else:
            kind = "fact"
            timestamp = datetime.now()
        return MemoryEntry(key=key, value=body, kind=kind, timestamp=timestamp)
    except Exception:
        return None


class SessionFilesStore(MemoryStore):
    def __init__(self, base_dir: Path | None = None):
        if base_dir is None:
            base_dir = settings.memory_files_dir
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    async def save(self, entry: MemoryEntry) -> None:
        safe_key = re.sub(r"[^a-zA-Z0-9_\-]", "_", entry.key)
        if not safe_key:
            raise ValueError(f"Key inválida: {entry.key!r}")
        file_path = self.base_dir / f"{safe_key}.md"
        content = (
            f"# {entry.key}\n\n{entry.value}\n\n"
            f"_[{entry.kind}] {entry.timestamp.isoformat()}_"
        )
        file_path.write_text(content, encoding="utf-8")
        self._update_summary()

    async def recall(self, query: str, limit: int = 5) -> list[MemoryEntry]:
        results: list[MemoryEntry] = []
        for file_path in sorted(self.base_dir.glob("*.md")):
            if file_path.name == "summary.md":
                continue
            try:
                content = file_path.read_text(encoding="utf-8")
            except Exception:
                continue
            if query.lower() in content.lower():
                entry = _parse_memory_file(content)
                if entry:
                    results.append(entry)
                    if len(results) >= limit:
                        break
        return results

    def preamble(self, limit: int = 5) -> str:
        summary_file = self.base_dir / "summary.md"
        if summary_file.exists():
            return summary_file.read_text(encoding="utf-8")
        return ""

    async def clear(self) -> None:
        for f in self.base_dir.glob("*.md"):
            f.unlink()

    def _update_summary(self):
        all_memories = []
        for file_path in sorted(self.base_dir.glob("*.md")):
            if file_path.name == "summary.md":
                continue
            all_memories.append(file_path.read_text(encoding="utf-8"))
        summary_content = "# Long-Term Memory Summary\n\n" + \
            "\n\n---\n\n".join(all_memories)
        (self.base_dir / "summary.md").write_text(summary_content, encoding="utf-8")

    async def get_all(self) -> list[MemoryEntry]:
        results: list[MemoryEntry] = []
        for file_path in sorted(self.base_dir.glob("*.md")):
            if file_path.name == "summary.md":
                continue
            try:
                content = file_path.read_text(encoding="utf-8")
            except Exception:
                continue
            entry = _parse_memory_file(content)
            if entry:
                results.append(entry)
        return results
