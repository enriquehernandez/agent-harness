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

    if cmd == "/quit" or cmd == "/exit":
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
            "| `/tokens` | Muestra el uso estimado de tokens |\n"
            "| `/compact` | Fuerza la compactación del contexto |\n"
            "| `/clear` | Limpia el historial de conversación |\n"
            "| `/debug` | Activa/desactiva los logs detallados |\n"
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
            "| `Enter` | Enviar el mensaje o comando |\n"
        )
        await app.escribir_en_chat(atajos, tipo="agent")
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
        # Limpiamos el contenedor de mensajes
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

    elif cmd == "/compact":
        await app.escribir_en_chat("🗜️ Compactando contexto...", tipo="system")
        old_len = len(ctx.messages)
        old_tokens = ctx.estimate_tokens()

        await ctx.force_compact(llm)

        new_len = len(ctx.messages)
        new_tokens = ctx.estimate_tokens()

        resumen = (
            f"✅ **Contexto compactado**\n\n"
            f"- Mensajes: `{old_len}` ➡️ `{new_len}`\n"
            f"- Tokens: `{old_tokens}` ➡️ `{new_tokens}`"
        )
        await app.escribir_en_chat(resumen, tipo="agent")
        return True

    elif cmd == "/debug":
        current_level = logger.level
        if current_level == logging.DEBUG:
            logger.setLevel(logging.INFO)
            await app.escribir_en_chat("🔕 **Debug DESACTIVADO.**", tipo="system")
        else:
            logger.setLevel(logging.DEBUG)
            await app.escribir_en_chat("🔔 **Debug ACTIVADO.** Verás los logs detallados.", tipo="system")
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
