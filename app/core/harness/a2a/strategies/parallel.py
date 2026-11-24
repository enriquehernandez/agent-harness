import asyncio
from app.core.harness.a2a.base import A2AStrategy, AgentCard
from app.core.harness.loop import AgentLoop
from app.core.harness.tool import ToolResult
from app.core.harness.context import ContextManager
from app.core.logger import logger, log_agent_flow
from app.core.llm import get_llm


class ParallelStrategy(A2AStrategy):
    """Estrategia Fan-out/Gather: lanza N agentes en paralelo y consolida."""

    def __init__(self, llm, registry: dict[str, AgentCard], permissions, agents_to_run: list[str]):
        super().__init__(llm, registry, permissions)
        self.agents_to_run = agents_to_run

    async def _run_agent(self, agent: AgentCard, task: str, context: ContextManager = None) -> tuple[str, str]:
        """Ejecuta un agente y devuelve (nombre, resultado)."""
        if agent.mode == "fork" and context:
            agent_ctx = ContextManager(system_prompt=agent.system_prompt)
            agent_ctx.messages = context.messages.copy()
        else:
            agent_ctx = ContextManager(system_prompt=agent.system_prompt)

        # Gate del subagente: comparte aprobaciones con el padre
        sub_gate = self._child_gate()

        # Resolvemos el LLM (específico del agente o el del padre)
        if agent.model:
            # Usamos el mismo proveedor, pero con el modelo específico del agente
            from app.core.config import settings
            agent_llm = get_llm(settings.LLM_PROVIDER,
                                model=agent.model)
        else:
            agent_llm = self.llm

        # 🔥 Log para el árbol de agentes
        log_agent_flow(agent.name, "start")

        loop = AgentLoop(
            llm=agent_llm,
            tools=agent.tools,
            permissions=sub_gate,
        )
        result = await loop.run(task, context=agent_ctx)

        # 🔥 Log para el árbol de agentes
        log_agent_flow(agent.name, "end")

        return agent.name, result.final_answer

    async def execute(self, task: str, context: ContextManager = None) -> ToolResult:
        tasks = []
        for name in self.agents_to_run:
            agent = self.agents.get(name)
            if not agent:
                logger.warning(f"Parallel: agente '{name}' no encontrado.")
                continue
            tasks.append(self._run_agent(agent, task, context))

        if not tasks:
            return ToolResult(success=False, content="", error="Ningún agente válido encontrado.")

        logger.debug(
            f"Parallel lanzando {len(tasks)} agentes: {self.agents_to_run}")

        # Lanzamos todos en paralelo con asyncio.gather
        results = await asyncio.gather(*tasks, return_exceptions=True)

        combined = []
        for res in results:
            if isinstance(res, Exception):
                combined.append(f"## Error\n{res}")
            else:
                name, output = res
                combined.append(f"## {name}\n{output}")

        return ToolResult(
            success=True,
            content="\n\n---\n\n".join(combined)
        )
