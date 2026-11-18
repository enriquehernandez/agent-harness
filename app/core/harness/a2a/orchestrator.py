from typing import Any
from app.core.harness.tool import BaseTool, ToolResult
from app.core.harness.a2a.base import AgentCard
from app.core.harness.a2a.strategies.supervisor import SupervisorStrategy
from app.core.harness.a2a.strategies.sequential import SequentialStrategy
from app.core.harness.a2a.strategies.parallel import ParallelStrategy
from app.core.harness.a2a.strategies.swarm import SwarmStrategy
from app.core.config import settings
from app.core.logger import logger


class OrchestratorTool(BaseTool):
    """La tool que el agente principal usa para delegar en el sistema A2A."""

    def __init__(self, llm, agents: dict[str, AgentCard], permissions):
        self.name = "delegate_task"
        self.description = (
            "Delega una tarea compleja a un sistema de subagentes expertos. "
            "Usa esto cuando la tarea requiera múltiples pasos o especialización."
        )
        self.parameters_schema = {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "La tarea a delegar (descripción completa)."
                }
            },
            "required": ["task"]
        }
        self.llm = llm
        self.agents = agents
        self.permissions = permissions

    async def run(self, task: str, **kwargs) -> ToolResult:
        strategy_name = settings.A2A_STRATEGY.lower()

        try:
            if strategy_name == "supervisor":
                strategy = SupervisorStrategy(
                    self.llm, self.agents, self.permissions)
            elif strategy_name == "sequential":
                sequence = [s.strip()
                            for s in settings.A2A_SEQUENCE.split(",") if s.strip()]
                strategy = SequentialStrategy(
                    self.llm, self.agents, self.permissions, sequence)
            elif strategy_name == "parallel":
                agents_to_run = [
                    s.strip() for s in settings.A2A_PARALLEL_AGENTS.split(",") if s.strip()]
                strategy = ParallelStrategy(
                    self.llm, self.agents, self.permissions, agents_to_run)
            elif strategy_name == "swarm":
                strategy = SwarmStrategy(
                    self.llm, self.agents, self.permissions,
                    start_agent=settings.A2A_SWARM_START
                )
            else:
                return ToolResult(
                    success=False, content="",
                    error=f"Estrategia A2A desconocida: {strategy_name}"
                )

            # Pasamos un contexto vacío (el orchestrator no tiene historial propio)
            return await strategy.execute(task, context=None)

        except Exception as e:
            logger.error(f"Error en OrchestratorTool: {e}", exc_info=True)
            return ToolResult(success=False, content="", error=str(e))
