from pathlib import Path
from typing import Any
from app.core.harness.tool import BaseTool, ToolResult


class ReadFileTool(BaseTool):
    def __init__(self, base_dir: str = "."):
        self.name = "read_file"
        self.description = "Read the content of a text file. Use it to inspect code or logs."
        self.parameters_schema = {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path of the file to read (e.g., 'app/main.py')."
                }
            },
            "required": ["path"]
        }
        self.base_dir = Path(base_dir).resolve()

    async def run(self, path: str) -> ToolResult:
        try:
            target = (self.base_dir / path).resolve()
            if not str(target).startswith(str(self.base_dir)):
                return ToolResult(success=False, content="", error="Access denied: outside base directory.")

            if not target.is_file():
                return ToolResult(success=False, content="", error=f"File '{path}' does not exist.")

            content = target.read_text(encoding="utf-8")
            if len(content) > 10000:
                content = content[:10000] + "\n\n... [TRUNCATED]"

            return ToolResult(success=True, content=content)
        except Exception as e:
            return ToolResult(success=False, content="", error=str(e))


class WriteFileTool(BaseTool):
    def __init__(self, base_dir: str = "."):
        self.name = "write_file"
        self.description = "Write (or overwrite) content to a file. Creates necessary directories."
        self.parameters_schema = {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path of the file."},
                "content": {"type": "string", "description": "The content to write."}
            },
            "required": ["path", "content"]
        }
        self.base_dir = Path(base_dir).resolve()

    async def run(self, path: str, content: str) -> ToolResult:
        try:
            target = (self.base_dir / path).resolve()
            if not str(target).startswith(str(self.base_dir)):
                return ToolResult(success=False, content="", error="Access denied: outside base directory.")

            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            return ToolResult(success=True, content=f"File '{path}' written successfully ({len(content)} bytes).")
        except Exception as e:
            return ToolResult(success=False, content="", error=str(e))
