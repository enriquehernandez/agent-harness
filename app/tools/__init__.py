from app.core.harness.tool import ToolRegistry
from .filesystem import ReadFileTool, WriteFileTool
from .shell import BashTool
from .memory import MemorySaveTool, MemoryRecallTool  # 🔥 Importamos


def register_core_tools(registry: ToolRegistry, base_dir: str = ".") -> None:
    registry.register(ReadFileTool(base_dir=base_dir))
    registry.register(WriteFileTool(base_dir=base_dir))
    registry.register(BashTool())
    # 🔥 Registramos las de memoria
    registry.register(MemorySaveTool())
    registry.register(MemoryRecallTool())


__all__ = ["register_core_tools"]
