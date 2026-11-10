from typing import Any
from .tool import BaseTool, ToolResult, ToolRegistry
from .loop import AgentLoop
from .context import ContextManager
from .permissions import PermissionGate, Decision
from ..llm.base import BaseLLM


class DelegateTool(BaseTool):
    """Herramienta que permite al agente principal delegar tareas a un subagente."""

    def __init__(
        self,
        name: str,
        description: str,
        llm: BaseLLM,
        tools: ToolRegistry,
        system_prompt: str
    ):
        self.name = name
        self.description = description
        self.parameters_schema = {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "La tarea específica que el subagente debe realizar."
                }
            },
            "required": ["task"]
        }
        self.llm = llm
        self.tools = tools
        # El subagente tiene su propio prompt de sistema
        self.system_prompt = system_prompt

    async def run(self, task: str) -> ToolResult:
        # 1. Creamos un contexto aislado para el subagente
        ctx = ContextManager(system_prompt=self.system_prompt)

        # 2. El subagente hereda las herramientas pero con un PermissionGate que permite todo
        # (Asumimos que el agente principal ya pidió permiso al usuario para delegar)
        gate = PermissionGate()
        for tool in self.tools.names():
            gate.policies[tool] = Decision.ALLOW

        loop = AgentLoop(llm=self.llm, tools=self.tools,
                         permissions=gate, max_iterations=5)

        try:
            # 3. Ejecutamos al subagente
            result = await loop.run(task, context=ctx)

            # 4. Devolvemos el resumen final al agente principal
            return ToolResult(
                success=True,
                content=f"[Subagente: {self.name}] Respuesta:\n{result.final_answer}"
            )
        except Exception as e:
            return ToolResult(success=False, content="", error=f"El subagente falló: {str(e)}")
