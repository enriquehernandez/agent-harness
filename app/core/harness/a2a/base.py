import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Iterable
from app.core.config import settings
from app.core.harness.context import ContextManager
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

    def _fork_context(
        self, agent: AgentCard, context: ContextManager | None
    ) -> ContextManager:
        """Prepara el contexto del subagente.

        En modo `fork` hereda el historial del padre (mensajes user/assistant/tool),
        pero mantiene el `system_prompt` del `AgentCard`: las instrucciones del
        orquestador no deben convertirse en instrucciones del subagente. Tras el
        historial heredado añade un preámbulo para que el subagente distinga ese
        contexto de la tarea que `AgentLoop.run()` añadirá a continuación.
        """
        agent_ctx = ContextManager(system_prompt=agent.system_prompt)
        if agent.mode == "fork" and context:
            inherited = [
                message for message in context.messages
                if message.get("role") != "system"
            ]
            if inherited:
                agent_ctx.messages.extend(inherited)
                agent_ctx.add_user(
                    "Continúas la tarea iniciada por el agente principal. "
                    "El historial anterior es contexto heredado; tu tarea "
                    "se indica en el siguiente mensaje."
                )
        return agent_ctx

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
