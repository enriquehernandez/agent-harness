import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Iterable
from app.core.config import settings
from app.core.harness.permissions import PermissionGate
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
    model: str | None = None


class A2AStrategy(ABC):
    """Interfaz para las estrategias de orquestación Agent-to-Agent."""

    def __init__(self, llm, registry: dict[str, AgentCard], permissions):
        self.llm = llm
        self.agents = registry
        self.permissions = permissions

    def _load_persisted_permissions(self) -> set[str]:
        """Lee los patrones aprobados de `.harness/permissions.json`."""
        perm_file = settings.permissions_file
        if not perm_file.exists():
            return set()
        try:
            data = json.loads(perm_file.read_text())
            return set(data.get("session_allowed", []))
        except Exception:
            return set()

    def _child_gate(self, allow: Iterable[str] = ()) -> PermissionGate:
        """Construye el gate del subagente compartiendo estado con el padre.

        Las aprobaciones persistidas se cargan también aquí para que cualquier
        estrategia (incluida `parallel`) las respete al ejecutarse.
        """
        gate = (self.permissions.child(allow=allow) if self.permissions
                else PermissionGate())
        for pattern in self._load_persisted_permissions():
            gate.session_allowed.add(pattern)
        return gate

    @abstractmethod
    async def execute(self, task: str, context: Any = None) -> ToolResult:
        """Ejecuta la tarea usando los subagentes configurados."""
        ...
