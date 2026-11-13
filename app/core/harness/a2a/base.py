from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any
from app.core.harness.tool import ToolRegistry, ToolResult


@dataclass
class AgentCard:
    """Define las capacidades de un subagente (estándar A2A)."""
    name: str
    description: str
    system_prompt: str
    tools: ToolRegistry
    # 🔥 Modo de contexto: "fork" (hereda historial) o "isolated" (limpio)
    mode: str = "isolated"


class A2AStrategy(ABC):
    """Interfaz para las estrategias de orquestación Agent-to-Agent."""

    def __init__(self, llm, registry: dict[str, AgentCard], permissions):
        self.llm = llm
        self.agents = registry
        self.permissions = permissions

    @abstractmethod
    async def execute(self, task: str, context: Any = None) -> ToolResult:
        """Ejecuta la tarea usando los subagentes configurados."""
        ...
