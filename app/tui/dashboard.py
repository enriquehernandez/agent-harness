from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.console import Group
from rich.text import Text
from rich.markdown import Markdown


class Dashboard:
    def __init__(self):
        self.state = {
            "provider": "Desconocido",
            "model": "N/A",
            "tokens": 0,
            "tools_used": [],
            "log_level": "INFO",
            "status": "Listo",
            "last_tool": "Ninguna"
        }
        self.messages = []
        self.prompt_text = ""  # 🔥 Almacenamos el texto del prompt

    def update(self, **kwargs):
        self.state.update(kwargs)

    def set_prompt_text(self, text: str):
        self.prompt_text = text

    def add_message(self, role: str, content: str):
        self.messages.append((role, content))

    def get_dashboard_panel(self) -> Panel:
        # ... (Igual que antes)
        table = Table.grid(expand=True)
        table.add_column(justify="left", ratio=1)
        table.add_column(justify="center", ratio=1)
        table.add_column(justify="right", ratio=1)

        provider_text = Text(f"🧠 {self.state['provider']}", style="bold cyan")
        model_text = Text(f"{self.state['model']}", style="dim")

        status_color = "green" if self.state["status"] == "Listo" else "yellow"
        status_text = Text(f"⚡ {self.state['status']}", style=status_color)
        tokens_text = Text(f"🪙 {self.state['tokens']} tokens", style="magenta")

        tool_text = Text(f"🛠️ {self.state['last_tool']}", style="blue")
        log_text = Text(f"Log: {self.state['log_level']}", style="dim")

        table.add_row(
            Group(provider_text, model_text),
            Group(status_text, tokens_text),
            Group(tool_text, log_text)
        )

        return Panel(table, title="[bold]Harness Dashboard[/bold]", border_style="bright_black", padding=(0, 1))

    def get_messages_panel(self) -> Panel:
        # ... (Igual que antes)
        renderables = []
        for role, content in self.messages[-10:]:
            if role == "user":
                renderables.append(Text(f"🐚 > {content}", style="bold cyan"))
            elif role == "agent":
                renderables.append(Text("🤖 Agente:", style="bold green"))
                renderables.append(Markdown(content))
            elif role == "system":
                renderables.append(Text(content, style="dim italic"))
            elif role == "error":
                renderables.append(Text(f"Error: {content}", style="bold red"))
            renderables.append(Text(""))

        return Panel(Group(*renderables), title="[bold]Conversación[/bold]", border_style="bright_black", padding=(0, 1))

    def make_layout(self) -> Layout:
        layout = Layout(name="root")
        layout.split_column(
            Layout(name="header", size=5),
            Layout(name="body", ratio=1),
            Layout(name="footer", size=3)
        )

        layout["header"].update(self.get_dashboard_panel())
        layout["body"].update(self.get_messages_panel())

        # 🔥 El footer muestra el prompt con el texto actual
        layout["footer"].update(
            Panel(
                Text(f"🐚 > {self.prompt_text}", style="bold cyan"),
                border_style="cyan",
                padding=(0, 1)
            )
        )

        return layout
