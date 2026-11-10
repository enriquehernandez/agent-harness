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
        self.description = "Guarda un hecho o preferencia importante en la memoria a largo plazo para recordarlo en futuras sesiones."
        self.parameters_schema = {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Un título corto para el recuerdo (ej. 'stack_tecnologico')."},
                "value": {"type": "string", "description": "El contenido o hecho a recordar."}
            },
            "required": ["key", "value"]
        }

    async def run(self, key: str, value: str) -> ToolResult:
        try:
            MEMORY_DIR.mkdir(exist_ok=True)
            safe_key = re.sub(r'[^a-zA-Z0-9_\-]', '_', key)
            file_path = MEMORY_DIR / f"{safe_key}.md"

            # 1. Guardamos el recuerdo individual
            content = f"# {key}\n\n{value}\n"
            file_path.write_text(content, encoding="utf-8")

            # 2. Regeneramos el summary.md dinámicamente
            self._update_summary()

            return ToolResult(success=True, content=f"Recuerdo guardado: '{key}'. La memoria global ha sido actualizada.")
        except Exception as e:
            return ToolResult(success=False, content="", error=str(e))

    def _update_summary(self):
        """Reconstruye summary.md con todos los archivos .md de la carpeta."""
        all_memories = []
        for file_path in MEMORY_DIR.glob("*.md"):
            if file_path.name == "summary.md":
                continue
            content = file_path.read_text(encoding="utf-8").strip()
            all_memories.append(content)

        summary_content = "# Resumen de Memoria a Largo Plazo\n\n"
        summary_content += "\n\n---\n\n".join(all_memories)

        SUMMARY_FILE.write_text(summary_content, encoding="utf-8")


class MemoryRecallTool(BaseTool):
    # ... (el código de MemoryRecallTool se mantiene igual)
    def __init__(self):
        self.name = "memory_recall"
        self.description = "Busca en la memoria a largo plazo hechos o preferencias guardados anteriormente."
        self.parameters_schema = {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Palabra clave o tema a buscar."}
            },
            "required": ["query"]
        }

    async def run(self, query: str) -> ToolResult:
        try:
            if not MEMORY_DIR.exists():
                return ToolResult(success=True, content="La memoria está vacía.")

            results = []
            for file_path in MEMORY_DIR.glob("*.md"):
                if file_path.name == "summary.md":
                    continue
                content = file_path.read_text(encoding="utf-8")
                if query.lower() in content.lower():
                    results.append(content)

            if not results:
                return ToolResult(success=True, content=f"No se encontraron recuerdos para: '{query}'.")

            full_text = "\n---\n".join(results)
            return ToolResult(success=True, content=f"Recuerdos encontrados:\n\n{full_text}")

        except Exception as e:
            return ToolResult(success=False, content="", error=str(e))
