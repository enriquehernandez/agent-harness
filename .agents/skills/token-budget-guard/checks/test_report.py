import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Importamos la función a testear
from generate_report import generate_report


@pytest.fixture
def mock_analyze():
    """Mockea analyze_session para devolver datos predecibles."""
    with patch("generate_report.analyze_session") as mock:
        mock.return_value = {
            "session_id": "test_session",
            "model": "openai/gpt-4o",
            "prompt_tokens": 1000,
            "completion_tokens": 500,
            "total_tokens": 1500,
            "cost_usd": 0.0075
        }
        yield mock


def test_generate_report_within_budget(tmp_path, mock_analyze):
    """Testea un reporte donde el coste está dentro del presupuesto."""
    with patch("generate_report.REPORTS_DIR", tmp_path):
        report_output = generate_report(
            session_id="test_session",
            budget=5.00,
            model="openai/gpt-4o"
        )

        # Verificamos el contenido del output (que es la tabla + status)
        assert "✅ **Within budget**" in report_output
        assert "| **Total** | **1,500** | **$0.007500** |" in report_output
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


def test_generate_report_exceeded_budget(tmp_path, mock_analyze):
    """Testea un reporte donde el coste excede el presupuesto."""
    with patch("generate_report.REPORTS_DIR", tmp_path):
        report_output = generate_report(
            session_id="test_session",
            budget=0.001,
            model="openai/gpt-4o"
        )

        # Verificamos que salta la alerta
        assert "⚠️ **Budget exceeded**" in report_output


def test_generate_report_session_not_found(tmp_path):
    """Testea el caso en que la sesión no existe."""
    with patch("generate_report.analyze_session", return_value=None):
        with patch("generate_report.REPORTS_DIR", tmp_path):
            report_output = generate_report(
                session_id="ghost_session",
                budget=5.00,
                model="openai/gpt-4o"
            )
            assert "Error: Session ghost_session not found." in report_output
            assert len(list(tmp_path.glob("*.md"))) == 0
