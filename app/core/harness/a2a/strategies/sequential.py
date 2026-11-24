from app.core.harness.a2a.base import A2AStrategy, AgentCard
from app.core.harness.loop import AgentLoop
from app.core.harness.tool import ToolResult
from app.core.harness.context import ContextManager
from app.core.logger import logger, log_agent_flow
from app.core.config import settings
from app.core.llm import get_llm


class SequentialStrategy(A2AStrategy):
    """Estrategia pipeline: los agentes se ejecutan en orden predefinido."""

    def __init__(self, llm, registry: dict[str, AgentCard], permissions, sequence: list[str]):
        super().__init__(llm, registry, permissions)
        self.sequence = sequence

    async def execute(self, task: str, context: ContextManager = None) -> ToolResult:
        current_input = task
        history = []

        for agent_name in self.sequence:
            agent = self.agents.get(agent_name)
            if not agent:
                logger.warning(
                    f"Sequential: agente '{agent_name}' no encontrado.")
                continue

            logger.debug(
                f"Sequential ejecutando: {agent_name} (model={agent.model or 'default'})")

            # 🔥 Log para el árbol de agentes
            log_agent_flow(agent_name, "start")

            # Preparamos el contexto
            agent_ctx = self._fork_context(agent, context)

            # Gate del subagente: comparte aprobaciones con el padre
            sub_gate = self._child_gate()

            # Resolvemos el LLM (específico del agente o el del padre)
            if agent.model:
                # Usamos el mismo proveedor, pero con el modelo específico del agente
                agent_llm = get_llm(settings.LLM_PROVIDER,
                                    model=agent.model)
            else:
                agent_llm = self.llm

            # Ejecutamos el agente
            loop = AgentLoop(
                llm=agent_llm,
                tools=agent.tools,
                permissions=sub_gate,
            )
            result = await loop.run(current_input, context=agent_ctx)

            # 🔥 Log para el árbol de agentes
            log_agent_flow(agent_name, "end")

            history.append(f"## {agent_name}\n{result.final_answer}")
            current_input = result.final_answer

        return ToolResult(
            success=True,
            content="\n\n---\n\n".join(history)
        )
