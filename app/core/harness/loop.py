from dataclasses import dataclass, field
from typing import Any

from ..llm.base import BaseLLM, LLMResponse
from .tool import ToolRegistry
from .permissions import PermissionGate, Decision
from .context import ContextManager


@dataclass
class LoopResult:
    """Resultado final de una ejecución del bucle."""
    final_answer: str
    steps: int = 0
    tools_used: list[str] = field(default_factory=list)
    usage_total: dict[str, int] = field(default_factory=dict)


class AgentLoop:
    """Bucle ReAct: LLM -> tools -> LLM -> ... -> respuesta final."""

    def __init__(
        self,
        llm: BaseLLM,
        tools: ToolRegistry,
        permissions: PermissionGate | None = None,
        max_iterations: int = 10,
    ):
        self.llm = llm
        self.tools = tools
        self.permissions = permissions or PermissionGate()
        self.max_iterations = max_iterations

    async def run(
        self,
        user_input: str,
        context: ContextManager | None = None,
    ) -> LoopResult:
        ctx = context or ContextManager()
        ctx.add_user(user_input)

        tools_used: list[str] = []
        usage_total: dict[str, int] = {}

        for step in range(1, self.max_iterations + 1):
            # 🔥 NUEVO: Verificar y compactar contexto antes de llamar al LLM
            await ctx.maybe_compact(self.llm)

            response: LLMResponse = await self.llm.chat(
                messages=ctx.get_messages(),
                tools=self.tools.all_schemas() or None,
            )
            self._accumulate_usage(usage_total, response.usage)

            if not response.tool_calls:
                final = response.content or ""
                ctx.add_assistant(final)
                return LoopResult(
                    final_answer=final,
                    steps=step,
                    tools_used=tools_used,
                    usage_total=usage_total,
                )

            ctx.add_assistant(response.content, response.tool_calls)

            for tc in response.tool_calls:
                tool_name = tc["name"]
                args = tc["arguments"]
                tool_call_id = tc["id"]

                decision = await self.permissions.check(tool_name, args)

                if decision == Decision.DENY:
                    ctx.add_tool_result(
                        tool_call_id,
                        f"ERROR: El usuario denegó el permiso para ejecutar '{tool_name}'."
                    )
                    continue

                tool = self.tools.get(tool_name)
                if tool is None:
                    ctx.add_tool_result(
                        tool_call_id, f"Tool '{tool_name}' not found.")
                    continue

                result = await tool.run(**args)
                tools_used.append(tool_name)

                if result.success:
                    ctx.add_tool_result(tool_call_id, result.content)
                else:
                    ctx.add_tool_result(
                        tool_call_id, f"Error: {result.error}")

        return LoopResult(
            final_answer="[Max iterations reached without final answer]",
            steps=self.max_iterations,
            tools_used=tools_used,
            usage_total=usage_total,
        )

    @staticmethod
    def _accumulate_usage(total: dict[str, int], usage: dict[str, int]) -> None:
        for k, v in usage.items():
            total[k] = total.get(k, 0) + v
