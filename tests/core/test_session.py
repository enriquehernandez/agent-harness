import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from app.core.harness.session import SessionManager
from app.core.harness.context import ContextManager
from app.core.config import settings


@pytest.fixture
def mock_settings(tmp_path):
    # 🔥 Parcheamos la propiedad directamente en la clase Settings
    # creando un PropertyMock que devuelve nuestro tmp_path
    from unittest.mock import PropertyMock
    with patch("app.core.config.Settings.sessions_dir", new_callable=PropertyMock) as mock_dir:
        mock_dir.return_value = tmp_path
        yield tmp_path


def test_session_save_and_load(mock_settings):
    ctx = ContextManager()
    ctx.add_user("Hola")
    ctx.add_assistant("Mundo")

    sm = SessionManager("test_session")
    file_path = sm.save(ctx, agent_loop=None)

    assert Path(file_path).exists()

    loaded = sm.load()
    assert len(loaded) == 2
    assert loaded[0]["content"] == "Hola"
    assert loaded[1]["content"] == "Mundo"


def test_session_save_empty_messages(mock_settings):
    ctx = MagicMock()
    ctx.get_messages.return_value = [
        {"role": "user", "content": ""},
        {"role": "assistant", "content": "Hola"},
        {"role": "tool", "content": "", "tool_calls": []}
    ]
    sm = SessionManager("test_empty")
    sm.save(ctx, agent_loop=None)

    data = json.loads(sm.session_file.read_text())
    assert data["message_count"] == 1


def test_session_load_not_exists(mock_settings):
    sm = SessionManager("inexistente")
    assert sm.load() == []


def test_session_list_sessions(mock_settings):
    for i in range(2):
        f = mock_settings / f"session_{i}.json"
        f.write_text(json.dumps({
            "session_id": f"session_{i}",
            "timestamp": "2024-01-01T10:00:00",
            "message_count": i + 1,
            "messages": []
        }))

    (mock_settings / "corrupt.json").write_text("no es json")

    sessions = SessionManager.list_sessions()
    assert len(sessions) == 2
    assert sessions[0]["id"] == "session_1"


def test_session_delete(mock_settings):
    sm = SessionManager("to_delete")
    sm.session_file.write_text("{}")

    assert SessionManager.delete_session("to_delete") is True
    assert not sm.session_file.exists()

    assert SessionManager.delete_session("no_existe") is False


@pytest.mark.asyncio
async def test_session_repair_counts_persistence(mock_settings):
    """Cubre el guardado y carga de repair_counts en la sesión."""
    from unittest.mock import MagicMock
    from app.core.harness.context import ContextManager

    ctx = ContextManager(system_prompt="System")
    ctx.add_user("Test")

    # Mockeamos un AgentLoop que tiene repair_counts
    mock_agent = MagicMock()
    mock_agent.repair_counts = {"bash": 2}

    sm = SessionManager("test_repair")

    # 1. Guardamos con el agent_loop
    sm.save(ctx, agent_loop=mock_agent)

    # 2. Cargamos los metadatos y verificamos
    metadata = sm.load_metadata()
    assert metadata["repair_counts"] == {"bash": 2}


def test_session_load_metadata_corrupt(mock_settings):
    """Cubre el except de load_metadata (línea 45)."""
    from app.core.harness.session import SessionManager
    sm = SessionManager("corrupt_meta")
    # Forzamos que el session_file exista (porque mock_settings parchea sessions_dir)
    sm.session_file.parent.mkdir(parents=True, exist_ok=True)
    sm.session_file.write_text("{invalid_json}")

    # Verificamos que load_metadata devuelve {} sin lanzar excepción
    assert sm.load_metadata() == {}


def test_session_load_metadata_exception(mock_settings):
    """Cubre la línea 45: cuando el JSON está corrupto."""
    sm = SessionManager("corrupt_meta")
    # Escribimos un JSON inválido directamente
    sm.session_file.write_text("{invalid_json}")
    assert sm.load_metadata() == {}


def test_session_load_metadata_file_not_exists(mock_settings):
    """Cubre la línea 45 de session.py: archivo inexistente."""
    sm = SessionManager("non_existent_session_123")
    # No creamos el archivo
    assert not sm.session_file.exists()  # Verificamos que no existe
    assert sm.load_metadata() == {}      # Debe devolver {} por la línea 45
