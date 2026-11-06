from rich.console import Console
from app.core.harness.context import ContextManager
from app.core.llm.registry import list_providers
from app.core.llm.base import BaseLLM

console = Console()

# 🔥 NUEVO: Firma ahora es async y recibe el llm


async def handle_command(command: str, ctx: ContextManager, state: dict, llm: BaseLLM) -> bool:
    """
    Procesa comandos con '/'. 
    Devuelve True si el comando fue manejado (no debe ir al LLM), False si debe ir al LLM.
    """
    parts = command.strip().split()
    cmd = parts[0].lower()

    if cmd == "/quit" or cmd == "/exit":
        console.print("[bold red]Saliendo del Harness...[/bold red]")
        raise SystemExit(0)

    elif cmd == "/help":
        console.print("[bold cyan]Comandos disponibles:[/bold cyan]")
        console.print(
            "  [bold green]/help[/bold green]      Muestra esta ayuda")
        console.print(
            "  [bold green]/model[/bold green]     Muestra o cambia el LLM actual (ej. /model fake)")
        console.print(
            "  [bold green]/tokens[/bold green]    Muestra el uso estimado de tokens de la sesión")
        console.print(
            "  [bold green]/compact[/bold green]   Fuerza la compactación del contexto (resumen)")
        console.print(
            "  [bold green]/clear[/bold green]     Limpia el historial de conversación")
        console.print(
            "  [bold green]/quit[/bold green]      Sale del programa")
        return True

    elif cmd == "/tokens":
        tokens = ctx.estimate_tokens()
        limit = llm.max_context_window
        console.print(
            f"[bold yellow]Tokens estimados:[/bold yellow] {tokens} / {limit} ({(tokens/limit)*100:.1f}%)")
        return True

    elif cmd == "/clear":
        ctx.clear()
        console.print(
            "[bold yellow]Historial de conversación limpiado.[/bold yellow]")
        return True

    elif cmd == "/model":
        if len(parts) > 1:
            new_model = parts[1]
            state["provider"] = new_model
            console.print(
                f"[bold green]Proveedor cambiado a:[/bold green] {new_model}")
        else:
            available = ", ".join(list_providers())
            current = state.get("provider", "desconocido")
            console.print(
                f"[bold yellow]Proveedor actual:[/bold yellow] {current}")
            console.print(f"[dim]Disponibles: {available}[/dim]")
        return True

    elif cmd == "/compact":
        console.print("[bold yellow]Compactando contexto...[/bold yellow]")
        old_len = len(ctx.messages)
        old_tokens = ctx.estimate_tokens()

        await ctx.force_compact(llm)

        new_len = len(ctx.messages)
        new_tokens = ctx.estimate_tokens()
        console.print(
            f"[bold green]Contexto compactado.[/bold green] Mensajes: {old_len} -> {new_len} | Tokens: {old_tokens} -> {new_tokens}")
        return True

    else:
        console.print(
            f"[bold red]Comando desconocido: {cmd}[/bold red]. Usa /help.")
        return True

    return False
