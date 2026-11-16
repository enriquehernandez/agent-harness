import pytest
from suggest_alternatives import suggest


def test_suggest_alternatives_known_model():
    """Testea que devuelve una recomendación para un modelo conocido."""
    result = suggest("openai/gpt-4o")

    assert isinstance(result, dict)
    assert "cheaper" in result
    assert "savings" in result
    assert "tip" in result
    assert result["cheaper"] == "openai/gpt-4o-mini"
    assert result["savings"] == "~94%"


def test_suggest_alternatives_unknown_model():
    """Testea que devuelve un error estructurado para un modelo desconocido."""
    result = suggest("modelo/inventado-xyz")

    assert isinstance(result, dict)
    assert "error" in result
    assert "No recommendations" in result["error"]
