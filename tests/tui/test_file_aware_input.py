import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from app.tui.widgets.file_aware_input import FileAwareInput


def test_clean_path():
    """Verifica la limpieza de rutas."""
    input_box = FileAwareInput()
    assert input_box._clean_path("'/path/to/file.txt'") == "/path/to/file.txt"
    assert input_box._clean_path(
        "/path/with\\\\ spaces/file.txt") == "/path/with spaces/file.txt"


@pytest.mark.asyncio
async def test_process_batch(tmp_path):
    """Verifica que el batch procesa los archivos."""
    mock_app = MagicMock()
    mock_app.handle_file_paste = AsyncMock()

    input_box = FileAwareInput()
    # 🔥 No podemos asignar `input_box.app` porque es read-only.
    # En su lugar, parcheamos el método `_process_single_file` y verificamos
    # que se llama con la ruta correcta.
    input_box._pending_files = [str(tmp_path / "test.txt")]
    (tmp_path / "test.txt").write_text("Hola")

    with patch.object(input_box, "_process_single_file", new_callable=AsyncMock) as mock_single:
        await input_box._process_batch()
        mock_single.assert_called_once_with(str(tmp_path / "test.txt"))


@pytest.mark.asyncio
async def test_file_aware_input_on_key_ctrl_u():
    """Ctrl+U limpia el input y sus adjuntos sin propagar el evento."""
    from app.tui.app import AgentHarnessApp

    app = AgentHarnessApp()
    with patch("app.tui.app.SessionManager") as mock_sm:
        mock_sm.list_sessions.return_value = []
        with patch.object(app, "initialize_agent", new_callable=AsyncMock):
            async with app.run_test() as pilot:
                input_box = app.query_one("#input-box", FileAwareInput)
                input_box.focus()
                await pilot.pause()

                input_box.value = "texto a borrar"
                app.attached_files = ["/tmp/fake.txt"]
                app.attached_images = ["data:image/png;base64,x"]

                event = MagicMock()
                event.key = "ctrl+u"
                await input_box.on_key(event)

                assert input_box.value == ""
                assert app.attached_files == []
                assert app.attached_images == []
                event.prevent_default.assert_called_once()
                event.stop.assert_called_once()

                # Otras teclas no se interceptan
                other_event = MagicMock()
                other_event.key = "a"
                await input_box.on_key(other_event)
                other_event.prevent_default.assert_not_called()
                other_event.stop.assert_not_called()
