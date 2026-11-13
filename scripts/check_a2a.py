import asyncio
import argparse
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from app.core.config import settings
from app.core.logger import logger
from app.core.llm import get_llm
from app.core.harness.tool import ToolRegistry
from app.core.harness.a2a import AgentCard, OrchestratorTool
from app.core.harness.permissions import PermissionGate, Decision

console = Console()

# 🎯 ¿Qué verás?
# --strategy supervisor: El LLM elige un agente (probablemente analyst).

# --strategy sequential: Ejecuta analyst → writer → reviewer en cadena.

# --strategy parallel: Lanza analyst y reviewer en paralelo (con asyncio.gather). Verás las respuestas consolidadas.

# --strategy swarm: Empieza con analyst y, si su respuesta contiene HANDOFF: writer, transfiere el control.


# # Probar con la estrategia del .env
# uv run python scripts/check_a2a.py

# # Forzar una estrategia específica
# uv run python scripts/check_a2a.py --strategy parallel
# uv run python scripts/check_a2a.py --strategy swarm

# # Forzar una tarea específica
# uv run python scripts/check_a2a.py --strategy sequential --task "Revisa el archivo pyproject.toml"

# uv run python scripts/check_a2a.py --strategy swarm --task "Analiza el archivo pyproject.toml y si necesitas documentación, responde 'HANDOFF: writer'" 2>&1 | grep -E "Swarm|Tool|ERROR|WARNING"

async def main():
    parser = argparse.ArgumentParser(description="Diagnóstico del Sistema A2A")
    parser.add_argument("--strategy", type=str, default=None,
                        help="Forzar estrategia: supervisor, sequential, parallel, swarm")
    parser.add_argument(
        "--task", type=str, default="Analiza el archivo app/core/harness/loop.py y dime cuántas líneas tiene.", help="Tarea a ejecutar")
    args = parser.parse_args()

    # 🔥 Si se pasa --strategy, sobreescribimos la configuración
    if args.strategy:
        settings.A2A_STRATEGY = args.strategy
        console.print(
            f"[yellow]⚠️ Estrategia forzada por CLI: `{args.strategy}`[/yellow]")

    console.print(Panel.fit(
        "[bold]Diagnóstico del Sistema Agent-to-Agent (A2A)[/bold]\n"
        "Verifica que el Orquestador y los subagentes funcionan correctamente.",
        border_style="cyan"
    ))

    # 1. Mostrar configuración
    console.print("\n[bold]1. Configuración actual:[/bold]")
    console.print(f"  - Estrategia: `{settings.A2A_STRATEGY}`")
    console.print(f"  - Secuencia (sequential): `{settings.A2A_SEQUENCE}`")
    console.print(
        f"  - Agentes paralelos (parallel): `{settings.A2A_PARALLEL_AGENTS}`")
    console.print(f"  - Agente inicial (swarm): `{settings.A2A_SWARM_START}`")
    console.print(f"  - Proveedor LLM: `{settings.LLM_PROVIDER}`")

    # 2. Crear LLM y permisos
    llm = get_llm(settings.LLM_PROVIDER)
    gate = PermissionGate()
    # Para el script de diagnóstico, permitimos todo automáticamente
    gate.policies = {
        "read_file": Decision.ALLOW,
        "read_text_file": Decision.ALLOW,
        "bash": Decision.ALLOW,
        "write_file": Decision.ALLOW,
    }
    logger.info(f"CheckA2A: gate policies={gate.policies}")  # 🔥 LOG

    # 3. Crear registry de tools para los agentes
    base_tools = ToolRegistry()
    from app.tools.filesystem import ReadFileTool
    from app.tools.shell import BashTool
    base_tools.register(ReadFileTool())
    base_tools.register(BashTool())

    # 4. Definir los agentes (los mismos que en app.py)
    a2a_agents = {
        # "analyst": AgentCard(
        #     name="analyst",
        #     description="Analiza código y genera reportes.",
        #     system_prompt=(
        #         "Eres un analista experto. Analiza el código y reporta hallazgos. "
        #         "SIEMPRE debes terminar tu respuesta con 'HANDOFF: writer' para que el writer documente tu análisis."
        #     ),
        #     tools=base_tools,
        #     mode="isolated",
        # ),
        "analyst": AgentCard(
            name="analyst",
            description="Analiza código y genera reportes.",
            system_prompt="Eres un analista experto. Analiza el código y reporta hallazgos.",
            tools=base_tools,
            mode="isolated",
        ),
        "writer": AgentCard(
            name="writer",
            description="Escribe documentación siguiendo un análisis.",
            system_prompt="Eres un escritor técnico. Documenta con claridad.",
            tools=base_tools,
            mode="fork",
        ),
        "reviewer": AgentCard(
            name="reviewer",
            description="Revisa el trabajo de otros agentes.",
            system_prompt="Eres un revisor estricto. Señala errores.",
            tools=base_tools,
            mode="isolated",
        ),
    }

    console.print("\n[bold]2. Agentes registrados:[/bold]")
    table = Table()
    table.add_column("Nombre", style="cyan")
    table.add_column("Modo", style="green")
    table.add_column("Descripción", style="yellow")
    for name, card in a2a_agents.items():
        table.add_row(name, card.mode, card.description)
    console.print(table)

    # 5. Crear el Orquestador
    orchestrator = OrchestratorTool(
        llm=llm, agents=a2a_agents, permissions=gate)

    # 6. Probar el Orquestador
    task = args.task
    console.print(f"\n[bold]3. Probando Orquestador con tarea:[/bold]")
    console.print(f"   [italic]'{task}'[/italic]")

    result = await orchestrator.run(task)

    if result.success:
        console.print(
            "\n[bold green]✅ Orquestador respondió con éxito:[/bold green]")
        console.print(Panel(result.content, border_style="green"))
    else:
        console.print(f"\n[bold red]❌ Error: {result.error}[/bold red]")


if __name__ == "__main__":
    asyncio.run(main())
