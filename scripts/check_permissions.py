import asyncio
from app.core.llm import get_llm
from app.core.llm.base import LLMResponse
from app.core.harness import AgentLoop, ToolRegistry
from app.core.harness.permissions import PermissionGate
from app.tools import register_core_tools
from app.tui.prompt import ask_user_permission


async def main():
    # 1. Registramos tools
    registry = ToolRegistry()
    register_core_tools(registry)

    # 2. Configuramos el PermissionGate con la TUI
    gate = PermissionGate(ask_user=ask_user_permission)

    # 3. Simulamos un LLM
    fake = get_llm("fake", responses=[
        # Turno 1: Intenta leer un archivo (ALLOW por defecto)
        LLMResponse(
            content=None,
            tool_calls=[{"id": "c1", "name": "read_file",
                         "arguments": {"path": "pyproject.toml"}}],
        ),
        # Turno 2: Intenta ejecutar bash (ASK)
        LLMResponse(
            content=None,
            tool_calls=[{"id": "c2", "name": "bash", "arguments": {
                "command": "echo 'Hackeando el sistema...'"}}],
        ),
        # Turno 3: Responde
        LLMResponse(content="He terminado mi tarea."),
    ])

    loop = AgentLoop(llm=fake, tools=registry, permissions=gate)
    result = await loop.run("Haz tu magia.")

    print(f"\n[bold green]Respuesta final:[/bold green] {result.final_answer}")
    # 🔥 Añadimos el detalle de las herramientas
    print(f"[bold cyan]Pasos:[/bold cyan] {result.steps}")
    print(f"[bold cyan]Tools usadas:[/bold cyan] {result.tools_used}")

if __name__ == "__main__":
    asyncio.run(main())
