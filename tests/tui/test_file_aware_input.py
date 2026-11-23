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
