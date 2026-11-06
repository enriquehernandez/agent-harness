import asyncio
from typing import Any
from app.core.harness.tool import BaseTool, ToolResult


class BashTool(BaseTool):
    def __init__(self, timeout_seconds: int = 30):
        self.name = "bash"
        self.description = "Ejecuta un comando de shell (bash) en el sistema. Úsalo para correr tests, instalar dependencias o explorar el sistema."
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

    async def run(self, command: str) -> ToolResult:
        try:
            # Ejecutamos en un subproceso
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

            # Si falla, devolvemos el stderr como error
            if process.returncode != 0:
                error_msg = err_str or out_str or f"Exit code {process.returncode}"
                return ToolResult(success=False, content="", error=error_msg)

            return ToolResult(success=True, content=out_str or "Comando ejecutado sin salida.")

        except Exception as e:
            return ToolResult(success=False, content="", error=str(e))
