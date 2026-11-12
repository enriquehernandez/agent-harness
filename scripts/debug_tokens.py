import asyncio
import json
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from app.core.llm import get_llm
from app.core.harness import AgentLoop, ToolRegistry, ContextManager
from app.core.harness.permissions import PermissionGate, Decision
from app.core.harness.memory.factory import create_memory_store
from app.core.config import settings
from app.tools import register_core_tools

console = Console()


async def main():
    console.print(Panel.fit(
        "[bold]Diagnóstico de Tokens y Tools[/bold]\n"
        "Ejecuta una conversación con el LLM y muestra el usage real.",
        border_style="cyan"
    ))

    # 1. Configuración
    provider = settings.LLM_PROVIDER
    model = getattr(settings, f"{provider.upper()}_MODEL", "desconocido")
    console.print(f"\n[bold]Proveedor:[/bold] {provider}")
    console.print(f"[bold]Modelo:[/bold] {model}")

    # 2. Creamos el LLM
    llm = get_llm(provider)

    # 3. Creamos el registry con tools
    memory_store = create_memory_store(settings.MEMORY_BACKEND)
    registry = ToolRegistry()
    register_core_tools(registry, memory_store=memory_store)

    # 4. Creamos el PermissionGate que permite todo (para no bloquear)
    gate = PermissionGate(ask_user=None)  # Sin UI, permite todo
    gate.policies = {name: Decision.ALLOW for name in registry.names()}

    # 5. Creamos el AgentLoop
    loop = AgentLoop(llm=llm, tools=registry,
                     permissions=gate, max_iterations=5)

    # 6. Contexto
    ctx = ContextManager(
        system_prompt="Eres un asistente útil. Usa herramientas si es necesario.")

    # 7. Pregunta que fuerza el uso de una tool
    question = "¿Qué archivos hay en la carpeta app/core/harness? Usa 'list_directory'."
    console.print(f"\n[bold yellow]Pregunta:[/bold yellow] {question}")

    # 8. Ejecutamos el stream
    console.print("\n[bold]Iniciando stream...[/bold]")

    full_text = ""
    final_result = None

    async for chunk in loop.stream(question, context=ctx):
        if isinstance(chunk, str):
            full_text += chunk
        elif isinstance(chunk, dict):
            if chunk.get("type") == "tool_call":
                console.print(
                    f"  [dim]🛠️ Tool call: {chunk['name']} → {chunk['arguments']}[/dim]")
            elif chunk.get("type") == "usage":
                console.print(
                    f"  [dim]📊 Usage recibido: {chunk['usage']}[/dim]")
            elif chunk.get("type") == "result":
                final_result = chunk
                break

    # 9. Mostramos resultados
    console.print("\n[bold green]=== Resultado Final ===[/bold green]")

    if final_result:
        table = Table(title="Métricas")
        table.add_column("Métrica", style="cyan")
        table.add_column("Valor", style="green")

        table.add_row("Respuesta final", full_text[:100] + "...")
        table.add_row("Pasos", str(final_result.get("steps", 0)))
        table.add_row("Tools usadas", str(final_result.get("tools_used", [])))
        table.add_row("Usage total", json.dumps(
            final_result.get("usage_total", {}), indent=2))

        console.print(table)

        # 10. Verificamos si el usage está vacío
        if not final_result.get("usage_total"):
            console.print(
                "\n[bold red]⚠️ EL USAGE ESTÁ VACÍO. Posibles causas:[/bold red]")
            console.print(
                "  - El proveedor no envía usage en streaming (ej. modelos free de OpenRouter).")
            console.print(
                "  - El stream_options={'include_usage': True} no está soportado.")
            console.print("  - El AgentLoop no está capturando el usage.")
            console.print(
                "\n[bold yellow]Fallback:[/bold yellow] Estimación de tokens =", len(full_text) // 4)
        else:
            console.print(
                "\n[bold green]✅ El usage se capturó correctamente.[/bold green]")
    else:
        console.print(
            "[bold red]❌ No se recibió el resultado final.[/bold red]")


if __name__ == "__main__":
    asyncio.run(main())
