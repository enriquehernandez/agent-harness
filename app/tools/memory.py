import os
import re
from pathlib import Path
from typing import Any
from app.core.harness.tool import BaseTool, ToolResult

MEMORY_DIR = Path(".harness_memory")
SUMMARY_FILE = MEMORY_DIR / "summary.md"


class MemorySaveTool(BaseTool):
    def __init__(self):
        self.name = "memory_save"
        self.description = "Save a fact or preference in long-term memory for future sessions."
        self.parameters_schema = {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "A short title for the memory (e.g., 'tech_stack')."},
                "value": {"type": "string", "description": "The content or fact to remember."}
            },
            "required": ["key", "value"]
        }

    async def run(self, key: str, value: str) -> ToolResult:
        try:
            MEMORY_DIR.mkdir(exist_ok=True)
            safe_key = re.sub(r'[^a-zA-Z0-9_\-]', '_', key)
            file_path = MEMORY_DIR / f"{safe_key}.md"

            content = f"# {key}\n\n{value}\n"
            file_path.write_text(content, encoding="utf-8")

            self._update_summary()

            return ToolResult(success=True, content=f"Memory saved: '{key}'. Global memory updated.")
        except Exception as e:
            return ToolResult(success=False, content="", error=str(e))

    def _update_summary(self):
        all_memories = []
        for file_path in MEMORY_DIR.glob("*.md"):
            if file_path.name == "summary.md":
                continue
            content = file_path.read_text(encoding="utf-8").strip()
            all_memories.append(content)

        summary_content = "# Long-Term Memory Summary\n\n"
        summary_content += "\n\n---\n\n".join(all_memories)

        SUMMARY_FILE.write_text(summary_content, encoding="utf-8")


class MemoryRecallTool(BaseTool):
    def __init__(self):
        self.name = "memory_recall"
        self.description = "Search long-term memory for previously saved facts or preferences."
        self.parameters_schema = {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Keyword or topic to search."}
            },
            "required": ["query"]
        }

    async def run(self, query: str) -> ToolResult:
        try:
            if not MEMORY_DIR.exists():
                return ToolResult(success=True, content="Memory is empty.")

            results = []
            for file_path in MEMORY_DIR.glob("*.md"):
                if file_path.name == "summary.md":
                    continue
                content = file_path.read_text(encoding="utf-8")
                if query.lower() in content.lower():
                    results.append(content)

            if not results:
                return ToolResult(success=True, content=f"No memories found for: '{query}'.")

            full_text = "\n---\n".join(results)
            return ToolResult(success=True, content=f"Memories found:\n\n{full_text}")

        except Exception as e:
            return ToolResult(success=False, content="", error=str(e))
