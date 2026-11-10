import json
import logging
from pathlib import Path

from app.core.logger import logger
from app.core.harness.context import ContextManager
from app.core.llm.registry import list_providers
from app.core.llm.base import BaseLLM
from app.core.llm import get_llm


async def handle_command(command: str, ctx: ContextManager, state: dict, llm: BaseLLM, app) -> bool:
    parts = command.strip().split()
    cmd = parts[0].lower()

    if cmd in ("/quit", "/exit"):
        await app.escribir_en_chat("👋 Saliendo del Harness...", tipo="system")
        app.exit()
        return True

    elif cmd == "/help":
        ayuda = (
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
            "| `/compact [sliding/summarize/none]` | Fuerza la compactación opcionalmente con una estrategia |\n"
            "| `/verbose [on/off]` | Muestra/oculta los detalles de la compactación |\n"
            "| `/clear` | Limpia el historial de conversación |\n"
            "| `/debug [on/off/clear]` | Controla el panel de debug |\n"
            "| `/permissions` | Gestiona permisos guardados |\n"
            "| `/quit` | Sale del programa |\n"
        )
        await app.escribir_en_chat(ayuda, tipo="agent")
        return True

    elif cmd == "/shortcuts" or cmd == "/hotkeys":
        atajos = (
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
        await app.escribir_en_chat(atajos, tipo="agent")
        return True

    elif cmd == "/tools":
        if not app.registry:
            await app.escribir_en_chat("❌ El Registry no está inicializado.", tipo="system")
            return True

        tools = app.registry.names()
        if not tools:
            await app.escribir_en_chat("No hay herramientas registradas.", tipo="system")
            return True

        txt = "### 🧰 Herramientas Disponibles\n\n"
        txt += "| Nombre | Origen |\n"
        txt += "| :--- | :--- |\n"
        for name in tools:
            tool = app.registry.get(name)
            # Detectamos si es MCP por la descripción
            origen = "MCP" if "[MCP]" in tool.description else "Local"
            txt += f"| `{name}` | {origen} |\n"

        await app.escribir_en_chat(txt, tipo="agent")
        return True

    elif cmd == "/subagents":
        if not app.registry:
            await app.escribir_en_chat("❌ El Registry no está inicializado.", tipo="system")
            return True

        # Buscamos los subagentes (aquellos cuyo nombre empiece por delegate_)
        subagents = [name for name in app.registry.names()
                     if name.startswith("delegate_")]

        if not subagents:
            await app.escribir_en_chat("No hay subagentes registrados.", tipo="system")
            return True

        txt = "### 🤖 Subagentes Registrados\n\n"
        txt += "| Nombre | Descripción |\n"
        txt += "| :--- | :--- |\n"
        for name in subagents:
            tool = app.registry.get(name)
            txt += f"| `{name}` | {tool.description[:80]}... |\n"

        await app.escribir_en_chat(txt, tipo="agent")
        return True

    elif cmd == "/tokens":
        tokens = ctx.estimate_tokens()
        limit = llm.max_context_window
        porcentaje = (tokens/limit)*100
        await app.escribir_en_chat(
            f"**Uso de Tokens:**\n"
            f"- Actuales: `{tokens}`\n"
            f"- Límite: `{limit}`\n"
            f"- Porcentaje: `{porcentaje:.1f}%`",
            tipo="agent"
        )
        return True

    elif cmd == "/clear":
        ctx.clear()
        scroll = app.query_one("#chat-scroll")
        await scroll.remove_children()
        await app.escribir_en_chat("🧹 Historial de conversación limpiado.", tipo="system")
        return True

    elif cmd == "/model":
        if len(parts) > 1:
            new_provider = parts[1]
            try:
                new_llm = get_llm(new_provider)
                state["provider"] = new_provider
                if app.loop_agent:
                    app.loop_agent.llm = new_llm
                app.actualizar_dashboard("Listo")
                await app.escribir_en_chat(f"✅ Proveedor cambiado a: **{new_provider}**", tipo="system")
            except Exception as e:
                await app.escribir_en_chat(f"❌ Error al cambiar de modelo: {e}", tipo="system")
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
            await app.escribir_en_chat(info, tipo="agent")
        return True

    elif cmd == "/provider":
        if len(parts) > 1:
            new_provider = parts[1]
            try:
                new_llm = get_llm(new_provider)
                state["provider"] = new_provider
                if app.loop_agent:
                    app.loop_agent.llm = new_llm
                app.actualizar_dashboard("Listo")
                await app.escribir_en_chat(f"✅ Proveedor cambiado a: **{new_provider}**", tipo="system")
            except Exception as e:
                await app.escribir_en_chat(f"❌ Error al cambiar de proveedor: {e}", tipo="system")
        else:
            current = state.get("provider", "desconocido")
            available = ", ".join(list_providers())
            await app.escribir_en_chat(
                f"**Proveedor actual:** `{current.upper()}`\n\n"
                f"**Disponibles:** `{available}`",
                tipo="agent"
            )
        return True

    elif cmd == "/compact":
        strategy_arg = parts[1].lower() if len(parts) > 1 else "summarize"
        if strategy_arg not in ("summarize", "sliding", "none"):
            await app.escribir_en_chat("❌ Estrategias válidas: `summarize`, `sliding`, `none`.", tipo="system")
            return True

        strategy_name = ctx.set_strategy(strategy_arg)
        await app.escribir_en_chat(f"🗜️ **Compactando contexto** (Estrategia: `{strategy_name}`)...", tipo="system")

        old_len = len(ctx.messages)
        old_tokens = ctx.estimate_tokens()

        # 🔥 Obtenemos el resumen si verbose está activo
        verbose = getattr(app, 'verbose_mode', False)
        summary_text = await ctx.force_compact(llm, verbose=verbose)

        new_len = len(ctx.messages)
        new_tokens = ctx.estimate_tokens()

        resumen = (
            f"✅ **Contexto compactado**\n\n"
            f"- Mensajes: `{old_len}` ➡️ `{new_len}`\n"
            f"- Tokens: `{old_tokens}` ➡️ `{new_tokens}`"
        )
        await app.escribir_en_chat(resumen, tipo="agent")

        # 🔥 Si verbose está activo y hay resumen, lo mostramos en el chat
        if verbose and summary_text:
            await app.escribir_en_chat(f"🔊 **Resumen generado:**\n\n```markdown\n{summary_text}\n```", tipo="system")

        return True

    # 🔥 ACTUALIZAR /verbose
    elif cmd == "/verbose":
        if len(parts) > 1:
            subcmd = parts[1].lower()
            if subcmd == "on":
                app.verbose_mode = True
                # Opcional: Aquí podrías cambiar la estrategia a SummarizationStrategy
                # si quieres que el verbose muestre el resumen de la compactación.
                await app.escribir_en_chat("🔊 **Modo verbose ACTIVADO.**", tipo="system")
            elif subcmd == "off":
                app.verbose_mode = False
                await app.escribir_en_chat("🔇 **Modo verbose DESACTIVADO.**", tipo="system")
            else:
                await app.escribir_en_chat("❌ Usa `/verbose on` o `/verbose off`.", tipo="system")
        else:
            estado = "ACTIVADO" if getattr(
                app, 'verbose_mode', False) else "DESACTIVADO"
            await app.escribir_en_chat(f"🔊 **Verbose:** `{estado}`", tipo="system")
        return True

    elif cmd == "/debug":
        if len(parts) > 1:
            subcmd = parts[1].lower()
            if subcmd == "on":
                logger.setLevel(logging.DEBUG)
                app.debug_mode = True
                await app.toggle_debug_panel(True)
                await app.escribir_en_chat("🔔 **Debug ACTIVADO.** Panel abierto.", tipo="system")
            elif subcmd == "off":
                logger.setLevel(logging.INFO)
                app.debug_mode = False
                await app.toggle_debug_panel(False)
                await app.escribir_en_chat("🔕 **Debug DESACTIVADO.** Panel cerrado.", tipo="system")
            elif subcmd == "clear":
                app.clear_debug_events()
                await app.escribir_en_chat("🧹 **Panel de debug limpiado.**", tipo="system")
            else:
                await app.escribir_en_chat(f"❌ Subcomando desconocido: `{subcmd}`. Usa `on`, `off` o `clear`.", tipo="system")
        else:
            estado = "ACTIVADO" if logger.level == logging.DEBUG else "DESACTIVADO"
            await app.escribir_en_chat(f"🪲 **Debug:** `{estado}`\nUsa `/debug on`, `/debug off` o `/debug clear`.", tipo="system")
        return True

    elif cmd == "/permissions":
        perm_file = Path(".harness_permissions.json")
        if not perm_file.exists():
            await app.escribir_en_chat("No hay permisos guardados en `.harness_permissions.json`.", tipo="system")
            return True

        data = json.loads(perm_file.read_text())
        allowed = list(data.get("session_allowed", {}).keys())

        if not allowed:
            await app.escribir_en_chat("No hay herramientas con 'Permitir siempre'.", tipo="system")
            return True

        txt = "### 🔐 Permisos Permanentes\n\n"
        for tool in allowed:
            txt += f"- `{tool}`\n"
        txt += "\n*Para borrarlos, elimina el archivo `.harness_permissions.json`.*"

        await app.escribir_en_chat(txt, tipo="agent")
        return True

    else:
        await app.escribir_en_chat(f"❌ **Comando desconocido:** `{cmd}`\nUsa `/help` para ver la lista.", tipo="agent")
        return True
