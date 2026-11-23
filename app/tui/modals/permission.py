# app/tui/modals/permission.py
from textual.screen import ModalScreen
from textual.containers import Vertical, Horizontal
from textual.widgets import Static, Button
from textual.app import ComposeResult


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
        max-height: 20;
        overflow-y: auto;
        width: 100%;
        padding: 0 0 1 0;
    }
    #buttons {
        height: auto;
        width: 100%;
        align: center middle;
        dock: bottom;
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
