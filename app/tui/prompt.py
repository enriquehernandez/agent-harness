from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

console = Console()


async def ask_user_permission(tool_name: str, signature: str, args: dict, diff_text: str | None = None) -> str:
    """Pregunta interactiva usando rich."""

    args_str = ""
    for k, v in args.items():
        if k in ("content", "edits") and diff_text:
            continue
        if isinstance(v, str) and "\n" in v:
            args_str += f"[bold cyan]{k}[/bold cyan]:\n"
            lang = "bash" if tool_name == "bash" else "text"
            args_str += f"```{lang}\n{v}\n```\n"
        else:
            args_str += f"[bold cyan]{k}[/bold cyan]: {v}\n"

    if diff_text:
        args_str += "\n[bold yellow]Propuesta de cambios (Diff):[/bold yellow]\n"
        args_str += f"```diff\n{diff_text}\n```\n"

    subtitle = (
        f"[dim]y = Permitir esta vez | "
        f"a = Permitir siempre [bold]{signature}[/bold] | "
        f"n = Denegar[/dim]"
    )

    panel = Panel(
        args_str,
        title=f"🛠️  [bold yellow]El agente quiere usar: {tool_name}[/bold yellow]",
        subtitle=subtitle,
        border_style="yellow",
    )

    # Imprimimos el panel
    console.print(panel)

    # Pedimos el input
    response = Prompt.ask(
        "[bold yellow]¿Permitir ejecución?[/bold yellow]",
        choices=["y", "n", "a"],
        default="n"
    )
    return response
