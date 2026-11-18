import pytest
from unittest.mock import patch

# Importamos la función a testear
from generate_report import generate_report, budget_status, resolve_budget


@pytest.fixture
def mock_analyze():
    """Mockea analyze_session para devolver datos predecibles."""
    with patch("generate_report.analyze_session") as mock:
        mock.return_value = {
            "session_id": "test_session",
            "model": "openai/gpt-5",
            "prompt_tokens": 1000,
            "completion_tokens": 500,
            "total_tokens": 1500,
            "prompt_cost_usd": 0.0025,
            "completion_cost_usd": 0.005,
            "cost_usd": 0.0075
        }
        yield mock


@pytest.fixture
def mock_suggest():
    """Mockea suggest para no depender de precios en vivo."""
    with patch("generate_report.suggest") as mock:
        mock.return_value = {
            "cheaper": "openai/gpt-5-mini",
            "savings": "~80%",
            "tip": "Enable prompt caching."
        }
        yield mock


def test_generate_report_within_budget(tmp_path, mock_analyze, mock_suggest):
    """Testea un reporte donde el coste está dentro del presupuesto."""
    with patch("generate_report.REPORTS_DIR", tmp_path):
        report_output = generate_report(
            session_id="test_session",
            budget=5.00,
            model="openai/gpt-5"
        )

        # Verificamos el contenido del output (que es la tabla + status)
        assert "✅ **Within budget**" in report_output
        assert "| **Total** | **1,500** | **$0.007500** |" in report_output
        # El desglose usa los costes por concepto, no hardcodeados
        assert "| Prompt (Input) | 1,000 | $0.002500 |" in report_output
        assert "| Completion (Output) | 500 | $0.005000 |" in report_output
        # Sale en el nombre del archivo guardado
        assert "test_session" in report_output

        # Verificamos que se ha guardado en disco
        saved_reports = list(tmp_path.glob("*.md"))
        assert len(saved_reports) == 1
        assert "test_session" in saved_reports[0].name

        # Verificamos que el reporte guardado en disco SÍ tiene el Markdown completo
        saved_content = saved_reports[0].read_text()
        assert "**Session:** `test_session`" in saved_content
        assert "### Token Budget Report" in saved_content


def test_generate_report_exceeded_budget(tmp_path, mock_analyze, mock_suggest):
    """Testea un reporte donde el coste excede el presupuesto."""
    with patch("generate_report.REPORTS_DIR", tmp_path):
        report_output = generate_report(
            session_id="test_session",
            budget=0.001,
            model="openai/gpt-5"
        )

        # Verificamos que salta la alerta
        assert "⚠️ **Budget exceeded**" in report_output


def test_generate_report_approaching_budget(tmp_path, mock_analyze, mock_suggest):
    """Testea la alerta temprana al superar el umbral (80%) sin exceder el presupuesto."""
    with patch("generate_report.REPORTS_DIR", tmp_path):
        report_output = generate_report(
            session_id="test_session",
            budget=0.009,   # 0.0075 / 0.009 = 83% > 80% umbral, pero < presupuesto
            model="openai/gpt-5",
            threshold=0.8
        )

        assert "Approaching budget" in report_output


def test_generate_report_session_not_found(tmp_path, mock_analyze, mock_suggest):
    """Testea el caso en que la sesión no existe."""
    mock_analyze.return_value = None
    with patch("generate_report.REPORTS_DIR", tmp_path):
        report_output = generate_report(
            session_id="ghost_session",
            budget=5.00,
            model="openai/gpt-5"
        )
        assert "Error: Session ghost_session not found." in report_output
        assert len(list(tmp_path.glob("*.md"))) == 0


def test_budget_status_levels():
    assert "exceeded" in budget_status(6.0, 5.0, 0.8)
    assert "Approaching" in budget_status(4.5, 5.0, 0.8)
    assert "Within" in budget_status(1.0, 5.0, 0.8)


def test_resolve_budget_precedence():
    config = {
        "default_budget_usd": 5.0,
        "alert_threshold": 0.8,
        "model_overrides": {"openai/gpt-5": {"budget_usd": 10.0}},
    }
    assert resolve_budget(2.0, config, "openai/gpt-5") == 2.0   # CLI gana
    # override por modelo
    assert resolve_budget(None, config, "openai/gpt-5") == 10.0
    assert resolve_budget(None, config, "otro/modelo") == 5.0     # default
