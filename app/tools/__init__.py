from app.core.harness.tool import ToolRegistry
from .filesystem import ReadFileTool, WriteFileTool, EditFileTool
from .shell import BashTool
from .memory import MemorySaveTool, MemoryRecallTool
from .skills import LoadSkillTool
from .observations import ExportObservationsTool
from .documents import ReadDocumentTool


def register_core_tools(registry: ToolRegistry, base_dir: str = ".", memory_store=None, mcp_clients=None) -> None:
    registry.register(ReadFileTool(base_dir=base_dir))
    registry.register(WriteFileTool(base_dir=base_dir))
    registry.register(EditFileTool(base_dir=base_dir))

    # `export_observations` es una tool por derecho propio: el modelo la pide
    # explícitamente y el PermissionGate la aprueba. BashTool no escribe por él.
    registry.register(ExportObservationsTool(
        registry=registry, mcp_clients=mcp_clients or []))
    registry.register(BashTool())

    registry.register(LoadSkillTool(registry=registry))

    registry.register(ReadDocumentTool(base_dir=base_dir))

    if memory_store:
        registry.register(MemorySaveTool(store=memory_store))
        registry.register(MemoryRecallTool(store=memory_store))
