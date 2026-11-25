from langfuse import get_client
import os
import asyncio
from dataclasses import dataclass, field
from app.core.logger import logger
from app.core.config import settings
from app.core.pricing import get_pricing
from app.core.harness.events import AgentEvent

from ..llm.base import BaseLLM, LLMResponse
from .tool import ToolRegistry, ToolResult
from .permissions import PermissionGate, Decision
from .context import ContextManager
from .hooks import HookEvent, HookOutcome, emit_hook


def _init_langfuse():
    """Configura Langfuse solo si hay credenciales."""
    if settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_SECRET_KEY:
        os.environ["LANGFUSE_PUBLIC_KEY"] = settings.LANGFUSE_PUBLIC_KEY
        os.environ["LANGFUSE_SECRET_KEY"] = settings.LANGFUSE_SECRET_KEY
        os.environ["LANGFUSE_HOST"] = settings.LANGFUSE_HOST or "https://cloud.langfuse.com"
        return get_client()
    return None


langfuse = _init_langfuse()


@dataclass
class LoopResult:
    """Final result of a loop execution."""
    final_answer: str
    steps: int = 0
    tools_used: list[str] = field(default_factory=list)
    usage_total: dict[str, int] = field(default_factory=dict)
    cost_usd: float = 0.0


class AgentLoop:
    """ReAct Loop desacoplado de la UI. Emite eventos y usa Auto-Reflexión."""

    def __init__(
        self,
        llm: BaseLLM,
        tools: ToolRegistry,
        permissions: PermissionGate | None = None,
        max_iterations: int = 10,
        repair_counts: dict[str, int] | None = None,
        provider_name: str = "openrouter",
        critic_tool=None,
        agent_rules: str = "",
    ):
        self.llm = llm
        self.tools = tools
        self.permissions = permissions or PermissionGate()
        self.max_iterations = max_iterations
        self.repair_counts: dict[str, int] = repair_counts or {}
        self.pricing = get_pricing(provider_name)
        self.critic_tool = critic_tool
        self.agent_rules = agent_rules
        self.provider_name = provider_name
        self.last_hook_denial: str | None = None

    @staticmethod
    def _apply_hook_feedback(
        outcome: HookOutcome, ctx: ContextManager, default: str
    ) -> bool:
        """Convierte un `block` de hook en feedback temporal para el LLM."""
        if outcome.denied is not True:
            return False
        reason = outcome.reason or default
        ctx.add_user(f"[SISTEMA - FEEDBACK DE HOOK]: {reason}")
        return True

    async def _emit_stop_with_feedback(self, ctx: ContextManager) -> bool:
        outcome = await emit_hook(HookEvent(hook_event_name="Stop"))
        return self._apply_hook_feedback(
            outcome, ctx, "El hook pidió revisar la respuesta.")

    async def _emit_post_tool(
        self, ctx: ContextManager, tool_name: str, args: dict, success: bool
    ) -> None:
        outcome = await emit_hook(HookEvent(
            hook_event_name="PostToolUse", tool_name=tool_name,
            tool_input=args, success=success))
        self._apply_hook_feedback(
            outcome, ctx, "El hook pidió corregir el uso de la herramienta.")

    async def run(
        self,
        user_input: str,
        context: ContextManager | None = None,
        verbose: bool = False,
    ) -> LoopResult:
        ctx = context or ContextManager()
        await emit_hook(HookEvent(
            hook_event_name="UserPromptSubmit", prompt=user_input))
        ctx.add_user(user_input)

        tools_used: list[str] = []
        usage_total: dict[str, int] = {}
        reflection_attempts = 0

        for step in range(1, self.max_iterations + 1):
            await ctx.maybe_compact(self.llm, verbose=verbose)
            response: LLMResponse = await self.llm.chat(
                messages=ctx.get_messages(),
                tools=self.tools.all_schemas() or None,
            )
            self._accumulate_usage(usage_total, response.usage)

            if not response.tool_calls:
                final = response.content or ""

                if self.critic_tool and reflection_attempts < 2:
                    critique = await self.critic_tool.run(
                        proposed_response=final,
                        agent_rules=self.agent_rules or "Sigue las instrucciones del sistema.",
                    )
                    if critique.success and critique.content.startswith("REJECTED"):
                        reflection_attempts += 1
                        critique_msg = critique.content.replace(
                            "REJECTED:", "").strip()
                        logger.warning(
                            f"La respuesta fue rechazada por el crítico (Intento {reflection_attempts}/2).")
                        ctx.add_assistant(final)
                        ctx.add_user(
                            f"[SISTEMA - FEEDBACK DEL CRÍTICO]: Tu respuesta anterior fue rechazada por este motivo: {critique_msg}. Corrige el error y responde de nuevo.")
                        continue

                if await self._emit_stop_with_feedback(ctx):
                    continue
                ctx.add_assistant(final)
                cost = await self._calculate_total_cost(usage_total)
                return LoopResult(
                    final_answer=final,
                    steps=step,
                    tools_used=tools_used,
                    usage_total=usage_total,
                    cost_usd=cost,
                )

            ctx.add_assistant(response.content, response.tool_calls)

            for tc in response.tool_calls:
                await self._execute_tool(tc, ctx)
                tools_used.append(tc["name"])

        await self._emit_stop_with_feedback(ctx)
        cost = await self._calculate_total_cost(usage_total)
        return LoopResult(
            final_answer="[Max iterations reached without final answer]",
            steps=self.max_iterations,
            tools_used=tools_used,
            usage_total=usage_total,
            cost_usd=cost,
        )

    async def stream(
        self,
        user_input: str,
        context: ContextManager | None = None,
        verbose: bool = False,
        timeout_seconds: float | None = None,
    ):
        timeout = timeout_seconds if timeout_seconds is not None else settings.LLM_STREAM_TIMEOUT
        if timeout <= 0:
            timeout = settings.LLM_STREAM_TIMEOUT

        ctx = context or ContextManager()
        if user_input.strip():
            ctx.add_user(user_input)

        tools_used: list[str] = []
        usage_total: dict[str, int] = {}
        reflection_attempts = 0

        generation_cm = None
        generation = None
        if langfuse is not None:
            generation_cm = langfuse.start_as_current_observation(
                as_type="generation",
                name="agent_stream",
                model=getattr(self.llm, "model_name", "unknown"),
                input=user_input,
                metadata={...},
            )
            generation = generation_cm.__enter__()

        try:
            for step in range(1, self.max_iterations + 1):
                await ctx.maybe_compact(self.llm, verbose=verbose)

                full_content = ""
                tool_calls = []
                step_usage = {}

                async with asyncio.timeout(timeout):
                    async for chunk in self.llm.stream_chat(
                        messages=ctx.get_messages(),
                        tools=self.tools.all_schemas() or None,
                    ):
                        if isinstance(chunk, str):
                            full_content += chunk
                            yield AgentEvent(type="text_chunk", data={"text": chunk})
                        elif isinstance(chunk, dict):
                            if chunk.get("type") == "tool_call":
                                tool_calls.append(chunk)
                                yield AgentEvent(type="tool_start", data=chunk)
                            elif chunk.get("type") == "usage":
                                step_usage.update(chunk["usage"])

                self._accumulate_usage(usage_total, step_usage)

                if not tool_calls:
                    if self.critic_tool:
                        if reflection_attempts >= 2:
                            yield AgentEvent(type="text_chunk", data={
                                "text": "\n\n⚠️ Se alcanzó el límite de reflexiones. Aceptando respuesta actual.\n\n"})
                            if await self._emit_stop_with_feedback(ctx):
                                continue
                            cost = await self._calculate_total_cost(usage_total)
                            self._langfuse_update(
                                generation, full_content, step, tools_used, usage_total, cost)
                            ctx.add_assistant(full_content)
                            yield AgentEvent(type="result", data={
                                "final_answer": full_content,
                                "steps": step,
                                "tools_used": tools_used,
                                "usage_total": usage_total,
                                "cost_usd": cost,
                            })
                            return

                        yield AgentEvent(type="text_chunk", data={
                            "text": "\n\n*(Reflexionando...)*\n",
                            "is_correction_marker": True,
                        })
                        rules = self.agent_rules or "Sigue las instrucciones del sistema."

                        critique_result = await self.critic_tool.run(
                            proposed_response=full_content,
                            agent_rules=rules,
                        )

                        if critique_result.success and critique_result.content.startswith("REJECTED"):
                            reflection_attempts += 1
                            critique_msg = critique_result.content.replace(
                                "REJECTED:", "").strip()
                            logger.warning(
                                f"Respuesta rechazada por el crítico (Intento {reflection_attempts}/2). Reintentando...")
                            ctx.add_assistant(full_content)
                            ctx.add_user(
                                f"[SISTEMA - FEEDBACK DEL CRÍTICO]: Tu respuesta anterior fue rechazada por este motivo: {critique_msg}. Corrige el error y responde de nuevo.")
                            yield AgentEvent(type="text_chunk", data={
                                "text": f"\n\n⚠️ Corrección aplicada: {critique_msg}\n\n"})
                            continue

                    if await self._emit_stop_with_feedback(ctx):
                        continue
                    cost = await self._calculate_total_cost(usage_total)
                    self._langfuse_update(
                        generation, full_content, step, tools_used, usage_total, cost)
                    ctx.add_assistant(full_content)
                    yield AgentEvent(type="result", data={
                        "final_answer": full_content,
                        "steps": step,
                        "tools_used": tools_used,
                        "usage_total": usage_total,
                        "cost_usd": cost,
                    })
                    return

                ctx.add_assistant(full_content, tool_calls)

                for tc in tool_calls:
                    success, tool_result = await self._execute_tool(tc, ctx)
                    if self.last_hook_denial:
                        denial = self.last_hook_denial
                        self.last_hook_denial = None
                        yield AgentEvent(type="hook_denied", data={
                            "tool": tc["name"], "message": denial})
                    # 🔥 siempre, no solo success
                    tools_used.append(tc["name"])
                    yield AgentEvent(type="tool_end", data={
                        "tool": tc["name"],
                        "success": success,
                        "result": tool_result,
                    })

            # 🔥 Si el for termina sin return, se agotó max_iterations
            await self._emit_stop_with_feedback(ctx)
            cost = await self._calculate_total_cost(usage_total)
            self._langfuse_update(
                generation, "", self.max_iterations, tools_used, usage_total, cost)
            yield AgentEvent(type="result", data={
                "final_answer": (
                    f"[Max iterations ({self.max_iterations}) reached without final answer]"
                ),
                "steps": self.max_iterations,
                "tools_used": tools_used,
                "usage_total": usage_total,
                "cost_usd": cost,
            })

        except (asyncio.TimeoutError, TimeoutError):
            self._langfuse_error(generation, "Timeout")
            await emit_hook(HookEvent(hook_event_name="StopFailure"))
            yield AgentEvent(type="error", data={
                "message": f"Timeout: el stream superó {timeout}s",
                "is_timeout": True,
            })
            return
        except Exception as e:
            logger.error(f"AgentLoop.stream error: {e}", exc_info=True)
            self._langfuse_error(generation, str(e))
            await emit_hook(HookEvent(hook_event_name="StopFailure"))
            yield AgentEvent(type="error", data={"message": str(e), "is_timeout": False})
            return
        finally:
            if generation_cm is not None:
                try:
                    generation_cm.__exit__(None, None, None)
                except Exception:
                    pass

    @staticmethod
    def _langfuse_update(generation, full_content, step, tools_used, usage_total, cost_total):
        if generation is None:
            return
        try:
            generation.update(
                output=full_content,
                metadata={"steps": step, "tools_used": tools_used},
                usage_details={
                    "prompt_tokens": usage_total.get("prompt_tokens", 0),
                    "completion_tokens": usage_total.get("completion_tokens", 0),
                    "total_tokens": usage_total.get("total_tokens", 0),
                    "input": usage_total.get("prompt_tokens", 0),
                    "output": usage_total.get("completion_tokens", 0),
                },
                cost_details={
                    "input": cost_total * 0.5,
                    "output": cost_total * 0.5,
                },
            )
        except Exception as e:
            logger.warning(f"Langfuse update falló: {e}")

    @staticmethod
    def _langfuse_error(generation, message):
        if generation is None:
            return
        try:
            generation.update(output=f"Error: {message}", metadata={
                              "error": message})
        except Exception:
            pass

    async def _execute_tool(self, tc: dict, ctx: ContextManager) -> tuple[bool, ToolResult | None]:
        tool_name = tc["name"]
        args = tc["arguments"]
        tool_call_id = tc["id"]

        self.last_hook_denial = None
        hook_outcome = await emit_hook(HookEvent(
            hook_event_name="PreToolUse", tool_name=tool_name, tool_input=args))
        if hook_outcome.denied is True:
            self.last_hook_denial = (
                hook_outcome.reason
                or f"El hook bloqueó la herramienta '{tool_name}'."
            )
            ctx.add_tool_result(tool_call_id, f"ERROR: {self.last_hook_denial}")
            await self._emit_post_tool(ctx, tool_name, args, False)
            return False, None

        decision = await self.permissions.check(tool_name, args)
        if decision == Decision.DENY:
            ctx.add_tool_result(
                tool_call_id, f"ERROR: Permission denied for '{tool_name}'.")
            await self._emit_post_tool(ctx, tool_name, args, False)
            return False, None

        tool = self.tools.get(tool_name)
        if tool is None:
            ctx.add_tool_result(tool_call_id, f"Tool '{tool_name}' not found.")
            await self._emit_post_tool(ctx, tool_name, args, False)
            return False, None

        try:
            result = await tool.run(**args)
        except Exception as e:
            result = ToolResult(success=False, content="",
                                error=f"Error inesperado: {e}")

        if result.success:
            self.repair_counts.pop(tool_name, None)
            ctx.add_tool_result(tool_call_id, result.content)
        else:
            attempts = self.repair_counts.get(tool_name, 0) + 1
            self.repair_counts[tool_name] = attempts
            logger.warning(
                f"⚠️ Tool '{tool_name}' falló ({attempts}/3): {result.error}")

            if attempts >= 3:
                ctx.add_tool_result(
                    tool_call_id,
                    f"[SISTEMA: La herramienta {tool_name} falló {attempts} veces. Detente y pide ayuda al usuario.]",
                )
            else:
                ctx.add_tool_result(
                    tool_call_id,
                    f"Error: {result.error}. (Reintento {attempts}/3. Si no puedes recuperarte, pregunta al usuario).",
                )

        await self._emit_post_tool(ctx, tool_name, args, result.success)
        return result.success, result

    @staticmethod
    def _accumulate_usage(total: dict[str, int], usage: dict[str, int]) -> None:
        for k, v in usage.items():
            total[k] = total.get(k, 0) + v

    async def _calculate_total_cost(self, usage: dict[str, int]) -> float:
        prompt = usage.get("prompt_tokens", 0)
        completion = usage.get("completion_tokens", 0)
        model = getattr(self.llm, "model_name", "unknown")
        return await self.pricing.get_cost(model, prompt, completion)

    async def _calculate_cost(self, usage: dict[str, int]) -> dict:
        prompt = usage.get("prompt_tokens", 0)
        completion = usage.get("completion_tokens", 0)
        model = getattr(self.llm, "model_name", "unknown")
        return await self.pricing.get_cost_pricing(model, prompt, completion)
