import importlib
import sys
import tomllib
from pathlib import Path
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


@patch("app.main.run_tui")
def test_main_entry(mock_run_tui):
    """Covers the entry point without leaking an un-awaited Textual coroutine."""
    main()
    mock_run_tui.assert_called_once_with()


def test_main_entry_without_textual_image():
    """La app arranca aunque `textual_image` no esté instalado."""
    import app.main as main_module

    sys.modules["textual_image.renderable"] = None
    try:
        reloaded = importlib.reload(main_module)
        with patch.object(reloaded, "run_tui") as mock_run_tui:
            reloaded.main()
        mock_run_tui.assert_called_once_with()
    finally:
        del sys.modules["textual_image.renderable"]
        importlib.reload(main_module)


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
    config = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    test_command = config["tool"]["tomlscript"]["test"]

    assert "--cov-fail-under=100" in test_command


def test_test_config_does_not_hide_failures():
    """La configuración no debe ocultar integración, warnings ni ramas reales."""
    config = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    pytest_config = config["tool"]["pytest"]["ini_options"]

    assert "--ignore=tests/integration" not in pytest_config["addopts"]
    assert pytest_config.get("filterwarnings", []) == []
    assert set(config["tool"]["coverage"]["report"]["exclude_lines"]) == {
        "pragma: no cover",
        "if __name__ == .__main__.:",
        r"^\s*\.\.\.\s*$",
    }


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
