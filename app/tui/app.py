import asyncio
import json
from pathlib import Path
import pyperclip
from textual.app import App, ComposeResult
from textual.containers import Vertical, Horizontal, Center, VerticalScroll
from textual.widgets import Input, Static, LoadingIndicator, Markdown
from textual.widgets._markdown import MarkdownFence
from textual.widgets import Button
from textual import work
from textual.screen import ModalScreen
from textual.suggester import SuggestFromList

from app.core.llm import get_llm
from app.core.harness import AgentLoop, ToolRegistry, ContextManager
from app.core.harness.permissions import PermissionGate
from app.core.harness.subagents import DelegateTool
from app.tools import register_core_tools
from app.tui.commands import handle_command
from app.mcp.client import MCPClient
from app.core.config import settings
from app.core.logger import logger
from app.tools.memory import SUMMARY_FILE

# ==========================================
# MARKDOWN PERSONALIZADO CON BOTÓN DE COPIAR
# ==========================================


class CopyableMarkdownFence(MarkdownFence):
    """Bloque de código con botón de copiar."""

    def compose(self) -> ComposeResult:
        yield from super().compose()
        # El botón se añadirá dinámicamente en on_mount

    async def on_mount(self) -> None:
        # Añadimos el botón como un hijo del bloque
        btn = Button("📋", id=f"copy-{id(self)}",
                     classes="copy-btn", variant="default")
        await self.mount(btn)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id and event.button.id.startswith("copy-"):
            try:
                # En algunas versiones de Textual el código está en self.code
                pyperclip.copy(self.code)
                event.button.label = "✅"
                self.set_timer(1.5, lambda: setattr(
                    event.button, "label", "📋"))
            except Exception as e:
                event.button.label = "❌"


class CopiableMarkdown(Markdown):
    """Markdown que usa bloques de código con botón de copiar."""

    def get_fence(self, code: str, language: str | None = None) -> MarkdownFence:
        return CopyableMarkdownFence(code, language)


class CopiableMarkdown(Markdown):
    """Un widget Markdown que usa bloques de código con botón de copiar."""

    def get_fence(self, code: str, language: str | None = None) -> MarkdownFence:
        return CopyableMarkdownFence(code, language)

# ==========================================
# MODAL DE PERMISOS
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
# APP PRINCIPAL
# ==========================================


class AgentHarnessApp(App):
    BINDINGS = [
        ("ctrl+q", "quit", "Salir"),
        ("ctrl+l", "clear_chat", "Limpiar Chat"),
        ("ctrl+u", "clear_input", "Limpiar Input"),
    ]

    CSS = """
    Screen {
        background: #0d1117;
    }
    
    /* TÍTULO */
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

    /* CHAT */
    #chat-container {
        height: 1fr;
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
    
    /* BOTÓN DE COPIAR EN BLOQUES DE CÓDIGO */
    .copy-btn {
        dock: right;
        width: 5;
        height: 1;
        margin-top: 1;
        margin-right: 1;
        background: #21262d;
        border: round #30363d;
        color: #8b949e;
        padding: 0;
        min-width: 5;
    }
    
    .copy-btn:hover {
        color: #58a6ff;
        background: #30363d;
    }

    /* INPUT */
    #input-container {
        dock: bottom; 
        height: 5; 
        padding: 0 2; 
        background: #0d1117;
        border-top: solid #30363d;
        align: center middle; 
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
        self.loop_agent = None
        self.attached_files = []

    def compose(self) -> ComposeResult:
        with Center(id="header-container"):
            yield Static("📊 Iniciando...", id="dashboard")

        with Vertical(id="chat-container"):
            with VerticalScroll(id="chat-scroll"):
                pass
            yield LoadingIndicator(id="loading-indicator")

        with Vertical(id="input-container"):
            yield Input(placeholder="Escribe tu mensaje... (Ctrl+U para limpiar)", id="input-box")

    async def on_mount(self) -> None:
        await self.inicializar_agente()
        await self.escribir_en_chat("🤖 Agent Harness iniciado. Escribe /help para ver comandos.", tipo="system")

        comandos_disponibles = [
            "/help", "/shortcuts", "/model", "/tokens",
            "/compact", "/clear", "/debug", "/permissions", "/quit"
        ]

        input_box = self.query_one("#input-box", Input)
        input_box.suggester = SuggestFromList(
            comandos_disponibles, case_sensitive=False)
        input_box.focus()

    async def inicializar_agente(self):
        memory_context = ""
        if SUMMARY_FILE.exists():
            content = SUMMARY_FILE.read_text(encoding="utf-8").strip()
            if content:
                memory_context = f"\n\n[Memoria a largo plazo]:\n{content}"

        self.ctx = ContextManager(
            system_prompt=(
                "Eres un asistente útil. Tienes acceso a herramientas locales y remotas (MCP). "
                "Responde de forma concisa. Usa 'write_file' o 'edit_file' para modificar archivos. "
                "Para revisar código, usa 'delegate_to_reviewer'. Para recordar cosas, usa 'memory_save'."
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
                    await self.escribir_en_chat(f"❌ Error conectando MCP {name}: {e}", tipo="system")

        reviewer_tools = ToolRegistry()
        for tool_name in ["read_text_file", "list_directory", "bash"]:
            if tool_name in self.registry:
                reviewer_tools.register(self.registry.get(tool_name))

        reviewer_tool = DelegateTool(
            name="delegate_to_reviewer", description="Delega una tarea de revisión de código.",
            llm=get_llm(self.state["provider"]), tools=reviewer_tools,
            system_prompt="Eres un revisor de código experto. Sé conciso."
        )
        self.registry.register(reviewer_tool)

        self.gate = PermissionGate(ask_user=self.pedir_permiso_textual)
        self.loop_agent = AgentLoop(llm=get_llm(
            self.state["provider"]), tools=self.registry, permissions=self.gate)

        self.actualizar_dashboard("Listo")

    def actualizar_dashboard(self, status: str, tokens: int = 0, last_tool: str = "Ninguna"):
        dash = self.query_one("#dashboard", Static)
        color = "green" if status == "Listo" else "yellow" if status == "Pensando..." else "red"

        model_name = "Desconocido"
        if self.loop_agent and self.loop_agent.llm:
            model_name = getattr(self.loop_agent.llm, 'model_name', getattr(
                self.loop_agent.llm, 'model', 'Desconocido'))

        dash.update(
            f"⚡ [bold]{self.state['provider']}[/] ({model_name})  •  "
            f"Estado: [bold {color}]{status}[/]  •  "
            f"Tokens: {tokens}  •  Última tool: {last_tool}"
        )

    async def escribir_en_chat(self, texto: str, tipo: str = "agent"):
        scroll = self.query_one("#chat-scroll", VerticalScroll)

        if tipo == "user":
            widget = Static(f"👤 **Tú:**\n{texto}",
                            classes="message-user", markup=True)
        elif tipo == "system":
            widget = Static(texto, classes="message-system", markup=True)
        else:
            widget = CopiableMarkdown(texto, classes="message-agent")

        await scroll.mount(widget)
        scroll.scroll_end(animate=False)

    async def pedir_permiso_textual(self, tool_name: str, signature: str, args: dict, diff_text: str | None = None) -> str:
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

        self.query_one("#input-box", Input).focus()
        return result

    @work(exclusive=True)
    async def procesar_entrada(self, user_input: str):
        loading = self.query_one("#loading-indicator", LoadingIndicator)

        if user_input.startswith("/"):
            await self.escribir_en_chat(f"⚙️ Ejecutando comando: {user_input}", tipo="system")
            try:
                await handle_command(user_input, self.ctx, self.state, get_llm(self.state["provider"]), self)
            except Exception as e:
                await self.escribir_en_chat(f"❌ Error en comando: {e}", tipo="system")
            return

        self.actualizar_dashboard("Pensando...")

        texto_mostrar = user_input if len(
            user_input) < 300 else user_input[:300] + "..."
        await self.escribir_en_chat(texto_mostrar, tipo="user")

        loading.display = True

        try:
            result = await asyncio.wait_for(
                self.loop_agent.run(user_input, context=self.ctx),
                timeout=120.0
            )

            self.actualizar_dashboard(
                "Listo",
                tokens=result.usage_total.get("total_tokens", 0),
                last_tool=result.tools_used[-1] if result.tools_used else "Ninguna"
            )
            await self.escribir_en_chat(result.final_answer, tipo="agent")

        except asyncio.TimeoutError:
            self.actualizar_dashboard("Error")
            await self.escribir_en_chat("⏳ **Timeout:** El agente tardó demasiado.", tipo="system")
        except Exception as e:
            self.actualizar_dashboard("Error")
            await self.escribir_en_chat(f"❌ **Error:** {e}", tipo="system")
            logger.error(f"Error en AgentLoop: {e}", exc_info=True)
        finally:
            loading.display = False
            self.query_one("#input-box", Input).focus()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        user_text = event.value.strip()

        if not user_text and not self.attached_files:
            return

        event.input.value = ""

        mensaje_final = user_text
        if self.attached_files:
            archivos_str = ", ".join([f"`{f}`" for f in self.attached_files])
            if user_text:
                mensaje_final = f"{user_text}\n\n[Archivos adjuntos para revisar: {archivos_str}]"
            else:
                mensaje_final = f"[Por favor, revisa estos archivos: {archivos_str}]"

            self.attached_files = []

        self.procesar_entrada(mensaje_final)

    async def on_paste(self, event) -> None:
        texto_pegado = event.text.strip()
        ruta_limpia = texto_pegado.strip("'\"")
        if ruta_limpia.startswith("file://"):
            ruta_limpia = ruta_limpia.replace("file://", "")
            if not ruta_limpia.startswith("/"):
                ruta_limpia = "/" + ruta_limpia

        try:
            p = Path(ruta_limpia).expanduser()
            if p.exists() and p.is_file():
                if str(p) not in self.attached_files:
                    self.attached_files.append(str(p))
                    icono = "📎"
                    if p.suffix.lower() in [".png", ".jpg", ".jpeg", ".gif"]:
                        icono = "🖼️"
                    elif p.suffix.lower() == ".pdf":
                        icono = "📄"
                    elif p.suffix.lower() in [".mp3", ".wav", ".m4a"]:
                        icono = "🎵"
                    elif p.suffix.lower() in [".py", ".js", ".ts", ".txt"]:
                        icono = "📝"

                    await self.escribir_en_chat(f"{icono} **Archivo adjunto:** `{p}`", tipo="system")

                event.prevent_default()
        except Exception:
            pass

    async def action_clear_chat(self) -> None:
        scroll = self.query_one("#chat-scroll", VerticalScroll)
        await scroll.remove_children()
        await self.escribir_en_chat("🧹 Chat limpiado (Ctrl+L)", tipo="system")

    def action_clear_input(self) -> None:
        input_box = self.query_one("#input-box", Input)
        input_box.value = ""
        input_box.focus()

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
