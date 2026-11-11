import pytest
from unittest.mock import patch
from app.main import main
from app.tools import register_core_tools
from app.core.harness.tool import ToolRegistry


def test_register_core_tools():
    """Covers tool registration."""
    registry = ToolRegistry()
    register_core_tools(registry)
    assert "bash" in registry.names()
    assert "read_file" in registry.names()


@patch("app.main.asyncio.run")
def test_main_entry(mock_asyncio_run):
    """Covers the entry point."""
    main()
    assert mock_asyncio_run.called
