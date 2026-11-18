import json
from app.core.harness.a2a.base import A2AStrategy, AgentCard
from app.core.harness.loop import AgentLoop
from app.core.harness.tool import ToolResult
from app.core.harness.context import ContextManager
from app.core.harness.permissions import PermissionGate
from app.core.logger import logger, log_agent_flow
from app.core.config import settings
from app.core.llm import get_llm


class SwarmStrategy(A2AStrategy):
    """
    Estrategia Swarm (Handoff dinámico): los agentes se pasan el control
    entre sí hasta que uno decida que la tarea está terminada.
    """

    def __init__(self, llm, registry: dict[str, AgentCard], permissions, start_agent: str = None):
        super().__init__(llm, registry, permissions)
        self.start_agent = start_agent or list(registry.keys())[0]

    def _load_persisted_permissions(self) -> set[str]:
        perm_file = settings.permissions_file
        if not perm_file.exists():
            return set()
        try:
            data = json.loads(perm_file.read_text())
            return set(data.get("session_allowed", []))
        except Exception:
            return set()

    async def execute(self, task: str, context: ContextManager = None) -> ToolResult:
        current_agent_name = self.start_agent
        current_input = task
        history = []
        visited = set()
        max_hops = 5
        persisted = self._load_persisted_permissions()

        for hop in range(max_hops):
            agent = self.agents.get(current_agent_name)
            if not agent:
                logger.warning(
                    f"Swarm: agente '{current_agent_name}' no encontrado.")
                break

            logger.info(
                f"Swarm [hop {hop + 1}/{max_hops}]: ejecutando '{current_agent_name}' (model={agent.model or 'default'})")

            # 🔥 Log para el árbol de agentes
            log_agent_flow(current_agent_name, "start")

            # Preparamos el contexto
            if agent.mode == "fork" and context:
                agent_ctx = ContextManager(system_prompt=agent.system_prompt)
                agent_ctx.messages = context.messages.copy()
            else:
                agent_ctx = ContextManager(system_prompt=agent.system_prompt)

            # Inyectamos el historial previo
            if history:
                agent_ctx.add_user(
                    f"Historial de la tarea hasta ahora:\n{chr(10).join(history)}"
                )

            # Creamos un PermissionGate específico para este subagente
            sub_gate = PermissionGate(
                ask_user=self.permissions.ask_user if self.permissions else None)
            if self.permissions and hasattr(self.permissions, "policies"):
                sub_gate.policies = self.permissions.policies.copy()
            for pattern in persisted:
                sub_gate.session_allowed.add(pattern)

            # Resolvemos el LLM (específico del agente o el del padre)
            if agent.model:
                # Usamos el mismo proveedor, pero con el modelo específico del agente
                agent_llm = get_llm(settings.LLM_PROVIDER,
                                    model=agent.model)
            else:
                agent_llm = self.llm

            # Ejecutamos el agente con el sub_gate
            loop = AgentLoop(
                llm=agent_llm,
                tools=agent.tools,
                permissions=sub_gate,
            )
            result = await loop.run(current_input, context=agent_ctx)
            output = result.final_answer

            logger.debug(
                f"Swarm: '{current_agent_name}' respondió: {output[:100]}...")

            # 🔥 Log para el árbol de agentes
            log_agent_flow(current_agent_name, "end")

            history.append(f"{current_agent_name}: {output}")
            visited.add(current_agent_name)

            # El agente puede pedir handoff a otro agente
            handoff_target = None
            for line in output.split("\n"):
                if line.strip().upper().startswith("HANDOFF:"):
                    handoff_target = line.split(":", 1)[1].strip().lower()
                    break

            if handoff_target:
                if handoff_target in self.agents and handoff_target not in visited:
                    logger.info(
                        f"Swarm: handoff de {current_agent_name} -> {handoff_target}")

                    # 🔥 Log para el árbol de agentes
                    log_agent_flow(handoff_target, "handoff")

                    current_agent_name = handoff_target
                    current_input = output
                    continue
                else:
                    logger.warning(
                        f"Swarm: handoff inválido o repetido: {handoff_target}")
                    break

            logger.info(
                f"Swarm: {current_agent_name} resolvió la tarea (sin handoff).")
            return ToolResult(
                success=True,
                content="\n\n---\n\n".join(history)
            )

        logger.warning(f"Swarm: límite de {max_hops} saltos alcanzado.")
        return ToolResult(
            success=True,
            content="\n\n---\n\n".join(history) +
            f"\n\n⚠️ Límite de {max_hops} saltos alcanzado."
        )
