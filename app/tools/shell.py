import asyncio
import json
import re
from pathlib import Path
from app.core.config import settings
from app.core.logger import logger
from app.core.harness.tool import BaseTool, ToolResult


class BashTool(BaseTool):
    def __init__(self, timeout_seconds: int = 30, export_observations=None):
        self.name = "bash"
        self.description = (
            "Ejecuta un comando de shell (bash) en el sistema. "
            "Úsalo para correr tests, instalar dependencias o explorar el sistema."
        )
        self.parameters_schema = {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "El comando a ejecutar (ej. 'ls -la', 'uv run pytest')."
                }
            },
            "required": ["command"]
        }
        self.timeout_seconds = timeout_seconds
        self.export_observations = export_observations
        self.timeout_seconds = timeout_seconds if timeout_seconds is not None else settings.TOOL_TIMEOUT

    async def run(self, command: str) -> ToolResult:
        try:
            # 🔥 Hook: si el comando usa capture_snapshot.py, generar observations.json
            # y añadir el flag --tools automáticamente.
            if "capture_snapshot.py" in command:
                logger.debug(f"Hook detectado: {command}")

                # 1. Generar observations.json si no existe
                if self.export_observations:
                    logger.debug("Generando observations.json...")
                    await self.export_observations.run("observations.json")

                # 2. Añadir --tools observations.json al comando si no está ya
                if "--tools" not in command:
                    # Insertamos --tools antes del --out (o al final si no hay --out)
                    if "--out" in command:
                        command = re.sub(
                            r'(capture_snapshot\.py)(\s+.*?)(--out)',
                            r'\1\2--tools observations.json \3',
                            command
                        )
                    else:
                        command += " --tools observations.json"
                    logger.debug(f"Comando modificado: {command}")

            # 3. Ejecutar el comando (original o modificado)
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.timeout_seconds
                )
            except asyncio.TimeoutError:
                process.kill()
                return ToolResult(success=False, content="", error=f"Timeout de {self.timeout_seconds}s excedido.")

            out_str = stdout.decode(errors="replace").strip()
            err_str = stderr.decode(errors="replace").strip()

            if process.returncode != 0:
                error_msg = err_str or out_str or f"Exit code {process.returncode}"
                return ToolResult(success=False, content="", error=error_msg)

            return ToolResult(success=True, content=out_str or "Comando ejecutado sin salida.")

        except Exception as e:
            return ToolResult(success=False, content="", error=str(e))
