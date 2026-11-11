import json
import logging
from pathlib import Path

from app.core.logger import logger, get_debug_events
from app.core.harness.context import ContextManager
from app.core.llm.registry import list_providers
from app.core.llm.base import BaseLLM
from app.core.llm import get_llm


async def handle_command(command: str, ctx: ContextManager, state: dict, llm: BaseLLM, app) -> bool:
    parts = command.strip().split()
    cmd = parts[0].lower()

    if cmd in ("/quit", "/exit"):
        await app.write_to_chat("👋 Saliendo del Harness...", type="system")
        app.exit()
        return True

    elif cmd == "/help":
        help_text = (
            "### 🛠️ Comandos Disponibles\n\n"
            "| Comando | Descripción |\n"
            "| :--- | :--- |\n"
            "| `/help` | Muestra esta ayuda |\n"
            "| `/shortcuts` | Muestra los atajos de teclado |\n"
            "| `/model [nombre]` | Muestra o cambia el LLM actual |\n"
            "| `/provider [nombre]` | Muestra o cambia el proveedor (openai/openrouter/etc) |\n"
            "| `/tools` | Lista las herramientas disponibles en el Registry |\n"
            "| `/subagents` | Lista los subagentes registrados |\n"
            "| `/tokens` | Muestra el uso estimado de tokens |\n"
            "| `/compact [estrategia]` | Fuerza la compactación (sliding/summarize/none) |\n"
            "| `/verbose [on/off]` | Muestra/oculta los detalles de la compactación |\n"
            "| `/clear` | Limpia el historial de conversación |\n"
            "| `/debug [on/off/clear]` | Controla el panel de debug |\n"
            "| `/permissions` | Gestiona permisos guardados |\n"
            "| `/quit` | Sale del programa |\n"
        )
        await app.write_to_chat(help_text, type="agent")
        return True

    elif cmd == "/shortcuts" or cmd == "/hotkeys":
        shortcuts = (
            "### ⌨️ Atajos de Teclado\n\n"
            "| Atajo | Acción |\n"
            "| :--- | :--- |\n"
            "| `Ctrl + U` | Limpiar la caja de texto actual |\n"
            "| `Ctrl + L` | Limpiar todo el historial del chat |\n"
            "| `Ctrl + Q` | Salir de la aplicación |\n"
            "| `F1` | Alternar panel de debug |\n"
            "| `Tab` | Navegar por los eventos (si el debug está abierto) |\n"
            "| `Enter` | Enviar el mensaje o comando |\n"
        )
        await app.write_to_chat(shortcuts, type="agent")
        return True

    elif cmd == "/tools":
        if not app.registry:
            await app.write_to_chat("❌ El Registry no está inicializado.", type="system")
            return True

        tools = app.registry.names()
        if not tools:
            await app.write_to_chat("No hay herramientas registradas.", type="system")
            return True

        txt = "### 🧰 Herramientas Disponibles\n\n"
        txt += "| Nombre | Origen |\n"
        txt += "| :--- | :--- |\n"
        for name in tools:
            tool = app.registry.get(name)
            origin = "MCP" if "[MCP]" in tool.description else "Local"
            txt += f"| `{name}` | {origin} |\n"

        await app.write_to_chat(txt, type="agent")
        return True

    elif cmd == "/subagents":
        if not app.registry:
            await app.write_to_chat("❌ El Registry no está inicializado.", type="system")
            return True

        subagents = [name for name in app.registry.names()
                     if name.startswith("delegate_")]

        if not subagents:
            await app.write_to_chat("No hay subagentes registrados.", type="system")
            return True

        txt = "### 🤖 Subagentes Registrados\n\n"
        txt += "| Nombre | Descripción |\n"
        txt += "| :--- | :--- |\n"
        for name in subagents:
            tool = app.registry.get(name)
            txt += f"| `{name}` | {tool.description[:80]}... |\n"

        await app.write_to_chat(txt, type="agent")
        return True

    elif cmd == "/tokens":
        tokens = ctx.estimate_tokens()
        limit = llm.max_context_window
        percentage = (tokens / limit) * 100
        await app.write_to_chat(
            f"**Uso de Tokens:**\n"
            f"- Actuales: `{tokens}`\n"
            f"- Límite: `{limit}`\n"
            f"- Porcentaje: `{percentage:.1f}%`",
            type="agent"
        )
        return True

    elif cmd == "/clear":
        ctx.clear()
        scroll = app.query_one("#chat-scroll")
        await scroll.remove_children()
        await app.write_to_chat("🧹 Historial de conversación limpiado.", type="system")
        return True

    elif cmd in ("/model", "/provider"):
        if len(parts) > 1:
            new_provider = parts[1]
            try:
                new_llm = get_llm(new_provider)
                state["provider"] = new_provider
                if app.agent_loop:
                    app.agent_loop.llm = new_llm
                app.update_dashboard("Listo")
                await app.write_to_chat(f"✅ Proveedor cambiado a: **{new_provider}**", type="system")
            except Exception as e:
                await app.write_to_chat(f"❌ Error al cambiar de proveedor: {e}", type="system")
        else:
            current = state.get("provider", "desconocido")
            available = ", ".join(list_providers())
            model_name = getattr(llm, 'model_name', getattr(
                llm, 'model', 'Desconocido'))
            info = (
                f"### ⚙️ Configuración Actual\n\n"
                f"**Proveedor:** `{current.upper()}`\n\n"
                f"**Modelo:** `{model_name}`\n\n"
                f"**Proveedores disponibles:**\n"
                f"`{available}`"
            )
            await app.write_to_chat(info, type="agent")
        return True

    elif cmd == "/compact":
        strategy_arg = parts[1].lower() if len(parts) > 1 else "summarize"
        if strategy_arg not in ("summarize", "sliding", "none"):
            await app.write_to_chat("❌ Estrategias válidas: `summarize`, `sliding`, `none`.", type="system")
            return True

        strategy_name = ctx.set_strategy(strategy_arg)
        await app.write_to_chat(f"🗜️ **Compactando contexto** (Estrategia: `{strategy_name}`)...", type="system")

        old_len = len(ctx.messages)
        old_tokens = ctx.estimate_tokens()

        verbose = getattr(app, 'verbose_mode', False)
        summary_text = await ctx.force_compact(llm, verbose=verbose)

        new_len = len(ctx.messages)
        new_tokens = ctx.estimate_tokens()

        summary = (
            f"✅ **Contexto compactado**\n\n"
            f"- Mensajes: `{old_len}` ➡️ `{new_len}`\n"
            f"- Tokens: `{old_tokens}` ➡️ `{new_tokens}`"
        )
        await app.write_to_chat(summary, type="agent")

        if verbose and summary_text:
            clean_summary = summary_text.replace("--- Summary of previous conversation ---", "").replace(
                "----------------------------------------", "").strip()
            await app.write_to_chat(
                f"🔊 **Resumen de compactación:**\n\n{clean_summary}",
                type="system"
            )

        return True

    elif cmd == "/verbose":
        if len(parts) > 1:
            subcmd = parts[1].lower()
            if subcmd == "on":
                app.verbose_mode = True
                await app.write_to_chat("🔊 **Modo verbose ACTIVADO.**", type="system")
            elif subcmd == "off":
                app.verbose_mode = False
                await app.write_to_chat("🔇 **Modo verbose DESACTIVADO.**", type="system")
            else:
                await app.write_to_chat("❌ Usa `/verbose on` o `/verbose off`.", type="system")
        else:
            status = "ACTIVADO" if getattr(
                app, 'verbose_mode', False) else "DESACTIVADO"
            await app.write_to_chat(f"🔊 **Verbose:** `{status}`", type="system")
        return True

    elif cmd == "/debug":
        if len(parts) > 1:
            subcmd = parts[1].lower()
            if subcmd == "on":
                logger.setLevel(logging.DEBUG)
                app.debug_mode = True
                await app.toggle_debug_panel(True)
                await app.write_to_chat("🔔 **Debug ACTIVADO.** Panel abierto.", type="system")
            elif subcmd == "off":
                logger.setLevel(logging.INFO)
                app.debug_mode = False
                await app.toggle_debug_panel(False)
                await app.write_to_chat("🔕 **Debug DESACTIVADO.** Panel cerrado.", type="system")
            elif subcmd == "clear":
                app.clear_debug_events()
                await app.write_to_chat("🧹 **Panel de debug limpiado.**", type="system")
            else:
                await app.write_to_chat(f"❌ Subcomando desconocido: `{subcmd}`. Usa `on`, `off` o `clear`.", type="system")
        else:
            status = "ACTIVADO" if logger.level == logging.DEBUG else "DESACTIVADO"
            await app.write_to_chat(f"🪲 **Debug:** `{status}`\nUsa `/debug on`, `/debug off` o `/debug clear`.", type="system")
        return True

    elif cmd == "/permissions":
        perm_file = Path(".harness_permissions.json")
        if not perm_file.exists():
            await app.write_to_chat("No hay permisos guardados en `.harness_permissions.json`.", type="system")
            return True

        data = json.loads(perm_file.read_text())
        allowed = list(data.get("session_allowed", {}).keys())

        if not allowed:
            await app.write_to_chat("No hay herramientas con 'Permitir siempre'.", type="system")
            return True

        txt = "### 🔐 Permisos Permanentes\n\n"
        for tool in allowed:
            txt += f"- `{tool}`\n"
        txt += "\n*Para borrarlos, elimina el archivo `.harness_permissions.json`.*"

        await app.write_to_chat(txt, type="agent")
        return True

    elif cmd == "/export":
        fmt = parts[1].lower() if len(parts) > 1 else "markdown"
        file_path = parts[2] if len(parts) > 2 else None

        from app.core.harness.transcript import render_transcript
        text = render_transcript(ctx.messages, fmt)

        if file_path:
            Path(file_path).write_text(text, encoding="utf-8")
            await app.write_to_chat(f"✅ Exportado a `{file_path}` en formato `{fmt}`.", type="system")
        else:
            await app.write_to_chat(f"```\n{text}\n```", type="agent")
        return True

    else:
        await app.write_to_chat(f"❌ **Comando desconocido:** `{cmd}`\nUsa `/help` para ver la lista.", type="agent")
        return True
