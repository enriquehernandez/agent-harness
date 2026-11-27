import pytest
from unittest.mock import MagicMock
from textual.app import App
from textual.widgets import Static
from app.tui.modals.permission import PermissionModal


@pytest.mark.asyncio
async def test_permission_modal_compose():
    """Verifica que el modal se compone correctamente."""
    modal = PermissionModal("bash", "command: ls", None)
    assert modal.tool_name == "bash"
    assert modal.args_str == "command: ls"
    assert modal.diff_text is None


@pytest.mark.asyncio
async def test_permission_modal_responses():
    """Verifica que el modal devuelve la respuesta correcta."""
    modal = PermissionModal("bash", "command: ls", None)
    # Mockeamos dismiss para capturar la respuesta
    modal.dismiss = MagicMock()

    # Simulamos la pulsación de "y"
    event = MagicMock()
    event.key = "y"
    event.prevent_default = MagicMock()
    modal.on_key(event)
    modal.dismiss.assert_called_with("y")


@pytest.mark.asyncio
async def test_permission_modal_compose_without_args_or_diff():
    """El modal indica cuando no hay argumentos y muestra la propuesta de cambios."""
    class ModalHost(App):
        def compose(self):
            yield PermissionModal("read_file", "", "--- diff ---")

    app = ModalHost()
    async with app.run_test() as pilot:
        modal = app.query_one(PermissionModal)
        message = modal.query_one("#message", Static)
        text = str(message.render())

    assert "no requiere argumentos" in text
    assert "Propuesta de cambios:" in text
    assert "--- diff ---" in text


@pytest.mark.parametrize("button_id,expected", [
    ("allow", "y"),
    ("always", "a"),
    ("deny", "n"),
])
def test_permission_modal_buttons(button_id, expected):
    """Cada botón devuelve una decisión distinta."""
    modal = PermissionModal("bash", "ls")
    modal.dismiss = MagicMock()
    event = MagicMock()
    event.button.id = button_id

    modal.on_button_pressed(event)

    modal.dismiss.assert_called_once_with(expected)


@pytest.mark.parametrize("key", ["n", "escape"])
def test_permission_modal_denial_keys(key):
    """`n` y Escape deniegan y consumen el evento."""
    modal = PermissionModal("bash", "ls")
    modal.dismiss = MagicMock()
    event = MagicMock()
    event.key = key

    modal.on_key(event)

    modal.dismiss.assert_called_once_with("n")
    event.prevent_default.assert_called_once()
