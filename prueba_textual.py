from textual.app import App, ComposeResult
from textual.widgets import Input, Static


class MiApp(App):
    def compose(self) -> ComposeResult:
        yield Static("Escribe algo (debería verse mientras escribes):")
        yield Input(placeholder="Escribe aquí...")


if __name__ == "__main__":
    MiApp().run()
