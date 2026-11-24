from pathlib import Path
from typing import Any
from app.core.harness.tool import BaseTool, ToolResult
from app.core.logger import logger


def _is_within_base_dir(target: Path, base_dir: Path) -> bool:
    """Comprueba que `target` está dentro de `base_dir` (resuelto)."""
    try:
        target.resolve().relative_to(base_dir.resolve())
        return True
    except ValueError:
        return False


class ReadFileTool(BaseTool):
    def __init__(self, base_dir: str = "."):
        self.name = "read_file"
        self.description = "Read the content of a text file. Use it to inspect code or logs."
        self.parameters_schema = {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path of the file to read (e.g., 'app/main.py').",
                }
            },
            "required": ["path"],
        }
        self.base_dir = Path(base_dir).resolve()

    async def run(self, path: str, **kwargs) -> ToolResult:
        try:
            target = (self.base_dir / path).resolve()
            if not _is_within_base_dir(target, self.base_dir):
                return ToolResult(success=False, content="", error="Access denied: outside base directory.")

            if not target.is_file():
                return ToolResult(success=False, content="", error=f"File '{path}' does not exist.")

            content = target.read_text(encoding="utf-8")
            if len(content) > 10000:
                content = content[:10000] + "\n\n... [TRUNCATED]"

            return ToolResult(success=True, content=content)
        except Exception as e:
            logger.error(f"ReadFileTool: error leyendo '{path}': {e}")
            return ToolResult(success=False, content="", error=str(e))


class EditFileTool(BaseTool):
    def __init__(self, base_dir: str = "."):
        self.name = "edit_file"
        self.description = (
            "Replace exact text in an existing file with a list of edits. "
            "Each edit has 'oldText' and 'newText'."
        )
        self.parameters_schema = {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path of the file to edit.",
                },
                "edits": {
                    "type": "array",
                    "minItems": 1,
                    "items": {
                        "type": "object",
                        "properties": {
                            "oldText": {"type": "string"},
                            "newText": {"type": "string"},
                        },
                        "required": ["oldText", "newText"],
                    },
                },
            },
            "required": ["path", "edits"],
        }
        self.base_dir = Path(base_dir).resolve()

    async def run(self, path: str, edits: list[dict], **kwargs) -> ToolResult:
        try:
            target = (self.base_dir / path).resolve()
            if not _is_within_base_dir(target, self.base_dir):
                return ToolResult(success=False, content="", error="Access denied: outside base directory.")

            if not target.is_file():
                return ToolResult(success=False, content="", error=f"File '{path}' does not exist.")

            content = target.read_text(encoding="utf-8")
            for edit in edits:
                old_text = edit.get("oldText", "")
                new_text = edit.get("newText", "")
                if not old_text:
                    return ToolResult(
                        success=False, content="",
                        error="Empty 'oldText': no se puede editar el archivo."
                    )
                if old_text not in content:
                    return ToolResult(
                        success=False, content="",
                        error=f"Text to replace not found: {old_text[:20]}..."
                    )
                content = content.replace(old_text, new_text)

            target.write_text(content, encoding="utf-8")
            return ToolResult(
                success=True, content=f"File '{path}' updated with {len(edits)} edit(s)."
            )
        except Exception as e:
            logger.error(f"EditFileTool: error editando '{path}': {e}")
            return ToolResult(success=False, content="", error=str(e))


class WriteFileTool(BaseTool):
    def __init__(self, base_dir: str = "."):
        self.name = "write_file"
        self.description = "Write (or overwrite) content to a file. Creates necessary directories."
        self.parameters_schema = {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path of the file."},
                "content": {"type": "string", "description": "The content to write."},
            },
            "required": ["path", "content"],
        }
        self.base_dir = Path(base_dir).resolve()

    async def run(self, path: str, content: str) -> ToolResult:
        try:
            target = (self.base_dir / path).resolve()
            if not _is_within_base_dir(target, self.base_dir):
                return ToolResult(success=False, content="", error="Access denied: outside base directory.")

            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            return ToolResult(success=True, content=f"File '{path}' written successfully ({len(content)} bytes).")
        except Exception as e:
            return ToolResult(success=False, content="", error=str(e))
