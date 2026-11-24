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


def test_register_core_tools_with_memory():
    from unittest.mock import MagicMock
    from app.tools import register_core_tools
    from app.core.harness.tool import ToolRegistry
    from app.core.harness.memory.backends.sqlite import SQLiteStore

    registry = ToolRegistry()
    memory_store = MagicMock(spec=SQLiteStore)
    register_core_tools(registry, memory_store=memory_store)

    assert "memory_save" in registry.names()
    assert "memory_recall" in registry.names()


def test_tom_test_enforces_full_coverage():
    """El script de tests debe fallar si la cobertura baja del 100%."""
    import tomllib
    from pathlib import Path

    config = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    test_command = config["tool"]["tomlscript"]["test"]

    assert "--cov-fail-under=100" in test_command


def test_no_known_unused_imports():
    """Los imports señalados en la auditoría deben estar eliminados."""
    import ast
    from pathlib import Path

    def imported_names(path: Path) -> set[str]:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.update(a.asname or a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                names.update(a.asname or a.name for a in node.names)
        return names

    app_imports = imported_names(Path("app/tui/app.py"))
    assert "UnicodeImage" not in app_imports
    assert "unquote" not in app_imports
    assert "pd" not in imported_names(Path("app/tools/documents.py"))


def test_no_print_in_production_code():
    """Verifica que no se use print() en el código de producción."""
    import os
    from pathlib import Path

    forbidden_dirs = ["app/"]
    for dir_path in forbidden_dirs:
        for root, _, files in os.walk(dir_path):
            for file in files:
                if file.endswith(".py"):
                    file_path = Path(root) / file
                    content = file_path.read_text()
                    # Ignoramos comentarios
                    lines = [line for line in content.split(
                        "\n") if not line.strip().startswith("#")]
                    for i, line in enumerate(lines, 1):
                        # Ignoramos rich.console
                        if "print(" in line and "console.print(" not in line:
                            raise AssertionError(
                                f"❌ Uso de print() encontrado en {file_path}:{i}\n{line}")
