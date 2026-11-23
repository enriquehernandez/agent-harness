import pytest
from unittest.mock import MagicMock
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
