import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Importamos la función a testear (asumiendo que conftest.py añade scripts/ al path)
from analyze_session import analyze_session

# Mock de precios para el test
MOCK_PRICING = {
    "openai/gpt-4o": {"input": 2.5e-6, "output": 1e-5}
}


@pytest.fixture
def mock_pricing():
    """Mockea get_pricing para no depender de la red."""
    with patch("analyze_session.get_pricing") as mock:
        mock.side_effect = lambda model: MOCK_PRICING.get(
            model, {"input": 1e-6, "output": 1e-6})
        yield mock


def test_analyze_session_success(tmp_path, mock_pricing):
    """Testea el cálculo correcto de tokens y costes."""
    # 1. Creamos un archivo de sesión falso
    session_file = tmp_path / "session_test.json"
    session_data = {
        "session_id": "session_test",
        "usage_total": {
            "prompt_tokens": 1000,
            "completion_tokens": 500,
            "total_tokens": 1500
        }
    }
    session_file.write_text(json.dumps(session_data))

    # 2. Ejecutamos la función
    result = analyze_session(session_file, model_name="openai/gpt-4o")

    # 3. Verificamos los resultados
    assert result is not None
    assert result["session_id"] == "session_test"
    assert result["model"] == "openai/gpt-4o"
    assert result["prompt_tokens"] == 1000
    assert result["completion_tokens"] == 500
    assert result["total_tokens"] == 1500

    # Cálculo esperado: (1000 * 2.5e-6) + (500 * 1e-5) = 0.0025 + 0.005 = 0.0075
    assert result["cost_usd"] == 0.0075


def test_analyze_session_empty_usage(tmp_path, mock_pricing):
    """Testea el caso de una sesión sin datos de uso (gratis o incompleta)."""
    session_file = tmp_path / "session_empty.json"
    session_data = {
        "session_id": "session_empty",
        "usage_total": {}
    }
    session_file.write_text(json.dumps(session_data))

    result = analyze_session(session_file, model_name="openai/gpt-4o")

    assert result["prompt_tokens"] == 0
    assert result["completion_tokens"] == 0
    assert result["total_tokens"] == 0
    assert result["cost_usd"] == 0.0


def test_analyze_session_file_not_found():
    """Testea el caso en que el archivo de sesión no existe."""
    fake_path = Path("/ruta/que/no/existe/session.json")
    result = analyze_session(fake_path)
    assert result is None
