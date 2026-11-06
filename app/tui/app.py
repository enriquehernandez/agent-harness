import asyncio
import json
from pathlib import Path
from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.styles import Style
from rich.console import Console

from app.core.llm import get_llm
from app.core.harness import AgentLoop, ToolRegistry, ContextManager
from app.core.harness.permissions import PermissionGate
from app.tools import register_core_tools
from app.tui.prompt import ask_user_permission
from app.tui.commands import handle_command
from app.mcp.client import MCPClient  # 🔥 NUEVO

console = Console()

style = Style.from_dict({
    'prompt': 'ansicyan bold',
})


async def run_tui():
    state = {"provider": "fake"}
    ctx = ContextManager(
        system_prompt="Eres un asistente útil. Tienes acceso a herramientas locales y remotas (MCP)."
    )

    registry = ToolRegistry()
    register_core_tools(registry)

    # 🔥 NUEVO: Cargar y conectar servidores MCP
    mcp_clients = []
    config_path = Path("mcp_config.json")
    if config_path.exists():
        with open(config_path, "r") as f:
            config = json.load(f)

        for name, server_conf in config.get("mcpServers", {}).items():
            console.print(f"[dim]Conectando al servidor MCP '{name}'...[/dim]")
            try:
                client = MCPClient(
                    command=server_conf["command"],
                    args=server_conf["args"]
                )
                await client.connect()
                await client.register_tools(registry)
                mcp_clients.append(client)
                console.print(f"[dim]✅ MCP '{name}' conectado.[/dim]")
            except Exception as e:
                console.print(
                    f"[bold red]Error conectando MCP '{name}': {e}[/bold red]")
    else:
        console.print(
            "[dim yellow]No se encontró mcp_config.json. Solo se usarán herramientas locales.[/dim yellow]")

    gate = PermissionGate(ask_user=ask_user_permission)

    session = PromptSession(
        history=InMemoryHistory(),
        style=style,
        multiline=False,
    )

    console.print("\n[bold green]🤖 Agent Harness iniciado.[/bold green]")
    console.print(
        "Escribe [bold cyan]/help[/bold cyan] para ver los comandos disponibles.\n")

    try:
        while True:
            user_input = await session.prompt_async("🐚 > ")
            user_input = user_input.strip()
            if not user_input:
                continue

            llm = get_llm(state["provider"])

            if user_input.startswith("/"):
                await handle_command(user_input, ctx, state, llm)
                continue

            loop = AgentLoop(llm=llm, tools=registry, permissions=gate)
            with console.status("[bold green]Pensando...[/bold green]"):
                result = await loop.run(user_input, context=ctx)

            console.print(
                f"[bold green]🤖 Agente:[/bold green] {result.final_answer}\n")
            console.print(
                f"[dim]Pasos: {result.steps} | Tools: {result.tools_used} | Tokens API: {result.usage_total.get('total_tokens', 0)}[/dim]\n")

    except KeyboardInterrupt:
        pass
    except EOFError:
        pass
    except SystemExit:
        pass
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
    finally:
        # 🔥 NUEVO: Cierre limpio de MCP
        for client in mcp_clients:
            await client.disconnect()
        console.print("[dim]Conexiones MCP cerradas.[/dim]")

if __name__ == "__main__":
    asyncio.run(run_tui())
