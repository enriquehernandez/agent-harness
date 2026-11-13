from app.core.harness.a2a.base import A2AStrategy, AgentCard
from app.core.harness.loop import AgentLoop
from app.core.harness.tool import ToolResult
from app.core.harness.context import ContextManager
from app.core.harness.permissions import PermissionGate
from app.core.logger import logger
import json
from app.core.config import settings


class SequentialStrategy(A2AStrategy):
    """Estrategia pipeline: los agentes se ejecutan en orden predefinido."""

    def __init__(self, llm, registry: dict[str, AgentCard], permissions, sequence: list[str]):
        super().__init__(llm, registry, permissions)
        self.sequence = sequence

    def _load_persisted_permissions(self) -> set[str]:
        """Lee los permisos persistidos de .harness/permissions.json."""
        perm_file = settings.permissions_file
        if not perm_file.exists():
            return set()
        try:
            data = json.loads(perm_file.read_text())
            return set(data.get("session_allowed", []))
        except Exception:
            return set()

    async def execute(self, task: str, context: ContextManager = None) -> ToolResult:
        current_input = task
        history = []

        # 🔥 Cargamos los permisos persistidos UNA VEZ para todos los agentes
        persisted = self._load_persisted_permissions()

        for agent_name in self.sequence:
            agent = self.agents.get(agent_name)
            if not agent:
                logger.warning(
                    f"Sequential: agente '{agent_name}' no encontrado.")
                continue

            logger.info(f"Sequential ejecutando: {agent_name}")

            # Preparamos el contexto según el modo del agente
            if agent.mode == "fork" and context:
                agent_ctx = ContextManager(system_prompt=agent.system_prompt)
                agent_ctx.messages = context.messages.copy()
            else:
                agent_ctx = ContextManager(system_prompt=agent.system_prompt)

            # 🔥 Creamos un PermissionGate específico para este subagente
            sub_gate = PermissionGate(ask_user=self.permissions.ask_user)

            # 🔥 HEREDAMOS LAS POLÍTICAS DEL PADRE (esto es lo que faltaba)
            if self.permissions and hasattr(self.permissions, "policies"):
                sub_gate.policies = self.permissions.policies.copy()

            # 🔥 Inyectamos los permisos persistidos (del JSON)
            for pattern in persisted:
                sub_gate.session_allowed.add(pattern)

            # Ejecutamos el agente
            loop = AgentLoop(
                llm=self.llm,
                tools=agent.tools,
                permissions=sub_gate,
            )
            result = await loop.run(current_input, context=agent_ctx)

            # El output del agente actual se convierte en el input del siguiente
            history.append(f"## {agent_name}\n{result.final_answer}")
            current_input = result.final_answer

        return ToolResult(
            success=True,
            content="\n\n---\n\n".join(history)
        )
