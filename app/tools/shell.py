import asyncio
from typing import Any
from app.core.harness.tool import BaseTool, ToolResult


class BashTool(BaseTool):
    def __init__(self, timeout_seconds: int = 30):
        self.name = "bash"
        self.description = "Execute a shell command (bash) on the system. Use it to run tests, install dependencies, or explore the system."
        self.parameters_schema = {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The command to execute (e.g., 'ls -la', 'uv run pytest')."
                }
            },
            "required": ["command"]
        }
        self.timeout_seconds = timeout_seconds

    async def run(self, command: str) -> ToolResult:
        try:
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
                return ToolResult(success=False, content="", error=f"Timeout of {self.timeout_seconds}s exceeded.")

            out_str = stdout.decode(errors="replace").strip()
            err_str = stderr.decode(errors="replace").strip()

            if process.returncode != 0:
                error_msg = err_str or out_str or f"Exit code {process.returncode}"
                return ToolResult(success=False, content="", error=error_msg)

            return ToolResult(success=True, content=out_str or "Command executed with no output.")

        except Exception as e:
            return ToolResult(success=False, content="", error=str(e))
