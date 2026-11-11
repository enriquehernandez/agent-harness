from dataclasses import dataclass, field
from typing import Any

from ..llm.base import BaseLLM, LLMResponse
from .tool import ToolRegistry
from .permissions import PermissionGate, Decision
from .context import ContextManager


@dataclass
class LoopResult:
    """Final result of a loop execution."""
    final_answer: str
    steps: int = 0
    tools_used: list[str] = field(default_factory=list)
    usage_total: dict[str, int] = field(default_factory=dict)


class AgentLoop:
    """ReAct Loop: LLM -> tools -> LLM -> ... -> final answer."""

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
        self.repair_counts: dict[str, int] = {}

    async def run(
        self,
        user_input: str,
        context: ContextManager | None = None,
        verbose: bool = False,
    ) -> LoopResult:
        ctx = context or ContextManager()
        ctx.add_user(user_input)

        tools_used: list[str] = []
        usage_total: dict[str, int] = {}

        for step in range(1, self.max_iterations + 1):
            await ctx.maybe_compact(self.llm, verbose=verbose)

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
                        f"ERROR: User denied permission to execute '{tool_name}'."
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
                    # Reseteamos el contador
                    self.repair_counts.pop(tool_name, None)
                else:
                    attempts = self.repair_counts.get(tool_name, 0) + 1
                    self.repair_counts[tool_name] = attempts

                    if attempts >= 3:
                        error_msg = f"[SISTEMA: La herramienta {tool_name} falló {attempts} veces. Detente y pide ayuda al usuario.]"
                        ctx.add_tool_result(tool_call_id, error_msg)
                    else:
                        error_msg = f"Error: {result.error}. (Reintento {attempts}/3. Si no puedes recuperarte, pregunta al usuario)."
                        ctx.add_tool_result(tool_call_id, error_msg)

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

    async def stream(self, user_input: str, context: ContextManager | None = None, verbose: bool = False):  # pragma: no cover
        """
        Versión streaming del AgentLoop. 
        Hace yield de los chunks de texto a medida que llegan.
        """
        ctx = context or ContextManager()
        # 🔥 Solo añadimos el mensaje si no está vacío
        if user_input.strip():
            ctx.add_user(user_input)

        tools_used: list[str] = []
        usage_total: dict[str, int] = {}

        for step in range(1, self.max_iterations + 1):
            await ctx.maybe_compact(self.llm, verbose=verbose)

            # 🔥 Usamos stream_chat en lugar de chat
            full_content = ""
            async for chunk in self.llm.stream_chat(
                messages=ctx.get_messages(),
                tools=self.tools.all_schemas() or None,
            ):
                full_content += chunk
                yield chunk  # 🔥 Enviamos el chunk a la TUI

            # Si el LLM no soporta tool calls en streaming, hacemos un fallback
            # (por simplicidad, asumimos que el streaming no tiene tool_calls)
            if not full_content:
                break

            # Si el agente termina sin tools, devolvemos el resultado
            ctx.add_assistant(full_content)
            return

        # Si se agotan las iteraciones
        ctx.add_assistant("[Max iterations reached]")
