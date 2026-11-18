import re
from pathlib import Path
from datetime import datetime
from app.core.config import settings
from app.core.harness.memory.base import MemoryStore, MemoryEntry


class SessionFilesStore(MemoryStore):
    def __init__(self, base_dir: Path | None = None):
        if base_dir is None:
            base_dir = settings.memory_files_dir  # 🔥 .harness/memory/
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    async def save(self, entry: MemoryEntry) -> None:
        safe_key = re.sub(r'[^a-zA-Z0-9_\-]', '_', entry.key)
        file_path = self.base_dir / f"{safe_key}.md"
        content = f"# {entry.key}\n\n{entry.value}\n\n_[{entry.kind}] {entry.timestamp.isoformat()}_"
        file_path.write_text(content, encoding="utf-8")
        self._update_summary()

    async def recall(self, query: str, limit: int = 5) -> list[MemoryEntry]:
        results = []
        for file_path in self.base_dir.glob("*.md"):
            if file_path.name == "summary.md":
                continue
            content = file_path.read_text(encoding="utf-8")
            if query.lower() in content.lower():
                lines = content.split("\n")
                key = lines[0].replace("# ", "")
                value = "\n".join(lines[2:]).split("_[")[0].strip()
                results.append(MemoryEntry(
                    key=key, value=value, timestamp=datetime.now(), kind="fact"
                ))
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
        for file_path in self.base_dir.glob("*.md"):
            if file_path.name == "summary.md":
                continue
            all_memories.append(file_path.read_text(encoding="utf-8"))
        summary_content = "# Long-Term Memory Summary\n\n" + \
            "\n\n---\n\n".join(all_memories)
        (self.base_dir / "summary.md").write_text(summary_content, encoding="utf-8")

    async def get_all(self) -> list[MemoryEntry]:
        results = []
        for file_path in self.base_dir.glob("*.md"):
            if file_path.name == "summary.md":
                continue
            content = file_path.read_text(encoding="utf-8")
            lines = content.split("\n")
            key = lines[0].replace("# ", "")
            value = "\n".join(lines[2:]).split("_[")[0].strip()
            results.append(MemoryEntry(
                key=key, value=value, timestamp=datetime.now(), kind="fact"
            ))
        return results
