from rich.syntax import Syntax
from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.containers import Vertical, VerticalScroll
from textual.widgets import Static, Label, ListView, ListItem


class DebugDetailScreen(ModalScreen):
    """Modal screen to view the JSON detail of a debug event."""

    CSS = """
    DebugDetailScreen {
        align: center middle;
        background: rgba(0, 0, 0, 0.9);
    }
    #detail-container {
        width: 90%;
        height: 85%;
        border: round $accent;
        background: $surface;
        padding: 1 2;
    }
    #detail-header {
        height: 3;
        dock: top;
        content-align: center middle;
        text-style: bold;
        color: $accent;
    }
    #detail-content {
        height: 1fr;
        overflow-y: auto;
    }
    """

    def __init__(self, title: str, payload: str):
        super().__init__()
        self.title = title
        self.payload = payload

    def compose(self) -> ComposeResult:
        with Vertical(id="detail-container"):
            yield Label(f"🪲 Detalle: {self.title} (Esc para cerrar)", id="detail-header")
            with VerticalScroll(id="detail-content"):
                try:
                    syntax = Syntax(self.payload, "json",
                                    theme="monokai", line_numbers=True)
                    yield Static(syntax)
                except Exception:
                    yield Static(self.payload)

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss()
