import os
from textual_image.widget import HalfcellImage
import asyncio
import base64
import json
from pathlib import Path
import shutil
from textual.app import App, ComposeResult
from textual.containers import Vertical, Horizontal, Center, VerticalScroll
from textual.widgets import Input, Static, LoadingIndicator, Markdown, Button, ListView, ListItem, Label, Tree
from textual import events
from app.tui.widgets.rich_message import RichMessage
from textual_image.widget import Image as TerminalImage
from textual import work
from textual.screen import ModalScreen
from textual.suggester import SuggestFromList, Suggester
from rich.syntax import Syntax

from app.core.llm import get_llm
from app.core.harness import AgentLoop, ToolRegistry, ContextManager
from app.core.harness.permissions import Decision, PermissionGate
from app.core.harness.hooks import HookEvent, emit_hook
from app.core.harness.subagents import DelegateTool
from app.core.harness.memory.factory import create_memory_store
from app.core.harness.session import SessionManager
from app.tools import register_core_tools
from app.tui.commands import AVAILABLE_COMMANDS, MODE_INSTRUCTIONS, handle_command, mode_message
from app.mcp.client import MCPClient
from app.core.config import settings
from app.tui.suggester import SkillSuggester, CombinedSuggester
from app.core.logger import logger, get_debug_events
from app.tui.debug_screen import DebugDetailScreen
from app.tui.widgets.file_aware_input import FileAwareInput
from app.tui.modals.permission import PermissionModal

# 🔥 Importamos el Crítico
from app.tools.critic import CriticTool


class AgentHarnessApp(App):
    BINDINGS = [
        ("ctrl+q", "quit", "Salir"),
        ("ctrl+l", "clear_chat", "Limpiar Chat"),
        ("ctrl+u", "clear_input", "Limpiar Input"),
        ("f1", "toggle_debug", "Toggle Debug Panel"),
    ]

    CSS = """
    Screen { background: #0d1117; }
    #header-container { height: 4; align: center middle; background: #161b22; border-bottom: solid #30363d; width: 100%; dock: top; }
    #dashboard { width: auto; height: auto; background: transparent; color: #c9d1d9; text-align: center; }
    #main-content { height: 1fr; }
    #chat-container { width: 1fr; padding: 1 2; }
    #chat-scroll { height: 1fr; background: transparent; border: none; }
    .message-user { background: #161b22; border-left: thick #58a6ff; padding: 1 2; margin-bottom: 1; color: #c9d1d9; }
    .message-agent { background: transparent; padding: 0 2; margin-bottom: 1; }
    .message-system { color: #8b949e; text-style: italic; padding: 1 2; margin-bottom: 1; }
    .message-image { width: 60%; height: auto; margin: 1 2; border: solid #30363d; padding: 1; }
    #loading-indicator { height: 3; display: none; color: #58a6ff; padding: 0 1; }
    #debug-panel { width: 50%; border-left: solid #30363d; background: #161b22; display: none; padding: 1; }
    #debug-header { height: 3; content-align: center middle; text-style: bold; color: #58a6ff; border-bottom: solid #30363d; margin-bottom: 1; }
    #debug-list { height: 1fr; background: transparent; }
    #agent-flow-tree { height: 30%; background: transparent; border-top: solid #30363d; padding: 1; }
    .debug-item { padding: 0 1; }
    .debug-item:hover { background: #21262d; }
    #input-container { dock: bottom; height: 6; padding: 0 2; background: #0d1117; border-top: solid #30363d; align: center middle; }
    #attachments-bar { height: 2; width: 100%; background: #161b22; border-bottom: solid #30363d; padding: 0 1; display: none; color: #58a6ff; text-style: italic; }
    #input-box { width: 100%; height: 3; border: round #30363d; background: #161b22; }
    #input-box:focus { border: round #58a6ff; }
    """

    def __init__(self):
        super().__init__()
        self.state = {"provider": settings.LLM_PROVIDER}
        self.ctx = None
        self.registry = None
        self.gate = None
        self.mcp_clients = []
        self.agent_loop = None
        self.attached_files = []
        self.attached_images = []
        self.debug_mode = False
        self.verbose_mode = False
        self.pending_mode = None
        self.pending_question = None
        self.session_manager = SessionManager()
        self.total_cost = 0.0

    def compose(self) -> ComposeResult:
        with Center(id="header-container"):
            yield Static("📊 Iniciando...", id="dashboard")
        with Horizontal(id="main-content"):
            with Vertical(id="chat-container"):
                with VerticalScroll(id="chat-scroll"):
                    pass
                yield LoadingIndicator(id="loading-indicator")
            with Vertical(id="debug-panel"):
                yield Label("🪲 Panel de Debug", id="debug-header")
                yield ListView(id="debug-list")
                yield Tree("🤖 Flujo de Agentes", id="agent-flow-tree")
        with Vertical(id="input-container"):
            yield Static("", id="attachments-bar")
            yield FileAwareInput(placeholder="Escribe tu mensaje... (Ctrl+U para limpiar)", id="input-box")

    async def on_mount(self) -> None:
        await self.initialize_agent()

        sessions = SessionManager.list_sessions()
        if sessions:
            last_session = sessions[0]
            self.session_manager = SessionManager(last_session["id"])
            messages = self.session_manager.load()
            if messages:
                self.ctx.messages = messages
                metadata = self.session_manager.load_metadata()
                repair_counts = metadata.get("repair_counts", {})
                if repair_counts and self.agent_loop:
                    self.agent_loop.repair_counts = repair_counts
                await self.write_to_chat(f"🔄 Sesión `{last_session['id']}` cargada ({len(messages)} mensajes, {len(repair_counts)} tools en reparación).", type="system")

        await self.write_to_chat("🤖 Agent Harness iniciado. Escribe /help para ver comandos.", type="system")
        await self.write_to_chat("💡 Puedes pegar imágenes o archivos. Escribe @ para cargar una skill.", type="system")

        input_box = self.query_one("#input-box", FileAwareInput)
        input_box.suggester = CombinedSuggester(AVAILABLE_COMMANDS)
        input_box.focus()

    async def initialize_agent(self):
        # 1. Memoria y contexto
        memory_store = create_memory_store(settings.MEMORY_BACKEND)
        self.memory_store = memory_store
        memory_context = f"\n\n[Long-term memory]:\n{memory_store.preamble()}" if memory_store.preamble(
        ) else ""

        from app.tools.skills import LoadSkillTool
        skills = LoadSkillTool().discover_skills()
        skills_list = ", ".join(f"'{s}'" for s in skills) if skills else "ninguna"

        context_files = ["AGENTS.md", "tasks/actual.md"]
        context_text = ""
        for file_path in context_files:
            p = Path(file_path)
            if p.exists():
                context_text += f"\n\n--- START OF {file_path} ---\n{p.read_text(encoding='utf-8')}\n--- END OF {file_path} ---"

        self.ctx = ContextManager(
            system_prompt=(
                "You are an expert AI assistant and Senior Software Engineer working on the Agent Harness.\n"
                "AGENTS.md contains your operational rules: follow them strictly.\n"
                "Everything else below (the task list in tasks/actual.md and long-term memory) "
                "is BACKGROUND CONTEXT for reference, not an instruction to act.\n"
                "Never volunteer, mention or try to resume pending tasks unless the user explicitly "
                "asks about project tasks or status; in that case, answer using tasks/actual.md.\n"
                "Always answer the user's actual message directly.\n"
                f"Available skills: {skills_list}.\n"
                f"{context_text}\n"
                f"{memory_context}"
            )
        )

        # 2. Registry
        self.registry = ToolRegistry()
        register_core_tools(
            self.registry, memory_store=memory_store, mcp_clients=self.mcp_clients)

        from app.tools.memory import MemorySaveTool, MemoryRecallTool
        self.registry.register(MemorySaveTool(store=memory_store))
        self.registry.register(MemoryRecallTool(store=memory_store))

        # 3. MCP
        config_path = Path("mcp_config.json")
        if config_path.exists():
            with open(config_path, "r") as f:
                config = json.load(f)
            for name, server_conf in config.get("mcpServers", {}).items():
                try:
                    client = MCPClient(
                        command=server_conf["command"], args=server_conf["args"], env=server_conf.get("env"))
                    await client.connect()
                    await client.register_tools(self.registry, server_name=name)
                    self.mcp_clients.append(client)
                except Exception as e:
                    await self.write_to_chat(f"❌ Error conectando MCP {name}: {e}", type="system")

        # 4. Permisos
        self.gate = PermissionGate(ask_user=self.request_permission)

        # 5. Subagente Reviewer (Legacy)
        reviewer_tools = ToolRegistry()
        for tool_name in ["read_file", "bash"]:
            if tool_name in self.registry:
                reviewer_tools.register(self.registry.get(tool_name))

        reviewer_tool = DelegateTool(
            name="delegate_to_reviewer",
            description="Delega una tarea de revisión de código.",
            llm=get_llm(self.state["provider"]),
            tools=reviewer_tools,
            system_prompt="You are an expert code reviewer. Be concise.",
            permissions=self.gate,
        )
        self.registry.register(reviewer_tool)

        # 6. A2A
        from app.core.harness.a2a import AgentCard, OrchestratorTool
        a2a_base_tools = ToolRegistry()
        for tool_name in ["read_file", "bash"]:
            if tool_name in self.registry:
                a2a_base_tools.register(self.registry.get(tool_name))

        a2a_agents = {
            "analyst": AgentCard(
                name="analyst", description="Analiza código y datos.",
                system_prompt="Eres un analista experto. Termina con 'HANDOFF: writer'.",
                tools=a2a_base_tools, mode="isolated", model=settings.A2A_ANALYST_MODEL or None,
            ),
            "writer": AgentCard(
                name="writer", description="Escribe documentación.",
                system_prompt="Eres un escritor técnico.",
                tools=a2a_base_tools, mode="fork", model=settings.A2A_WRITER_MODEL or None,
            ),
            "reviewer": AgentCard(
                name="reviewer", description="Revisa el trabajo.",
                system_prompt="Eres un revisor estricto.",
                tools=a2a_base_tools, mode="isolated", model=settings.A2A_REVIEWER_MODEL or None,
            ),
        }

        orchestrator = OrchestratorTool(
            llm=get_llm(self.state["provider"]),
            agents=a2a_agents,
            permissions=self.gate,
            context_provider=lambda: self.ctx,
        )
        self.registry.register(orchestrator)

        # 🔥 7. CONFIGURACIÓN DEL CRÍTICO (Auto-Reflexión)
        # Usamos el modelo definido para el Reviewer en el .env (ej. nemotron o claude)
        critic_model_name = settings.A2A_REVIEWER_MODEL or None
        critic_llm = get_llm(self.state["provider"], model=critic_model_name)
        self.critic_tool = CriticTool(llm=critic_llm)

        # 8. AgentLoop
        self.agent_loop = AgentLoop(
            llm=get_llm(self.state["provider"]),
            tools=self.registry,
            permissions=self.gate,
            provider_name=self.state["provider"],
            critic_tool=self.critic_tool,  # 🔥 Le pasamos el crítico
            agent_rules=context_text,  # 🔥 Pasamos las reglas desde el arranque
        )

        self.update_dashboard("Listo")

    def update_dashboard(self, status: str, tokens: int = 0, last_tool: str = "Ninguna"):
        dash = self.query_one("#dashboard", Static)
        color = "green" if status == "Listo" else "yellow" if status == "Pensando..." else "red"
        model_name = "Desconocido"
        if self.agent_loop and self.agent_loop.llm:
            model_name = getattr(self.agent_loop.llm, 'model_name', getattr(
                self.agent_loop.llm, 'model', 'Desconocido'))
        cost_display = f"${self.total_cost:.4f}" if self.total_cost > 0 else "$0.0000"
        dash.update(
            f"⚡ [bold]{self.state['provider']}[/] ({model_name})  •  "
            f"Estado: [bold {color}]{status}[/]  •  "
            f"Tokens: {tokens}  •  "
            f"Coste total: [bold]{cost_display}[/]"
        )

    async def write_to_chat(self, text: str, type: str = "agent"):
        try:
            scroll = self.query_one("#chat-scroll", VerticalScroll)
            if type == "user":
                widget = Static(
                    f"👤 **Tú:**\n{text}", classes="message-user", markup=True)
            elif type == "system":
                widget = Static(text, classes="message-system", markup=True)
            else:
                widget = RichMessage(text, classes="message-agent")
            await scroll.mount(widget)
            scroll.scroll_end(animate=False)
        except Exception:
            pass

    def update_attachments_bar(self):
        bar = self.query_one("#attachments-bar", Static)
        items = [f"📎 {Path(f).name}" for f in self.attached_files] + \
            ["🖼️ Imagen" for _ in self.attached_images]
        if items:
            bar.update(" | ".join(items) +
                       "  [dim](Ctrl+U para limpiar)[/dim]")
            bar.display = True
        else:
            bar.update("")
            bar.display = False

    async def handle_file_paste(self, path: str):
        p = Path(path)
        if p.suffix.lower() in [".png", ".jpg", ".jpeg", ".gif", ".webp"]:
            try:
                scroll = self.query_one("#chat-scroll", VerticalScroll)
                img_widget = HalfcellImage(p, classes="message-image") if os.environ.get(
                    "TERM_PROGRAM") == "WarpTerminal" else TerminalImage(p, classes="message-image")
                await scroll.mount(img_widget)
                scroll.scroll_end(animate=False)
            except Exception as e:
                logger.warning(f"No se pudo renderizar la imagen: {e}")
                await self.write_to_chat(f"🖼️ **Imagen adjunta:** `{p.name}` (vista previa no disponible)", type="system")

            with open(p, "rb") as f:
                img_data = base64.b64encode(f.read()).decode("utf-8")
            mime = "image/png" if p.suffix.lower() == ".png" else "image/jpeg"
            self.attached_images.append(f"data:{mime};base64,{img_data}")
        else:
            if str(p) not in self.attached_files:
                self.attached_files.append(str(p))
                await self.write_to_chat(f"📎 **Archivo adjunto:** `{p.name}`", type="system")
        self.update_attachments_bar()

    async def _expand_skills(self, user_input: str) -> str:
        import re
        from app.tools.skills import LoadSkillTool
        matches = re.findall(r'@([\w\-]+)', user_input)
        if not matches:
            return user_input
        skill_tool = LoadSkillTool()
        skills_context = ""
        for skill_name in matches:
            result = await skill_tool.run(skill_name)
            if result.success:
                skills_context += f"\n\n[SKILL CARGADA: {skill_name}]\n{result.content}\n[/SKILL]"
                await self.write_to_chat(f"📖 Skill `{skill_name}` cargada automáticamente.", type="system")
            else:
                await self.write_to_chat(f"❌ No se pudo cargar la skill `{skill_name}`: {result.error}", type="system")
        clean_input = re.sub(r'@[\w\-]+', '', user_input).strip()
        return f"{clean_input}\n\n{skills_context}"

    async def request_permission(self, tool_name: str, signature: str, args: dict, diff_text: str | None = None) -> str:
        args_str = ""
        for k, v in args.items():
            if k in ("content", "edits") and diff_text:
                continue
            if isinstance(v, str) and "\n" in v:
                args_str += f"```bash\n{v}\n```\n"
            else:
                args_str += f"- `{k}`: {v}\n"

        if diff_text:
            lines = diff_text.split("\n")
            if len(lines) > 50:
                diff_text = "\n".join(
                    lines[:50]) + f"\n\n... [TRUNCADO: {len(lines) - 50} líneas más] ..."

        try:
            result = await asyncio.wait_for(
                self.push_screen_wait(PermissionModal(
                    tool_name, args_str, diff_text)),
                timeout=settings.LLM_STREAM_TIMEOUT
            )
        except asyncio.TimeoutError:
            result = "n"

        if result == "y":
            await self.write_to_chat(f"✅ Permiso **concedido** para ejecutar: `{signature}`", type="system")
        elif result == "a":
            await self.write_to_chat(f"✅ Permiso **concedido permanentemente** para ejecutar: `{signature}`", type="system")
        else:
            await self.write_to_chat(f"❌ Permiso **denegado** para ejecutar: `{signature}`", type="system")

        self.query_one("#input-box", FileAwareInput).focus()
        return result

    async def action_toggle_debug(self) -> None:
        self.debug_mode = not self.debug_mode
        panel = self.query_one("#debug-panel")
        if self.debug_mode:
            panel.display = True
            await self._refresh_debug_list()
            self.query_one("#debug-list", ListView).focus()
        else:
            panel.display = False
            self.query_one("#input-box", FileAwareInput).focus()

    async def toggle_debug_panel(self, show: bool) -> None:
        panel = self.query_one("#debug-panel")
        if show:
            panel.display = True
            await self._refresh_debug_list()
        else:
            panel.display = False
            self.query_one("#input-box", FileAwareInput).focus()

    def clear_debug_events(self) -> None:
        from app.core.logger import debug_collector
        debug_collector.events.clear()
        if self.debug_mode:
            asyncio.create_task(self._refresh_debug_list())

    async def _refresh_debug_list(self):
        list_view = self.query_one("#debug-list", ListView)
        await list_view.clear()
        events = get_debug_events()
        if not events:
            list_view.append(ListItem(Label("No hay eventos aún.")))
        else:
            for idx, log in enumerate(events):
                summary = f"#{idx+1} {log['timestamp']} • {log['type']} • {log['summary'][:50]}..."
                list_view.append(ListItem(Label(summary), id=f"log-{idx}"))

        from app.core.logger import get_agent_flow
        tree = self.query_one("#agent-flow-tree", Tree)
        tree.clear()
        flow = get_agent_flow()
        if not flow:
            tree.root.add("No hay actividad de agentes aún.")
            return
        root = tree.root
        agent_nodes = {}
        for entry in flow:
            agent = entry["agent"]
            action = entry["action"]
            timestamp = entry["timestamp"]
            if agent not in agent_nodes:
                agent_nodes[agent] = root.add(f"🤖 {agent}")
            if action == "start":
                agent_nodes[agent].add(f"▶️ start ({timestamp})")
            elif action == "end":
                agent_nodes[agent].add(f"✅ end ({timestamp})")
            elif action == "handoff":
                agent_nodes[agent].add(f"🔄 handoff ({timestamp})")
            else:
                agent_nodes[agent].add(f"❓ {action} ({timestamp})")
        tree.root.expand()
        for node in agent_nodes.values():
            node.expand()

    async def on_list_view_selected(self, event: ListView.Selected) -> None:
        if not event.item.id or not event.item.id.startswith("log-"):
            return
        idx = int(event.item.id.split("-")[1])
        events = get_debug_events()
        if idx < len(events):
            log = events[idx]
            await self.push_screen(DebugDetailScreen(title=log['summary'], payload=log['payload']))

    def _begin_pending_mode(self) -> dict | None:
        """Inyecta el código temporal y devuelve el mensaje a retirar después."""
        mode = getattr(self, "pending_mode", None)
        self.pending_mode = None
        instruction = MODE_INSTRUCTIONS.get(mode) if mode else None
        if not instruction or self.ctx is None:
            return None
        temp_msg = {"role": "user", "content": mode_message(mode)}
        self.ctx.messages.append(temp_msg)
        return temp_msg

    def _end_pending_mode(self, temp_msg: dict | None) -> None:
        """Retira el mensaje temporal para que no quede en el historial."""
        if temp_msg is None:
            return
        for index, message in enumerate(self.ctx.messages):
            if message is temp_msg:
                del self.ctx.messages[index]
                break

    @work(exclusive=True)
    async def process_input(self, user_input: str):
        loading = self.query_one("#loading-indicator", LoadingIndicator)
        if user_input.startswith("/"):
            await self.write_to_chat(f"⚙️ Ejecutando comando: {user_input}", type="system")
            try:
                await handle_command(user_input, self.ctx, self.state, get_llm(self.state["provider"]), self)
                inline_question = getattr(self, "pending_question", None)
                if inline_question:
                    self.pending_question = None
                    await self._stream_user_message(inline_question, loading)
            except Exception as e:
                await self.write_to_chat(f"❌ Error en comando: {e}", type="system")
            return

        await self._stream_user_message(user_input, loading)

    async def _stream_user_message(self, user_input: str, loading: LoadingIndicator) -> None:
        # Mostramos primero el mensaje y el indicador: los hooks pueden llamar
        # a un LLM y no deben retrasar la respuesta visual de la TUI.
        self.update_dashboard("Pensando...")
        display_text = user_input if len(
            user_input) < 300 else user_input[:300] + "..."
        await self.write_to_chat(display_text, type="user")
        loading.display = True
        await emit_hook(HookEvent(
            hook_event_name="UserPromptSubmit", prompt=user_input,
            session_id=str(getattr(self.session_manager, "session_id", "") or ""),
        ), parallel=True)
        temp_msg = self._begin_pending_mode()

        try:
            stream_gen = self.agent_loop.stream(
                user_input,
                context=self.ctx,
                verbose=getattr(self, 'verbose_mode', False),
                timeout_seconds=settings.LLM_STREAM_TIMEOUT
            )
            await self.stream_to_chat(stream_gen)
        except Exception as e:
            self.update_dashboard("Error")
            await self.write_to_chat(f"❌ **Error inesperado:** {e}", type="system")
            logger.error(f"Error en process_input: {e}", exc_info=True)
        finally:
            loading.display = False
            self.query_one("#input-box", FileAwareInput).focus()
            self._end_pending_mode(temp_msg)
            if self.debug_mode:
                await self._refresh_debug_list()

    async def stream_to_chat(self, stream_generator):
        scroll = self.query_one("#chat-scroll", VerticalScroll)
        markdown_widget = None
        loading = self.query_one("#loading-indicator", LoadingIndicator)
        full_text = ""
        TIMEOUT_SECONDS = settings.LLM_STREAM_TIMEOUT
        is_correction = False  # 🔥 Flag para detectar correcciones
        stream_iterator = stream_generator.__aiter__()

        try:
            while True:
                # 🔥 Timeout real sin crear un Task nuevo por evento:
                # `wait_for` envuelve `__anext__()` en su propio Task, por lo que
                # el contexto de OTel/Langfuse abierto en un `anext` se intentaba
                # liberar en otro -> "Failed to detach context".
                # `asyncio.timeout` cancela el Task actual y preserva el Context.
                try:
                    async with asyncio.timeout(TIMEOUT_SECONDS):
                        event = await stream_iterator.__anext__()
                except StopAsyncIteration:
                    break

                if event.type == "text_chunk":
                    text = event.data["text"]

                    # 🔥 Detección de corrección por marcador de control (no por texto)
                    if event.data.get("is_correction_marker"):
                        is_correction = True
                        continue

                    if is_correction and markdown_widget:
                        await markdown_widget.remove()
                        markdown_widget = None
                        full_text = ""
                        is_correction = False

                    full_text += event.data["text"]
                    if markdown_widget is None:
                        markdown_widget = Markdown(
                            full_text, classes="message-agent")
                        await scroll.mount(markdown_widget)
                        loading.display = False
                    else:
                        await markdown_widget.update(full_text)
                    scroll.scroll_end(animate=False)

                elif event.type == "result":
                    final_result = event.data
                    tokens = (final_result.get("usage_total")
                              or {}).get("total_tokens", 0)
                    cost = final_result.get("cost_usd", 0.0)

                    self.total_cost += cost
                    self.last_cost = cost
                    self.last_usage = final_result.get("usage_total", {})

                    if self.agent_loop and self.agent_loop.llm:
                        self.last_model = getattr(
                            self.agent_loop.llm, 'model_name', 'Desconocido')

                    if tokens == 0:
                        tokens = len(full_text) // 4
                    self.update_dashboard("Listo", tokens=tokens)
                    break

                elif event.type == "hook_denied":
                    msg = event.data.get("message") or "Acción bloqueada por un hook."
                    await self.write_to_chat(
                        f"🚫 **Bloqueado por un hook:** {msg}", type="system")

                elif event.type == "error":
                    self.update_dashboard("Error")
                    loading.display = False
                    msg = event.data.get("message", "Error desconocido")
                    await self.write_to_chat(f"❌ **Error del Agente:** {msg}", type="system")
                    break

        except asyncio.TimeoutError:
            self.update_dashboard("Error")
            loading.display = False
            await self.write_to_chat("⏳ **Timeout:** El agente tardó demasiado.", type="system")
        except Exception as e:
            self.update_dashboard("Error")
            loading.display = False
            await self.write_to_chat(f"❌ **Error inesperado en la TUI:** {e}", type="system")
        finally:
            loading.display = False

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        user_text = event.value.strip()
        if not user_text and not self.attached_files and not self.attached_images:
            return

        event.input.value = ""
        user_text = await self._expand_skills(user_text)

        if self.attached_images:
            display_text = user_text if user_text else "[Imagen adjunta]"
            await self.write_to_chat(display_text, type="user")
            temp_msg = self._begin_pending_mode()
            self.ctx.add_user_with_image(user_text, self.attached_images)
            self.attached_images = []
            self.update_attachments_bar()
            self.update_dashboard("Pensando...")
            loading = self.query_one("#loading-indicator", LoadingIndicator)
            loading.display = True
            await emit_hook(HookEvent(
                hook_event_name="UserPromptSubmit", prompt=user_text,
                session_id=str(getattr(self.session_manager, "session_id", "") or ""),
            ), parallel=True)
            try:
                stream_gen = self.agent_loop.stream("", context=self.ctx, verbose=getattr(
                    self, 'verbose_mode', False), timeout_seconds=settings.LLM_STREAM_TIMEOUT)
                await self.stream_to_chat(stream_gen)
                self.update_dashboard("Listo")
            except Exception as e:
                await self.write_to_chat(f"❌ **Error:** {e}", type="system")
            finally:
                loading.display = False
                self.query_one("#input-box", FileAwareInput).focus()
                self._end_pending_mode(temp_msg)
            return

        final_message = user_text
        if self.attached_files:
            files_str = ", ".join([f"`{f}`" for f in self.attached_files])
            if user_text:
                final_message = f"{user_text}\n\n[Archivos adjuntos para revisar: {files_str}]"
            else:
                final_message = f"[Por favor, revisa estos archivos: {files_str}]"
            self.attached_files = []
            self.update_attachments_bar()

        self.process_input(final_message)

    async def action_clear_chat(self) -> None:
        if self.ctx:
            self.ctx.clear()
        scroll = self.query_one("#chat-scroll", VerticalScroll)
        await scroll.remove_children()
        await self.write_to_chat("🧹 Chat limpiado (Ctrl+L)", type="system")

    def action_clear_input(self) -> None:
        input_box = self.query_one("#input-box", FileAwareInput)
        input_box.value = ""
        input_box.focus()
        self.attached_files = []
        self.attached_images = []
        self.update_attachments_bar()

    async def on_unmount(self) -> None:
        if self.ctx:
            self.session_manager.save(self.ctx, self.agent_loop)
        for client in reversed(self.mcp_clients):
            try:
                await client.disconnect()
            except:
                pass


def run_tui():
    app = AgentHarnessApp()
    app.run()


if __name__ == "__main__":
    run_tui()
