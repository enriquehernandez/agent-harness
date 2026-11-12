from datetime import datetime
from app.core.harness.tool import BaseTool, ToolResult
from app.core.harness.memory.base import MemoryEntry


class MemorySaveTool(BaseTool):
    def __init__(self, store):
        self.name = "memory_save"
        self.description = "Save a fact or preference in long-term memory."
        self.store = store
        self.parameters_schema = {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Short title."},
                "value": {"type": "string", "description": "Content to remember."}
            },
            "required": ["key", "value"]
        }

    async def run(self, key: str, value: str) -> ToolResult:
        try:
            entry = MemoryEntry(
                key=key, value=value, timestamp=datetime.now(), kind="fact"
            )
            await self.store.save(entry)
            return ToolResult(success=True, content=f"Memory saved: '{key}'.")
        except Exception as e:
            return ToolResult(success=False, content="", error=str(e))


class MemoryRecallTool(BaseTool):
    def __init__(self, store):
        self.name = "memory_recall"
        self.description = "Search long-term memory."
        self.store = store
        self.parameters_schema = {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Keyword to search."}
            },
            "required": ["query"]
        }

    async def run(self, query: str) -> ToolResult:
        try:
            entries = await self.store.recall(query)
            if not entries:
                return ToolResult(success=True, content=f"No memories found for '{query}'.")
            text = "\n".join([f"- {e.key}: {e.value}" for e in entries])
            return ToolResult(success=True, content=f"Memories found:\n{text}")
        except Exception as e:
            return ToolResult(success=False, content="", error=str(e))
