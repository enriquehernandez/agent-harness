from app.core.harness.tool import ToolRegistry
from .filesystem import ReadFileTool, WriteFileTool
from .shell import BashTool


def register_core_tools(registry: ToolRegistry, base_dir: str = ".") -> None:
    """Registra todas las herramientas locales disponibles."""
    registry.register(ReadFileTool(base_dir=base_dir))
    registry.register(WriteFileTool(base_dir=base_dir))
    registry.register(BashTool())


__all__ = ["register_core_tools"]
