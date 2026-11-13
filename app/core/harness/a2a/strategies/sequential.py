from app.core.harness.a2a.base import A2AStrategy, AgentCard
from app.core.harness.loop import AgentLoop
from app.core.harness.tool import ToolResult
from app.core.harness.context import ContextManager
from app.core.logger import logger


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

            logger.info(f"Sequential ejecutando: {agent_name}")

            # Preparamos el contexto
            if agent.mode == "fork" and context:
                agent_ctx = ContextManager(system_prompt=agent.system_prompt)
                agent_ctx.messages = context.messages.copy()
            else:
                agent_ctx = ContextManager(system_prompt=agent.system_prompt)

            # Ejecutamos el agente
            loop = AgentLoop(
                llm=self.llm,
                tools=agent.tools,
                permissions=self.permissions
            )
            result = await loop.run(current_input, context=agent_ctx)

            # El output del agente actual se convierte en el input del siguiente
            history.append(f"## {agent_name}\n{result.final_answer}")
            current_input = result.final_answer

        return ToolResult(
            success=True,
            content="\n\n---\n\n".join(history)
        )
