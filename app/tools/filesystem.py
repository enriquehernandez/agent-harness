from pathlib import Path
from typing import Any
from app.core.harness.tool import BaseTool, ToolResult


class ReadFileTool(BaseTool):
    def __init__(self, base_dir: str = "."):
        self.name = "read_file"
        self.description = "Lee el contenido de un archivo de texto. Úsalo para inspeccionar código o logs."
        self.parameters_schema = {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Ruta relativa del archivo a leer (ej. 'app/main.py')."
                }
            },
            "required": ["path"]
        }
        self.base_dir = Path(base_dir).resolve()

    async def run(self, path: str) -> ToolResult:
        try:
            # Resolución segura para evitar salir del directorio base (Path Traversal)
            target = (self.base_dir / path).resolve()
            if not str(target).startswith(str(self.base_dir)):
                return ToolResult(success=False, content="", error="Acceso denegado: fuera del directorio base.")

            if not target.is_file():
                return ToolResult(success=False, content="", error=f"El archivo '{path}' no existe.")

            content = target.read_text(encoding="utf-8")
            # Truncar si es muy largo para no reventar el contexto
            if len(content) > 10000:
                content = content[:10000] + "\n\n... [TRUNCADO]"

            return ToolResult(success=True, content=content)
        except Exception as e:
            return ToolResult(success=False, content="", error=str(e))


class WriteFileTool(BaseTool):
    def __init__(self, base_dir: str = "."):
        self.name = "write_file"
        self.description = "Escribe (o sobrescribe) contenido en un archivo. Crea los directorios necesarios."
        self.parameters_schema = {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Ruta relativa del archivo."},
                "content": {"type": "string", "description": "El contenido a escribir."}
            },
            "required": ["path", "content"]
        }
        self.base_dir = Path(base_dir).resolve()

    async def run(self, path: str, content: str) -> ToolResult:
        try:
            target = (self.base_dir / path).resolve()
            if not str(target).startswith(str(self.base_dir)):
                return ToolResult(success=False, content="", error="Acceso denegado: fuera del directorio base.")

            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            return ToolResult(success=True, content=f"Archivo '{path}' escrito correctamente ({len(content)} bytes).")
        except Exception as e:
            return ToolResult(success=False, content="", error=str(e))
