import asyncio
import base64
import json
from pathlib import Path
from textual.app import App, ComposeResult
from textual.containers import Vertical, Horizontal, Center, VerticalScroll
from textual.widgets import Input, Static, LoadingIndicator, Markdown, Button, ListView, ListItem, Label
from textual import work
from textual.screen import ModalScreen
from textual.suggester import SuggestFromList
from rich.syntax import Syntax

from app.core.llm import get_llm
from app.core.harness import AgentLoop, ToolRegistry, ContextManager
from app.core.harness.permissions import PermissionGate
from app.core.harness.subagents import DelegateTool
from app.tools import register_core_tools
from app.tui.commands import handle_command
from app.mcp.client import MCPClient
from app.core.config import settings
from app.core.logger import logger, get_debug_events
from app.tools.memory import SUMMARY_FILE
from app.tui.debug_screen import DebugDetailScreen

# ==========================================
# INPUT PERSONALIZADO (INTERCEPTA ARCHIVOS)
# ==========================================


class FileAwareInput(Input):
    """Input que detecta si el texto es una ruta de archivo y lo intercepta."""

    async def _on_paste(self, event) -> None:
        text = event.text.strip().strip("'\"")
        clean_path = text.replace(
            "file://", "") if text.startswith("file://") else text

        try:
            p = Path(clean_path).expanduser()
            if p.exists() and p.is_file():
                # 🔥 Es un archivo: lo procesamos y NO lo escribimos en el input
                await self.app.handle_file_paste(str(p))
                event.prevent_default()
                event.stop()
                return
        except Exception:
            pass

        # Si no es un archivo, dejamos que el Input lo maneje normalmente
        await super()._on_paste(event)  # pragma: no cover

    def watch_value(self, value: str) -> None:
        """Watcher: si el texto se cuela, lo limpiamos."""
        if value and value.startswith("/") and " " not in value.strip():
            # Si parece una ruta de archivo (empieza con / y no tiene espacios)
            p = Path(value.strip().strip("'\""))
            if p.exists() and p.is_file():
                # 🔥 Es un archivo: lo borramos del input y lo procesamos
                self.value = ""
                self.app.call_later(self.app.handle_file_paste, str(p))
                return

# ==========================================
# PERMISSION MODAL
# ==========================================


class PermissionModal(ModalScreen[str]):
    CSS = """
    PermissionModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.7);
    }
    #dialog {
        width: 80;
        height: auto;
        max-height: 30;
        border: round $accent;
        background: $surface;
        padding: 1 2;
    }
    #message {
        height: auto;
        width: 100%;
        padding: 0 0 1 0;
    }
    #buttons {
        height: auto;
        width: 100%;
        align: center middle;
    }
    Button {
        width: 1fr;
        margin: 0 1;
    }
    """

    def __init__(self, tool_name: str, args_str: str, diff_text: str | None = None):
        super().__init__()
        self.tool_name = tool_name
        self.args_str = args_str
        self.diff_text = diff_text

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            msg = f"🛠️ [bold yellow]El agente quiere usar:[/] [bold]{self.tool_name}[/]\n\n"
            if self.args_str.strip():
                msg += f"[dim]Argumentos:[/]\n{self.args_str}"
            else:
                msg += "[dim]Esta herramienta no requiere argumentos.[/]"

            if self.diff_text:
                msg += f"\n\n[dim]Propuesta de cambios:[/]\n{self.diff_text}"

            yield Static(msg, id="message", markup=True)

            with Horizontal(id="buttons"):
                yield Button("Permitir (y)", id="allow", variant="success")
                yield Button("Siempre (a)", id="always", variant="primary")
                yield Button("Denegar (n)", id="deny", variant="error")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "allow":
            self.dismiss("y")
        elif event.button.id == "always":
            self.dismiss("a")
        else:
            self.dismiss("n")

    def on_key(self, event) -> None:
        key = event.key.lower()
        if key == "y":
            self.dismiss("y")
            event.prevent_default()
        elif key == "a":
            self.dismiss("a")
            event.prevent_default()
        elif key in ("n", "escape"):
            self.dismiss("n")
            event.prevent_default()

# ==========================================
# MAIN APP
# ==========================================


class AgentHarnessApp(App):
    BINDINGS = [
        ("ctrl+q", "quit", "Salir"),
        ("ctrl+l", "clear_chat", "Limpiar Chat"),
        ("ctrl+u", "clear_input", "Limpiar Input"),
        ("f1", "toggle_debug", "Toggle Debug Panel"),
    ]

    CSS = """
    Screen {
        background: #0d1117;
    }
    
    #header-container {
        height: 4;
        align: center middle; 
        background: #161b22;
        border-bottom: solid #30363d;
        width: 100%;
        dock: top;
    }
    #dashboard {
        width: auto;
        height: auto;
        background: transparent;
        color: #c9d1d9;
        text-align: center;
    }

    #main-content {
        height: 1fr;
    }

    #chat-container {
        width: 1fr;
        padding: 1 2;
    }
    #chat-scroll {
        height: 1fr;
        background: transparent;
        border: none;
    }
    
    .message-user {
        background: #161b22;
        border-left: thick #58a6ff;
        padding: 1 2;
        margin-bottom: 1;
        color: #c9d1d9;
    }
    
    .message-agent {
        background: transparent;
        padding: 0 2;
        margin-bottom: 1;
    }
    
    .message-system {
        color: #8b949e;
        text-style: italic;
        padding: 1 2;
        margin-bottom: 1;
    }

    #loading-indicator {
        height: 3;
        display: none;
        color: #58a6ff;
        padding: 0 1;
    }

    #debug-panel {
        width: 50%;
        border-left: solid #30363d;
        background: #161b22;
        display: none;
        padding: 1;
    }
    
    #debug-header {
        height: 3;
        content-align: center middle;
        text-style: bold;
        color: #58a6ff;
        border-bottom: solid #30363d;
        margin-bottom: 1;
    }

    #debug-list {
        height: 1fr;
        background: transparent;
    }

    .debug-item {
        padding: 0 1;
    }
    .debug-item:hover {
        background: #21262d;
    }

    #input-container {
        dock: bottom; 
        height: 6; 
        padding: 0 2; 
        background: #0d1117;
        border-top: solid #30363d;
        align: center middle; 
    }

    #attachments-bar {
        height: 2;
        width: 100%;
        background: #161b22;
        border-bottom: solid #30363d;
        padding: 0 1;
        display: none;
        color: #58a6ff;
        text-style: italic;
    }

    #input-box {
        width: 100%;
        height: 3;
        border: round #30363d;
        background: #161b22;
    }
    
    #input-box:focus {
        border: round #58a6ff;
    }
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

        with Vertical(id="input-container"):
            yield Static("", id="attachments-bar")
            # 🔥 Usamos nuestro Input personalizado
            yield FileAwareInput(placeholder="Escribe tu mensaje... (Ctrl+U para limpiar)", id="input-box")

    async def on_mount(self) -> None:
        await self.initialize_agent()
        await self.write_to_chat("🤖 Agent Harness iniciado. Escribe /help para ver comandos.", type="system")
        await self.write_to_chat("💡 Puedes pegar imágenes o archivos. Se mostrarán en la barra de adjuntos.", type="system")

        available_commands = [
            "/help", "/shortcuts", "/model", "/provider", "/tools", "/subagents",
            "/tokens", "/compact", "/verbose", "/clear", "/debug", "/permissions", "/export", "/quit"
        ]

        input_box = self.query_one("#input-box", FileAwareInput)
        input_box.suggester = SuggestFromList(
            available_commands, case_sensitive=False)
        input_box.focus()

    async def initialize_agent(self):
        memory_context = ""
        if SUMMARY_FILE.exists():
            content = SUMMARY_FILE.read_text(encoding="utf-8").strip()
            if content:
                memory_context = f"\n\n[Long-term memory]:\n{content}"

        self.ctx = ContextManager(
            system_prompt=(
                "You are a helpful assistant. You have access to local and remote tools (MCP). "
                "Answer concisely. Use 'write_file' or 'edit_file' to modify files. "
                "To review code, use 'delegate_to_reviewer'. To remember things, use 'memory_save'. "
                "If the user provides an image, describe it or use it as context."
                f"{memory_context}"
            )
        )

        self.registry = ToolRegistry()
        register_core_tools(self.registry)

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

        reviewer_tools = ToolRegistry()
        for tool_name in ["read_text_file", "list_directory", "bash"]:
            if tool_name in self.registry:
                reviewer_tools.register(self.registry.get(tool_name))

        reviewer_tool = DelegateTool(
            name="delegate_to_reviewer", description="Delega una tarea de revisión de código.",
            llm=get_llm(self.state["provider"]), tools=reviewer_tools,
            system_prompt="You are an expert code reviewer. Be concise."
        )
        self.registry.register(reviewer_tool)

        self.gate = PermissionGate(ask_user=self.request_permission)
        self.agent_loop = AgentLoop(llm=get_llm(
            self.state["provider"]), tools=self.registry, permissions=self.gate)

        self.update_dashboard("Listo")

    def update_dashboard(self, status: str, tokens: int = 0, last_tool: str = "Ninguna"):
        dash = self.query_one("#dashboard", Static)
        color = "green" if status == "Listo" else "yellow" if status == "Pensando..." else "red"

        model_name = "Desconocido"
        if self.agent_loop and self.agent_loop.llm:
            model_name = getattr(self.agent_loop.llm, 'model_name', getattr(
                self.agent_loop.llm, 'model', 'Desconocido'))

        dash.update(
            f"⚡ [bold]{self.state['provider']}[/] ({model_name})  •  "
            f"Estado: [bold {color}]{status}[/]  •  "
            f"Tokens: {tokens}  •  Última tool: {last_tool}"
        )

    async def write_to_chat(self, text: str, type: str = "agent"):
        try:
            scroll = self.query_one("#chat-scroll", VerticalScroll)
            if type == "user":
                widget = Static(f"👤 **Tú:**\n{text}",
                                classes="message-user", markup=True)
            elif type == "system":
                widget = Static(text, classes="message-system", markup=True)
            else:
                widget = Markdown(text, classes="message-agent")

            await scroll.mount(widget)
            scroll.scroll_end(animate=False)
        except Exception:
            pass

    def update_attachments_bar(self):
        bar = self.query_one("#attachments-bar", Static)
        items = []
        for f in self.attached_files:
            items.append(f"📎 {Path(f).name}")
        for _ in self.attached_images:
            items.append("🖼️ Imagen")

        if items:
            bar.update(" | ".join(items) +
                       "  [dim](Ctrl+U para limpiar)[/dim]")
            bar.display = True
        else:
            bar.update("")
            bar.display = False

    async def handle_file_paste(self, path: str):
        """Procesa el archivo pegado."""
        p = Path(path)

        if p.suffix.lower() in [".png", ".jpg", ".jpeg", ".gif", ".webp"]:
            with open(p, "rb") as f:
                img_data = base64.b64encode(f.read()).decode("utf-8")

            mime = "image/jpeg"
            if p.suffix.lower() == ".png":
                mime = "image/png"
            elif p.suffix.lower() == ".gif":
                mime = "image/gif"
            elif p.suffix.lower() == ".webp":
                mime = "image/webp"

            b64_url = f"data:{mime};base64,{img_data}"
            self.attached_images.append(b64_url)
            await self.write_to_chat(f"🖼️ **Imagen adjunta:** `{p.name}`", type="system")
        else:
            if str(p) not in self.attached_files:
                self.attached_files.append(str(p))
                await self.write_to_chat(f"📎 **Archivo adjunto:** `{p.name}`", type="system")

        self.update_attachments_bar()

    async def request_permission(self, tool_name: str, signature: str, args: dict, diff_text: str | None = None) -> str:
        args_str = ""
        for k, v in args.items():
            if k in ("content", "edits") and diff_text:
                continue
            if isinstance(v, str) and "\n" in v:
                args_str += f"```bash\n{v}\n```\n"
            else:
                args_str += f"- `{k}`: {v}\n"

        self.query_one("#loading-indicator", LoadingIndicator).display = False

        try:
            result = await asyncio.wait_for(
                self.push_screen_wait(PermissionModal(
                    tool_name, args_str, diff_text)),
                timeout=300.0
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
            return

        for idx, log in enumerate(events):
            summary = f"#{idx+1} {log['timestamp']} • {log['type']} • {log['summary'][:50]}..."
            list_view.append(ListItem(Label(summary), id=f"log-{idx}"))

    async def on_list_view_selected(self, event: ListView.Selected) -> None:
        if not event.item.id or not event.item.id.startswith("log-"):
            return

        idx = int(event.item.id.split("-")[1])
        events = get_debug_events()
        if idx < len(events):
            log = events[idx]
            await self.push_screen(DebugDetailScreen(title=log['summary'], payload=log['payload']))

    @work(exclusive=True)
    async def process_input(self, user_input: str):
        loading = self.query_one("#loading-indicator", LoadingIndicator)

        if user_input.startswith("/"):
            await self.write_to_chat(f"⚙️ Ejecutando comando: {user_input}", type="system")
            try:
                await handle_command(user_input, self.ctx, self.state, get_llm(self.state["provider"]), self)
            except Exception as e:
                await self.write_to_chat(f"❌ Error en comando: {e}", type="system")
            return

        self.update_dashboard("Pensando...")
        display_text = user_input if len(
            user_input) < 300 else user_input[:300] + "..."
        await self.write_to_chat(display_text, type="user")
        loading.display = True

        try:
            stream_gen = self.agent_loop.stream(
                user_input,
                context=self.ctx,
                verbose=getattr(self, 'verbose_mode', False)
            )
            full_text = await self.stream_to_chat(stream_gen)

            self.update_dashboard("Listo")

        except asyncio.TimeoutError:
            self.update_dashboard("Error")
            await self.write_to_chat("⏳ **Timeout:** El agente tardó demasiado.", type="system")
        except Exception as e:
            self.update_dashboard("Error")
            await self.write_to_chat(f"❌ **Error:** {e}", type="system")
            logger.error(f"Error en AgentLoop: {e}", exc_info=True)
        finally:
            loading.display = False
            self.query_one("#input-box", FileAwareInput).focus()
            if self.debug_mode:
                await self._refresh_debug_list()

    async def stream_to_chat(self, stream_generator):
        scroll = self.query_one("#chat-scroll", VerticalScroll)
        markdown_widget = Markdown("", classes="message-agent")
        await scroll.mount(markdown_widget)
        scroll.scroll_end(animate=False)

        full_text = ""
        async for chunk in stream_generator:
            full_text += chunk
            await markdown_widget.update(full_text)
            scroll.scroll_end(animate=False)

        return full_text

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        user_text = event.value.strip()
        if not user_text and not self.attached_files and not self.attached_images:
            return

        event.input.value = ""

        # 🔥 Si hay imágenes, las procesamos directamente
        if self.attached_images:
            # Mostramos el mensaje del usuario en el chat
            display_text = user_text if user_text else "[Imagen adjunta]"
            await self.write_to_chat(display_text, type="user")

            # Añadimos el mensaje multimodal al contexto
            self.ctx.add_user_with_image(user_text, self.attached_images)

            # Limpiamos las imágenes
            self.attached_images = []
            self.update_attachments_bar()

            # Llamamos al loop directamente (sin pasar por process_input)
            self.update_dashboard("Pensando...")
            loading = self.query_one("#loading-indicator", LoadingIndicator)
            loading.display = True

            try:
                stream_gen = self.agent_loop.stream(
                    "",  # 🔥 String vacío para que no añada otro mensaje
                    context=self.ctx,
                    verbose=getattr(self, 'verbose_mode', False)
                )
                await self.stream_to_chat(stream_gen)
                self.update_dashboard("Listo")
            except Exception as e:
                await self.write_to_chat(f"❌ **Error:** {e}", type="system")
            finally:
                loading.display = False
                self.query_one("#input-box", FileAwareInput).focus()
            return

        # Flujo normal (texto y archivos)
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
