from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

console = Console()


async def ask_user_permission(tool_name: str, title: str, args: dict) -> str:
    """Pregunta interactiva usando rich."""
    console.print()

    # Formatear los argumentos de forma bonita
    args_str = ""
    for k, v in args.items():
        if isinstance(v, str) and "\n" in v:
            # Si es un texto largo (ej. un comando o código), lo formateamos como bloque
            args_str += f"[bold cyan]{k}[/bold cyan]:\n"
            # Usamos el bloque de código con formato nativo de Rich
            lang = "bash" if tool_name == "bash" else "text"
            args_str += f"```{lang}\n{v}\n```\n"
        else:
            args_str += f"[bold cyan]{k}[/bold cyan]: {v}\n"

    panel = Panel(
        args_str,
        title=f"🛠️  [bold yellow]El agente quiere usar: {tool_name}[/bold yellow]",
        subtitle="[dim]y = Permitir una vez | a = Permitir siempre en esta sesión | n = Denegar[/dim]",
        border_style="yellow",
    )
    console.print(panel)

    # Prompt interactivo
    response = Prompt.ask(
        "[bold yellow]¿Permitir ejecución?[/bold yellow]",
        choices=["y", "n", "a"],
        default="n"
    )
    return response
