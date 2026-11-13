import asyncio
from dataclasses import dataclass, field
from typing import Any

from app.core.logger import logger

from ..llm.base import BaseLLM, LLMResponse
from .tool import ToolRegistry
from .permissions import PermissionGate, Decision
from .context import ContextManager
from app.core.config import settings
from app.core.pricing import get_pricing


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
        repair_counts: dict[str, int] | None = None,
        provider_name: str = "openrouter",
    ):
        self.llm = llm
        self.tools = tools
        self.permissions = permissions or PermissionGate()
        self.max_iterations = max_iterations
        # 🔥 Inicializamos desde el estado previo o vacío
        self.repair_counts: dict[str, int] = repair_counts or {}
        self.pricing = get_pricing(provider_name)

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

    async def stream(
        self,
        user_input: str,
        context: ContextManager | None = None,
        verbose: bool = False,
        timeout_seconds: float | None = None,  # 🔥 Nuevo
    ):
        timeout = timeout_seconds if timeout_seconds is not None else settings.LLM_STREAM_TIMEOUT
        ctx = context or ContextManager()
        if user_input.strip():
            ctx.add_user(user_input)

        tools_used: list[str] = []
        usage_total: dict[str, int] = {}
        repair_counts: dict[str, int] = {}  # 🔥 Añadido para el stream

        try:
            for step in range(1, self.max_iterations + 1):
                await ctx.maybe_compact(self.llm, verbose=verbose)

                full_content = ""
                tool_calls = []
                step_usage = {}

                # 🔥 Timeout por step
                async with asyncio.timeout(timeout):
                    async for chunk in self.llm.stream_chat(
                        messages=ctx.get_messages(),
                        tools=self.tools.all_schemas() or None,
                    ):
                        if isinstance(chunk, str):
                            full_content += chunk
                            yield chunk
                        elif isinstance(chunk, dict):
                            if chunk.get("type") == "tool_call":
                                tool_calls.append(chunk)
                                yield chunk
                            elif chunk.get("type") == "usage":
                                step_usage.update(chunk["usage"])

                self._accumulate_usage(usage_total, step_usage)

                if not tool_calls:
                    ctx.add_assistant(full_content)
                    yield {
                        "type": "result",
                        "final_answer": full_content,
                        "steps": step,
                        "tools_used": tools_used,
                        "usage_total": usage_total,
                        "cost_usd": await self._calculate_cost(usage_total),
                    }
                    return

                ctx.add_assistant(full_content, tool_calls)

                for tc in tool_calls:
                    tool_name = tc["name"]
                    args = tc["arguments"]
                    tool_call_id = tc["id"]

                    decision = await self.permissions.check(tool_name, args)
                    if decision == Decision.DENY:
                        ctx.add_tool_result(
                            tool_call_id, f"ERROR: Permission denied for '{tool_name}'.")
                        continue

                    tool = self.tools.get(tool_name)
                    if tool is None:
                        ctx.add_tool_result(
                            tool_call_id, f"Tool '{tool_name}' not found.")
                        continue

                    result = await tool.run(**args)
                    tools_used.append(tool_name)

                    # 🔥 Lógica de repair_counts inyectada
                    if result.success:
                        repair_counts.pop(tool_name, None)
                        ctx.add_tool_result(tool_call_id, result.content)
                    else:
                        attempts = repair_counts.get(tool_name, 0) + 1
                        repair_counts[tool_name] = attempts

                        if attempts >= 3:
                            ctx.add_tool_result(
                                tool_call_id,
                                f"[SISTEMA: La herramienta {tool_name} falló {attempts} veces. Detente y pide ayuda al usuario.]"
                            )
                        else:
                            ctx.add_tool_result(
                                tool_call_id,
                                f"Error: {result.error}. (Reintento {attempts}/3. Si no puedes recuperarte, pregunta al usuario)."
                            )

        except (asyncio.TimeoutError, TimeoutError):
            yield {
                "type": "result",
                "final_answer": f"[Timeout: el stream superó {timeout}s]",
                "steps": 0,
                "tools_used": tools_used,
                "usage_total": usage_total,
                "timeout": True,
            }
            return

        yield {
            "type": "result",
            "final_answer": "[Max iterations reached without final answer]",
            "steps": self.max_iterations,
            "tools_used": tools_used,
            "usage_total": usage_total,
            "cost_usd": await self._calculate_cost(usage_total),
        }

    async def _calculate_cost(self, usage: dict[str, int]) -> float:
        prompt = usage.get("prompt_tokens", 0)
        completion = usage.get("completion_tokens", 0)
        model = getattr(self.llm, "model_name", "unknown")
        logger.debug(f"Calculando coste para modelo: '{model}'")
        return await self.pricing.get_cost(model, prompt, completion)
