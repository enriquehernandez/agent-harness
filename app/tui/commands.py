import json
import logging
from pathlib import Path

from app.core.config import settings
from app.core.logger import logger
from app.core.harness.context import ContextManager
from app.core.harness.hooks import hook_manager
from app.core.llm.registry import list_providers
from app.core.llm.base import BaseLLM
from app.core.llm import get_llm


# Códigos de respuesta de un solo uso: se inyectan en la siguiente pregunta y
# se consumen automáticamente. Son instrucciones de estilo, no permisos.
MODE_INSTRUCTIONS = {
    "/truth": (
        "Modo TRUTH: sé directo y crítico. Apaga la cortesía, señala fallas y "
        "evita dar la razón cuando los hechos no la respaldan."
    ),
    "/human": (
        "Modo HUMAN: responde con un tono natural y cercano, como una persona "
        "hablando con otra; evita el estilo de manual corporativo."
    ),
    "/nofluff": (
        "Modo NOFLUFF: ve al grano. Omite saludos, rodeos y relleno; entrega "
        "solo lo esencial."
    ),
    "/devil": (
        "Modo DEVIL: actúa como abogado del diablo. Cuestiona la idea y enumera "
        "sus puntos débiles, riesgos y alternativas."
    ),
    "/decode": (
        "Modo DECODE: traduce el lenguaje técnico o legal a lenguaje claro; "
        "explica la letra pequeña y los términos complejos."
    ),
    "/genius": (
        "Modo GENIUS: razona paso a paso y muestra pasos verificables antes de "
        "concluir, especialmente en problemas lógicos, matemáticos o análisis profundo."
    ),
}


def mode_message(command: str) -> str:
    """Texto del mensaje temporal que se inyecta antes de la pregunta."""
    return (
        f"{MODE_INSTRUCTIONS[command]}\n\n"
        "Estas instrucciones son de estilo para esta pregunta: no cambian las "
        "reglas de AGENTS.md ni los permisos."
    )


AVAILABLE_COMMANDS = [
    "/help", "/shortcuts", "/model", "/provider", "/tools", "/subagents",
    "/skills", "/hooks", "/reload", "/tokens", "/compact", "/verbose", "/clear", "/debug",
    "/permissions", "/export", "/session", "/memory", "/doctor", "/trace", "/cost", "/quit",
    *MODE_INSTRUCTIONS,
]


async def handle_command(command: str, ctx: ContextManager, state: dict, llm: BaseLLM, app) -> bool:
    parts = command.strip().split()
    cmd = parts[0].lower()

    if cmd in ("/quit", "/exit"):
        await app.write_to_chat("👋 Saliendo del Harness...", type="system")
        app.exit()
        return True

    elif cmd in MODE_INSTRUCTIONS:
        question = " ".join(parts[1:]).strip()
        app.pending_mode = cmd
        app.pending_question = question or None
        suffix = f" y enviaré `{question}`" if question else ""
        await app.write_to_chat(
            f"🎮 Modo `{cmd}` activado para una sola pregunta{suffix}.", type="system")
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
            "| `/skills` | Lista todas las habilidades (tools + subagents) |\n"
            "| `/hooks [reload]` | Lista los hooks activos y sus errores; `reload` recarga la config |\n"
            "| `/reload [skills/permissions/tools]` | Recarga `skills`, `permissions` o `tools` |\n"
            "| `/tokens` | Muestra el uso estimado de tokens |\n"
            "| `/cost` | 💰 Muestra el coste real (USD) de la última llamada |\n"
            "| `/compact [estrategia]` | Fuerza la compactación (sliding/summarize/none) |\n"
            "| `/verbose [on/off]` | Muestra/oculta los detalles de la compactación |\n"
            "| `/clear` | Limpia el historial de conversación |\n"
            "| `/debug [on/off/clear]` | Controla el panel de debug |\n"
            "| `/permissions` | Gestiona permisos guardados |\n"
            "| `/export [formato]` | Exporta la conversación (markdown/json) |\n"
            "| `/memory [clear/migrate]` | Gestiona la memoria persistente |\n"
            "| `/session [list/load/delete/save/new]` | Gestiona las sesiones guardadas |\n"
            "| `/doctor` | 🩺 Diagnóstico del estado del sistema |\n"
            "| `/trace` | 📊 Muestra el uso de tokens real de la última llamada |\n"
            "| `/quit` | Sale del programa |\n"
            "\n### 🎮 Códigos de respuesta (un solo uso)\n\n"
            "| Código | Efecto |\n"
            "| :--- | :--- |\n"
            "| `/truth` | Sin cortesía; crítica honesta y fallas. |\n"
            "| `/human` | Tono natural y cercano. |\n"
            "| `/nofluff` | Sin saludos, rodeos ni relleno. |\n"
            "| `/devil` | Abogado del diablo; busca puntos débiles. |\n"
            "| `/decode` | Traduce lenguaje técnico o legal. |\n"
            "| `/genius` | Pasos verificables antes de concluir. |\n"
            "Ejemplo: `/devil ¿Qué fallos tiene este plan?`\n"
            "\n### 💡 Skills\n\n"
            "Escribe `@` seguido del nombre de la skill para cargarla automáticamente.\n"
            "Ejemplo: `@improve-codebase-architecture ¿Cómo está mi proyecto?`\n"
            "\n### 💵 Pricing\n\n"
            "El coste se calcula usando `pricing_config.json` y `pricing.json`.\n"
            "Puedes ajustar el TTL de la caché de precios en `.env` con `PRICING_CACHE_TTL_DAYS`.\n"
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
            "| `Enter` | Enviar el mensaje o comando |\n"
        )
        await app.write_to_chat(shortcuts, type="agent")
        return True

    elif cmd == "/doctor":

        txt = "### 🩺 Diagnóstico del Sistema\n\n"
        issues = 0

        # 1. LLM Config
        txt += "#### ⚙️ Configuración del LLM\n"
        if settings.LLM_PROVIDER == "fake":
            txt += "- ⚠️ Usando `FakeLLM` (no hay conexión real a IA).\n"
        else:
            api_key = getattr(
                settings, f"{settings.LLM_PROVIDER.upper()}_API_KEY", "")
            if not api_key or "..." in api_key:
                txt += f"- ❌ Falta `{settings.LLM_PROVIDER.upper()}_API_KEY` válida en .env.\n"
                issues += 1
            else:
                txt += f"- ✅ LLM configurado: `{settings.LLM_PROVIDER}`.\n"

        # 2. MCP Config
        txt += "\n#### 🔌 Servidores MCP\n"
        config_path = Path("mcp_config.json")
        if not config_path.exists():
            txt += "- ⚠️ No existe `mcp_config.json`. El agente no tendrá tools remotas.\n"
        else:
            try:
                config = json.loads(config_path.read_text())
                servers = config.get("mcpServers", {})
                if not servers:
                    txt += "- ⚠️ No hay servidores MCP configurados.\n"
                for name, conf in servers.items():
                    cmd = conf.get("command", "")
                    txt += f"- ✅ `{name}` (`{cmd}`)\n"
            except Exception as e:
                txt += f"- ❌ Error parseando `mcp_config.json`: {e}\n"
                issues += 1

        # 3. Skills
        txt += "\n#### 🧠 Skills\n"
        skills_dir = Path(".agents/skills")
        if not skills_dir.exists():
            txt += "- ⚠️ No existe el directorio `.agents/skills/`.\n"
        else:
            installed = [d.name for d in skills_dir.iterdir() if (
                d / "SKILL.md").exists()]
            if not installed:
                txt += "- ⚠️ No hay skills instaladas.\n"
            else:
                txt += f"- ✅ {len(installed)} skill(s) detectada(s): `{', '.join(installed)}`\n"

        # 4. Memoria
        txt += "\n#### 💾 Memoria\n"
        txt += f"- Backend: `{settings.MEMORY_BACKEND}`\n"

        if settings.MEMORY_BACKEND == "sqlite":
            if not settings.memory_db.exists():
                txt += "- ⚠️ La base de datos SQLite (FTS5) aún no se ha creado.\n"
            else:
                txt += f"- ✅ Base de datos FTS5 en `{settings.memory_db}`.\n"

        elif settings.MEMORY_BACKEND == "vector":
            if not settings.vector_db.exists():
                txt += "- ⚠️ La base de datos vectorial aún no se ha creado (se creará al guardar).\n"
            else:
                txt += f"- ✅ Base de datos vectorial en `{settings.vector_db}`.\n"

        elif settings.MEMORY_BACKEND == "files":
            if not settings.memory_files_dir.exists():
                txt += "- ⚠️ El directorio de archivos de memoria aún no se ha creado.\n"
            else:
                txt += f"- ✅ Archivos de memoria en `{settings.memory_files_dir}`.\n"

        else:
            txt += f"- ✅ Almacenamiento en `{settings.DATA_DIR}`.\n"

        # 5. Sesiones y Permisos
        txt += "\n#### 🔐 Seguridad y Sesiones\n"
        if settings.permissions_file.exists():
            txt += "- ✅ Archivo de permisos persistentes existe.\n"
        else:
            txt += "- ⚠️ No hay permisos guardados (todo pedirá confirmación).\n"

        sessions = app.session_manager.list_sessions(
        ) if hasattr(app, "session_manager") else []
        txt += f"- Sesiones guardadas: `{len(sessions)}`\n"

        # Resultado final
        if issues == 0:
            txt += "\n**✨ Todo en orden. Listo para trabajar.**"
        else:
            txt += f"\n**⚠️ Se encontraron {issues} problema(s) crítico(s).**"

        await app.write_to_chat(txt, type="agent")
        return True

    elif cmd == "/trace":
        usage = getattr(app, "last_usage", None)
        model = getattr(app, "last_model", "Desconocido")

        if not usage:
            await app.write_to_chat("⚠️ No hay datos de uso recientes. Envía un mensaje primero.", type="system")
            return True

        prompt = usage.get("prompt_tokens", 0)
        completion = usage.get("completion_tokens", 0)
        cached = usage.get("prompt_tokens_details", {}).get(
            "cached_tokens", 0) if isinstance(usage.get("prompt_tokens_details"), dict) else 0
        total = usage.get("total_tokens", 0)

        txt = f"### 📊 Traza de la Última Llamada\n\n"
        txt += f"**Modelo:** `{model}`\n\n"
        txt += "| Métrica | Tokens |\n"
        txt += "| :--- | :--- |\n"
        txt += f"| Prompt (Entrada) | `{prompt}` |\n"
        txt += f"| Completion (Salida) | `{completion}` |\n"
        if cached:
            txt += f"| 🎯 Cached (Ahorro) | `{cached}` |\n"
        txt += f"| **Total** | `{total}` |\n\n"

        if cached > 0:
            txt += f"✨ *Prompt Caching activo: {cached} tokens leídos de caché.*\n"
        else:
            txt += "💡 *Consejo: Activa `ENABLE_PROMPT_CACHING=true` en .env para ahorrar costes en prompts largos.*\n"

        await app.write_to_chat(txt, type="agent")
        return True

    elif cmd == "/cost":
        usage = getattr(app, "last_usage", None)
        cost = getattr(app, "last_cost", 0.0)
        total_cost = getattr(app, "total_cost", 0.0)
        model = getattr(app, "last_model", "Desconocido")

        if not usage:
            await app.write_to_chat("⚠️ No hay datos de coste. Envía un mensaje primero.", type="system")
            return True

        # 🔥 Comprobamos si el modelo está en el catálogo de precios
        is_known_model = False
        if app.agent_loop and app.agent_loop.pricing and app.agent_loop.pricing._prices:
            is_known_model = model in app.agent_loop.pricing._prices

        prompt = usage.get("prompt_tokens", 0)
        completion = usage.get("completion_tokens", 0)
        total = usage.get("total_tokens", 0)

        txt = f"### 💰 Coste de la Última Llamada\n\n"
        txt += f"**Modelo:** `{model}`\n\n"

        if not is_known_model:
            txt += "⚠️ **El modelo no se encuentra en el catálogo de precios.**\n"
            txt += "💡 *Verifica que `pricing_config.json` apunta a la API correcta y que el caché se ha generado.*\n\n"

        txt += "| Concepto | Tokens | Coste (USD) |\n"
        txt += "| :--- | :--- | :--- |\n"
        txt += f"| Entrada | `{prompt}` | `${(cost * (prompt / total) if total else 0):.6f}` |\n"
        txt += f"| Salida | `{completion}` | `${(cost * (completion / total) if total else 0):.6f}` |\n"
        txt += f"| **Total** | `{total}` | **`${cost:.6f}`** |\n"

        txt += f"\n**Coste acumulado de la sesión:** `${total_cost:.6f}`\n"

        if is_known_model and cost == 0.0:
            txt += "✨ *Este modelo es **gratuito** en el proveedor actual.*\n"
        elif not is_known_model:
            txt += "❌ *No se pudo calcular el coste (modelo desconocido).*\n"

        await app.write_to_chat(txt, type="agent")
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

    elif cmd == "/skills":
        if not app.registry:
            await app.write_to_chat("❌ El Registry no está inicializado.", type="system")
            return True

        # Tools del registry
        tools = app.registry.names()
        subagents = [name for name in tools if name.startswith("delegate_")]
        regular_tools = [
            name for name in tools if not name.startswith("delegate_")]

        # Skills instaladas en .agents/skills/
        from app.tools.skills import LoadSkillTool
        skill_tool = LoadSkillTool()
        installed_skills = skill_tool.discover_skills()

        txt = "### 🧠 Skills Disponibles\n\n"

        txt += "#### 🛠️ Herramientas Locales\n"
        for name in regular_tools:
            tool = app.registry.get(name)
            origin = "MCP" if "[MCP]" in tool.description else "Local"
            txt += f"- `{name}` ({origin}): {tool.description[:60]}...\n"

        if subagents:
            txt += "\n#### 🤖 Subagentes\n"
            for name in subagents:
                tool = app.registry.get(name)
                txt += f"- `{name}`: {tool.description[:60]}...\n"

        if installed_skills:
            txt += "\n#### 📦 Skills Instaladas (usa `@nombre` para cargarlas)\n"
            for name in installed_skills:
                txt += f"- `@{name}`\n"
        else:
            txt += "\n_No hay skills instaladas en `.agents/skills/`._\n"

        await app.write_to_chat(txt, type="agent")
        return True

    elif cmd == "/hooks":
        target = parts[1].lower() if len(parts) > 1 else None
        if target not in (None, "reload"):
            await app.write_to_chat(
                f"❌ Objetivo desconocido: `{target}`. Uso: `/hooks [reload]`",
                type="system")
            return True

        if target == "reload":
            try:
                hook_manager.reload()
            except Exception as exc:
                logger.warning(f"No se pudieron recargar los hooks: {exc}")
                await app.write_to_chat(
                    f"❌ No se pudieron recargar los hooks: {exc}", type="system")
                return True
            header = "✅ Configuración de hooks recargada.\n\n"
        else:
            header = ""

        await app.write_to_chat(header + hook_manager.describe(), type="agent")
        return True

    elif cmd == "/reload":
        target = parts[1].lower() if len(parts) > 1 else None

        if target == "skills":
            import re
            from app.tools.skills import LoadSkillTool
            from app.tui.suggester import CombinedSuggester

            skills = LoadSkillTool().discover_skills()
            skills_list = ", ".join(
                f"'{s}'" for s in skills) if skills else "ninguna"
            if getattr(app, "ctx", None) and app.ctx.messages:
                current_prompt = app.ctx.messages[0]["content"]
                app.ctx.messages[0]["content"] = re.sub(
                    r"Available skills:.*",
                    f"Available skills: {skills_list}.",
                    current_prompt,
                    count=1,
                    flags=re.MULTILINE,
                )
            app.query_one(
                "#input-box").suggester = CombinedSuggester(AVAILABLE_COMMANDS)
            await app.write_to_chat(
                f"✅ Skills recargadas: {', '.join(skills) or 'ninguna'}", type="system")

        elif target == "permissions":
            app.gate.reload_persisted()
            await app.write_to_chat(
                f"✅ Permisos recargados desde `{settings.permissions_file}`.", type="system")

        elif target == "tools":
            previous_ctx = app.ctx
            for client in reversed(getattr(app, "mcp_clients", [])):
                try:
                    await client.disconnect()
                except Exception:
                    logger.warning(
                        "Error desconectando cliente MCP al recargar tools", exc_info=True)
            app.mcp_clients.clear()
            await app.initialize_agent()
            app.ctx = previous_ctx
            await app.write_to_chat(
                "✅ Herramientas y conexiones MCP recargadas (contexto conservado).", type="system")

        else:
            suffix = f" Objetivo desconocido: `{target}`." if target else ""
            await app.write_to_chat(
                f"❌{suffix} Uso: `/reload [skills|permissions|tools]`", type="system")
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

    elif cmd == "/provider":
        if len(parts) > 1:
            new_provider = parts[1].lower()
            try:
                new_llm = get_llm(new_provider)
                state["provider"] = new_provider
                if app.agent_loop:
                    app.agent_loop.llm = new_llm
                app.update_dashboard("Listo")
                await app.write_to_chat(
                    f"✅ Proveedor cambiado a: **{new_provider}**", type="system"
                )
            except Exception as e:
                await app.write_to_chat(
                    f"❌ Error al cambiar de proveedor: {e}", type="system"
                )
        else:
            current = state.get("provider", "desconocido")
            available = ", ".join(list_providers())
            model_name = getattr(llm, "model_name", getattr(
                llm, "model", "Desconocido"))
            info = (
                f"### ⚙️ Configuración Actual\n\n"
                f"**Proveedor:** `{current.upper()}`\n\n"
                f"**Modelo:** `{model_name}`\n\n"
                f"**Proveedores disponibles:**\n"
                f"`{available}`"
            )
            await app.write_to_chat(info, type="agent")
        return True

    elif cmd == "/model":
        if len(parts) > 1:
            new_model = parts[1]
            provider = state.get("provider", settings.LLM_PROVIDER)
            try:
                new_llm = get_llm(provider, model=new_model)
                state["model"] = new_model
                if app.agent_loop:
                    app.agent_loop.llm = new_llm
                app.update_dashboard("Listo")
                await app.write_to_chat(
                    f"✅ Modelo cambiado a: **{new_model}** (provider: `{provider}`)",
                    type="system",
                )
            except Exception as e:
                await app.write_to_chat(
                    f"❌ Error al cambiar de modelo: {e}", type="system"
                )
        else:
            current = state.get("model", "desconocido")
            provider = state.get("provider", "desconocido")
            await app.write_to_chat(
                f"### ⚙️ Modelo Actual\n\n"
                f"**Modelo:** `{current}`\n\n"
                f"**Proveedor:** `{provider.upper()}`\n\n"
                f"Usa `/model <nombre>` para cambiarlo.",
                type="agent",
            )
        return True

    elif cmd == "/compact":
        strategy_arg = parts[1].lower() if len(parts) > 1 else "summarize"
        if strategy_arg not in ("summarize", "sliding", "none"):
            await app.write_to_chat("❌ Estrategias válidas: `summarize`, `sliding`, `none`.", type="system")
            return True

        # 🔥 Guardar la estrategia actual y restaurarla después (no permanente)
        previous_strategy = ctx.strategy
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
        ctx.strategy = previous_strategy
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
        perm_file = settings.permissions_file
        if not perm_file.exists():
            await app.write_to_chat(
                f"No hay permisos guardados en `{perm_file}`.", type="system")
            return True

        data = json.loads(perm_file.read_text())
        allowed = data.get("session_allowed", [])
        if not isinstance(allowed, list):
            allowed = list(allowed.keys()) if isinstance(allowed, dict) else []

        if not allowed:
            await app.write_to_chat("No hay herramientas con 'Permitir siempre'.", type="system")
            return True

        txt = "### 🔐 Permisos Permanentes\n\n"
        for tool in allowed:
            txt += f"- `{tool}`\n"
        txt += f"\n*Para borrarlos, elimina el archivo `{settings.permissions_file}`.*"

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

    elif cmd == "/memory":
        if len(parts) > 1:
            subcmd = parts[1].lower()
            if subcmd == "clear":
                if getattr(app, "memory_store", None) is not None:
                    await app.memory_store.clear()
                    await app.write_to_chat("🧹 Memoria limpiada.", type="system")
                else:
                    await app.write_to_chat("❌ Store no inicializado.", type="system")
            elif subcmd == "migrate":
                if getattr(app, "memory_store", None) is None:
                    await app.write_to_chat("❌ Store no inicializado.", type="system")
                    return True

                target = parts[2].lower() if len(parts) > 2 else "sqlite"
                from app.core.harness.memory.factory import create_memory_store
                from app.tools.memory import MemorySaveTool, MemoryRecallTool

                new_store = create_memory_store(target)
                old_entries = await app.memory_store.get_all()
                for entry in old_entries:
                    await new_store.save(entry)

                # Cerrar el store viejo si tiene close()
                if hasattr(app.memory_store, "close"):
                    import inspect
                    if inspect.iscoroutinefunction(app.memory_store.close):
                        await app.memory_store.close()
                    else:
                        app.memory_store.close()

                app.memory_store = new_store

                if hasattr(new_store, "close"):
                    import inspect
                    if inspect.iscoroutinefunction(new_store.close):
                        await new_store.close()
                    else:
                        new_store.close()
                elif hasattr(new_store, "commit"):
                    await new_store.commit()

                # Re-registrar tools con el nuevo store
                app.registry.register(MemorySaveTool(store=new_store))
                app.registry.register(MemoryRecallTool(store=new_store))

                if app.agent_loop:
                    app.agent_loop.tools = app.registry

                # 🔥 Actualizar el system prompt del contexto con el nuevo preamble
                if getattr(app, "ctx", None) and app.ctx.messages and app.ctx.messages[0].get("role") == "system":
                    new_preamble = new_store.preamble()
                    if new_preamble:
                        current = app.ctx.messages[0]["content"]
                        # Reemplazar la sección de memoria si existe, o añadirla al final
                        if "[Long-term memory]:" in current:
                            import re
                            current = re.sub(
                                r"\[Long-term memory\]:\n.*?(?=\n\n|\Z)",
                                f"[Long-term memory]:\n{new_preamble}",
                                current,
                                flags=re.DOTALL,
                            )
                        else:
                            current += f"\n\n[Long-term memory]:\n{new_preamble}"
                        app.ctx.messages[0]["content"] = current

                await app.write_to_chat(
                    f"✅ Memoria migrada a `{target}` y herramientas actualizadas.",
                    type="system",
                )
            else:
                await app.write_to_chat("Uso: `/memory clear` o `/memory migrate sqlite`", type="system")
        return True

    elif cmd == "/session":
        if len(parts) > 1:
            subcmd = parts[1].lower()
            if subcmd == "list":
                from app.core.harness.session import SessionManager
                sessions = SessionManager.list_sessions()
                if not sessions:
                    await app.write_to_chat("No hay sesiones guardadas.", type="system")
                    return True

                txt = "### 📁 Sesiones Guardadas\n\n"
                txt += "| ID | Fecha | Mensajes |\n"
                txt += "| :--- | :--- | :--- |\n"
                for s in sessions:
                    txt += f"| `{s['id']}` | {s['timestamp'][:19]} | {s['message_count']} |\n"

                await app.write_to_chat(txt, type="agent")
                return True

            elif subcmd == "load":
                if len(parts) > 2:
                    session_id = parts[2]
                    from app.core.harness.session import (
                        SessionManager, merge_session_history)
                    try:
                        sm = SessionManager(session_id)
                    except ValueError:
                        await app.write_to_chat(
                            f"❌ ID de sesión `{session_id}` no válido.",
                            type="system",
                        )
                        return True
                    messages = sm.load()
                    if messages:
                        app.ctx.messages = merge_session_history(
                            app.ctx.messages, messages)
                        app.session_manager = sm

                        # 🔥 Recargar repair_counts desde los metadatos
                        metadata = sm.load_metadata()
                        repair_counts = metadata.get("repair_counts", {})
                        if repair_counts and getattr(app, "agent_loop", None):
                            app.agent_loop.repair_counts = repair_counts

                        await app.write_to_chat(
                            f"✅ Sesión `{session_id}` cargada ({len(messages)} mensajes, "
                            f"{len(repair_counts)} tools en reparación).",
                            type="system",
                        )
                    else:
                        await app.write_to_chat(
                            f"❌ Sesión `{session_id}` no encontrada.", type="system"
                        )
                else:
                    await app.write_to_chat("Uso: `/session load <id>`", type="system")

            elif subcmd == "delete":
                if len(parts) > 2:
                    session_id = parts[2]
                    from app.core.harness.session import SessionManager
                    if SessionManager.delete_session(session_id):
                        await app.write_to_chat(f"✅ Sesión `{session_id}` eliminada.", type="system")
                    else:
                        await app.write_to_chat(f"❌ Sesión `{session_id}` no encontrada.", type="system")
                else:
                    await app.write_to_chat("Uso: `/session delete <id>`", type="system")

            elif subcmd == "save":
                if getattr(app, "session_manager", None) and app.ctx:
                    # 🔥 Pasamos app.agent_loop
                    file_path = app.session_manager.save(
                        app.ctx, getattr(app, "agent_loop", None))
                    await app.write_to_chat(f"✅ Sesión guardada en `{file_path}`.", type="system")
                else:
                    await app.write_to_chat("❌ No hay sesión activa.", type="system")

            elif subcmd == "new":
                from app.core.harness.session import SessionManager

                # 1. Guardar la sesión actual si existe
                if getattr(app, "session_manager", None) and app.ctx:
                    app.session_manager.save(
                        app.ctx, getattr(app, "agent_loop", None))
                    await app.write_to_chat(
                        "💾 Sesión actual guardada antes de crear la nueva.", type="system"
                    )

                # 2. Crear nueva sesión (nuevo ID y archivo JSON vacío en disco)
                sm = SessionManager.new()
                app.session_manager = sm

                # Limpiar los contadores de reparación del loop para la nueva sesión
                if getattr(app, "agent_loop", None):
                    app.agent_loop.repair_counts = {}

                # 3. Limpiar el contexto preservando el System Prompt
                # (Asumiendo que tu ContextManager guarda el system prompt en messages[0])
                if hasattr(app.ctx, "clear"):
                    # Si tu método clear() ya preserva el system prompt, está perfecto.
                    app.ctx.clear()
                else:
                    # Si no, lo preservamos manualmente:
                    system_prompt = app.ctx.messages[0] if app.ctx.messages and app.ctx.messages[0].get(
                        "role") == "system" else None
                    app.ctx.messages = [system_prompt] if system_prompt else []

                # 4. Limpiar la pantalla del chat (UI)
                if hasattr(app, "query_one"):
                    try:
                        scroll = app.query_one("#chat-scroll")
                        await scroll.remove_children()
                    except Exception:
                        pass  # Por si acaso se llama fuera de la UI

                await app.write_to_chat(
                    f"✅ Nueva sesión creada: `{sm.session_id}`. Contexto limpio.", type="system"
                )
                return True

            else:
                await app.write_to_chat("Uso: `/session [list|load|delete|save] [id]`", type="system")
        else:
            await app.write_to_chat(
                "### 💾 Comandos de Sesión\n\n"
                "- `/session list` → Lista todas las sesiones guardadas\n"
                "- `/session load <id>` → Carga una sesión\n"
                "- `/session delete <id>` → Elimina una sesión\n"
                "- `/session save` → Guarda la sesión actual\n"
                "- `/session new` → Guarda la actual y crea una nueva sesión",
                type="agent"
            )
        return True

    else:
        await app.write_to_chat(f"❌ **Comando desconocido:** `{cmd}`\nUsa `/help` para ver la lista.", type="agent")
        return True
