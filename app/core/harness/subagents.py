from typing import Any
from .tool import BaseTool, ToolResult, ToolRegistry
from .loop import AgentLoop
from .context import ContextManager
from .permissions import PermissionGate
from ..llm.base import BaseLLM


class DelegateTool(BaseTool):
    """Tool that allows the main agent to delegate tasks to a subagent."""

    def __init__(
        self,
        name: str,
        description: str,
        llm: BaseLLM,
        tools: ToolRegistry,
        system_prompt: str,
        permissions: PermissionGate | None = None,
        session_id: str | None = None,
    ):
        self.name = name
        self.description = description
        self.parameters_schema = {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "The specific task the subagent must perform."
                }
            },
            "required": ["task"]
        }
        self.llm = llm
        self.tools = tools
        self.system_prompt = system_prompt
        self.permissions = permissions
        self.session_id = session_id or f"delegate:{name}"

    async def run(self, task: str) -> ToolResult:
        ctx = ContextManager(system_prompt=self.system_prompt)

        # Comparte aprobaciones y políticas del padre, pero no auto-aprueba
        # ninguna tool: bash/write_file siguen pasando por PermissionGate.
        gate = (self.permissions or PermissionGate()).child(
            session_id=self.session_id)

        loop = AgentLoop(llm=self.llm, tools=self.tools,
                         permissions=gate, max_iterations=5)

        try:
            result = await loop.run(task, context=ctx)
            return ToolResult(
                success=True,
                content=f"[Subagent: {self.name}] Response:\n{result.final_answer}"
            )
        except Exception as e:
            return ToolResult(success=False, content="", error=f"Subagent failed: {str(e)}")
