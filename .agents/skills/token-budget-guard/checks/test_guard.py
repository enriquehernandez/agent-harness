import pytest
from unittest.mock import patch
from suggest_alternatives import suggest

MOCK_PRICES = {
    "openai/gpt-5": {"input": 1.25e-6, "output": 1e-5},
    "openai/gpt-5-mini": {"input": 0.25e-6, "output": 2e-6},
    "google/gemini-3-flash": {"input": 0.5e-6, "output": 3e-6},
}


@pytest.fixture
def mock_pricing():
    with patch("suggest_alternatives.get_pricing") as mock:
        mock.side_effect = lambda model: MOCK_PRICES.get(
            model, {"input": 1e-6, "output": 1e-6})
        yield mock


def test_suggest_alternatives_known_model(mock_pricing):
    """Testea que devuelve una recomendación con ahorro calculado para un modelo conocido."""
    result = suggest("openai/gpt-5")

    assert isinstance(result, dict)
    assert "cheaper" in result
    assert "savings" in result
    assert "tip" in result
    assert result["cheaper"] == "openai/gpt-5-mini"
    # blended: gpt-5 = 5.625e-6, mini = 1.125e-6 -> 80% ahorro
    assert result["savings"] == "~80%"


def test_suggest_alternatives_unknown_model(mock_pricing):
    """Testea que devuelve un error estructurado para un modelo desconocido."""
    result = suggest("modelo/inventado-xyz")

    assert isinstance(result, dict)
    assert "error" in result
    assert "No recommendations" in result["error"]
