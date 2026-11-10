import pytest
from unittest.mock import patch
from app.main import main
from app.tools import register_core_tools
from app.core.harness.tool import ToolRegistry


def test_register_core_tools():
    """Cubre el registro de herramientas."""
    registry = ToolRegistry()
    register_core_tools(registry)
    assert "bash" in registry.names()
    assert "read_file" in registry.names()


@patch("app.main.asyncio.run")
def test_main_entry(mock_asyncio_run):
    """Cubre el punto de entrada."""
    main()
    mock_asyncio_run.assert_called_once()


@patch("app.main.asyncio.run")
def test_main_entry_point(mock_asyncio_run):
    """Cubre la función main() que lanza la TUI."""
    # Al llamar a main(), se ejecuta asyncio.run(run_tui())
    main()
    mock_asyncio_run.assert_called_once()
