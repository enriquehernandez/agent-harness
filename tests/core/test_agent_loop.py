import asyncio
import json
import sys
from pathlib import Path
from typing import AsyncIterator

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from app.core.harness.loop import AgentLoop
from app.core.harness.permissions import PermissionGate, Decision
from app.core.harness.tool import FunctionTool, ToolRegistry, ToolResult
from app.core.llm.base import BaseLLM, LLMResponse
from app.core.harness.context import ContextManager
from app.core.llm.providers.fake import FakeLLM
from app.core.harness.events import AgentEvent
from app.core.harness.hooks import HookManager, HookOutcome


class HangingLLM(BaseLLM):
    async def chat(self, messages, tools=None, **kwargs) -> LLMResponse:
        pass

    async def stream_chat(self, messages, tools=None, **kwargs) -> AsyncIterator:
        yield "Inicio..."
        await asyncio.sleep(2)
        yield "Fin"

    def count_tokens(self, text: str) -> int: return 0
    @property
    def supports_tool_calling(self) -> bool: return True
    @property
    def max_context_window(self) -> int: return 1000


@pytest.mark.asyncio
async def test_loop_stream_timeout():
    """Cubre el except de TimeoutError en AgentLoop.stream."""
    llm = HangingLLM()
    loop = AgentLoop(llm=llm, tools=ToolRegistry())
    ctx = ContextManager()

    events = []
    async for event in loop.stream("Hola", context=ctx, timeout_seconds=0.1):
        events.append(event)

    # El último evento debe ser de tipo "error"
    last_event = events[-1]
    assert isinstance(last_event, AgentEvent)
    assert last_event.type == "error"
    assert last_event.data.get("is_timeout") is True


@pytest.mark.asyncio
async def test_loop_tool_not_found(fake_llm, basic_registry):
    fake_llm._responses = [
        LLMResponse(
            tool_calls=[{"id": "c1", "name": "ghost_tool", "arguments": {}}]),
        LLMResponse(content="Sorry, that tool does not exist.")
    ]
    gate = PermissionGate(policies={"ghost_tool": Decision.ALLOW})
    loop = AgentLoop(llm=fake_llm, tools=basic_registry, permissions=gate)
    result = await loop.run("Use the ghost tool")
    # Verificamos que al menos responde con el mensaje esperado
    assert "does not exist" in result.final_answer


@pytest.mark.asyncio
async def test_loop_stream_with_tools(fake_llm, basic_registry):
    """Cubre el método stream() del AgentLoop."""
    step_counter = {"n": 0}

    async def mock_stream(*args, **kwargs):
        step_counter["n"] += 1
        if step_counter["n"] == 1:
            # Step 1: pide tool
            yield "Pensando..."
            yield {"type": "tool_call", "id": "c1", "name": "add",
                   "arguments": {"a": 1, "b": 2}}
            yield {"type": "usage", "usage": {"total_tokens": 100}}
        else:
            # Step 2: sin tool_calls → el loop emite "result"
            yield "El resultado es 3."
            yield {"type": "usage", "usage": {"total_tokens": 50}}

    with patch.object(fake_llm, "stream_chat", side_effect=mock_stream):
        with patch.object(fake_llm, "model_name", "openai/gpt-4o"):
            gate = PermissionGate(policies={"add": Decision.ALLOW})
            loop = AgentLoop(
                llm=fake_llm, tools=basic_registry, permissions=gate)

            events = []
            async for event in loop.stream("Suma 1 y 2"):
                events.append(event)

    assert any(isinstance(e, AgentEvent) and e.type ==
               "text_chunk" for e in events)
    assert any(isinstance(e, AgentEvent) and e.type ==
               "tool_start" for e in events)
    assert any(isinstance(e, AgentEvent) and e.type ==
               "tool_end" for e in events)
    assert any(isinstance(e, AgentEvent)
               and e.type == "result" for e in events)


@pytest.mark.asyncio
async def test_loop_stream_edge_cases(fake_llm, basic_registry):
    """Cubre las ramas de error del stream()."""

    # 1. Cubre if not tool_calls
    async def mock_stream_no_tools(*args, **kwargs):
        yield "Solo texto"

    with patch.object(fake_llm, "stream_chat", side_effect=mock_stream_no_tools):
        with patch.object(fake_llm, "model_name", "openai/gpt-4o"):
            gate = PermissionGate(policies={})
            loop = AgentLoop(
                llm=fake_llm, tools=basic_registry, permissions=gate)
            async for _ in loop.stream("Hola"):
                pass


@pytest.mark.asyncio
async def test_loop_stream_tool_fails_successfully(fake_llm, basic_registry):
    """Cubre la línea 189: tool falla en stream y se inyecta el error."""
    async def fail_tool():
        return ToolResult(success=False, content="", error="Forced stream failure")

    basic_registry.register(FunctionTool(
        name="fail_stream", description="", parameters_schema={}, func=fail_tool
    ))

    async def mock_stream(*args, **kwargs):
        yield {"type": "tool_call", "id": "c1", "name": "fail_stream", "arguments": {}}
        yield "Texto después de la tool"

    with patch.object(fake_llm, "stream_chat", side_effect=mock_stream):
        with patch.object(fake_llm, "model_name", "openai/gpt-4o"):
            gate = PermissionGate(policies={"fail_stream": Decision.ALLOW})
            loop = AgentLoop(
                llm=fake_llm, tools=basic_registry, permissions=gate, max_iterations=1
            )

            events = []
            async for event in loop.stream("Fail"):
                events.append(event)

            result_events = [e for e in events if isinstance(
                e, AgentEvent) and e.type == "result"]
            assert len(result_events) > 0
            assert "fail_stream" in result_events[0].data["tools_used"]


@pytest.mark.asyncio
async def test_loop_stream_repair_counts_real(fake_llm, basic_registry):
    """Cubre las líneas 199-208 de loop.py: lógica de reintentos en stream()."""
    async def fail_tool():
        raise ValueError("Forced failure")

    basic_registry.register(FunctionTool(
        name="fail_stream", description="", parameters_schema={}, func=fail_tool
    ))

    step_counter = 0

    async def mock_stream(*args, **kwargs):
        nonlocal step_counter
        step_counter += 1

        if step_counter <= 3:
            yield {"type": "tool_call", "id": f"c{step_counter}", "name": "fail_stream", "arguments": {}}
        else:
            yield "Fin."

    with patch.object(fake_llm, "stream_chat", side_effect=mock_stream):
        with patch.object(fake_llm, "model_name", "openai/gpt-4o"):
            gate = PermissionGate(policies={"fail_stream": Decision.ALLOW})
            loop = AgentLoop(
                llm=fake_llm, tools=basic_registry, permissions=gate, max_iterations=5
            )
            ctx = ContextManager()

            async for _ in loop.stream("Fail", context=ctx):
                pass

            all_content = " ".join(str(msg.get("content", ""))
                                   for msg in ctx.messages)
            assert "Reintento 1/3" in all_content
            assert "Reintento 2/3" in all_content
            assert "falló 3 veces" in all_content


def test_init_langfuse_without_credentials():
    """Cubre el return None de _init_langfuse() cuando no hay credenciales."""
    from app.core.harness import loop as loop_module

    with patch.object(loop_module.settings, "LANGFUSE_PUBLIC_KEY", ""), \
            patch.object(loop_module.settings, "LANGFUSE_SECRET_KEY", ""):
        assert loop_module._init_langfuse() is None


@pytest.mark.asyncio
async def test_loop_run_critic_rejection_then_accept(fake_llm, basic_registry):
    """Cubre la rama de auto-reflexión de run() (REJECTED → corrección → aceptación)."""
    fake_llm._responses = [
        LLMResponse(content="Borrador", usage={"prompt_tokens": 10}),
        LLMResponse(content="Corregido", usage={"completion_tokens": 5}),
    ]
    critic = MagicMock()
    critic.run = AsyncMock(side_effect=[
        ToolResult(success=True, content="REJECTED: revisa el tono"),
        ToolResult(success=True, content="OK"),
    ])
    ctx = ContextManager()
    loop = AgentLoop(llm=fake_llm, tools=basic_registry, critic_tool=critic,
                     agent_rules="Reglas de prueba")

    result = await loop.run("Hola", context=ctx)

    assert result.final_answer == "Corregido"
    assert result.steps == 2
    assert result.usage_total == {"prompt_tokens": 10, "completion_tokens": 5}
    assert critic.run.await_count == 2
    assert critic.run.await_args_list[0].kwargs["agent_rules"] == "Reglas de prueba"
    all_content = " ".join(str(msg.get("content", ""))
                           for msg in ctx.get_messages())
    assert "revisa el tono" in all_content


@pytest.mark.asyncio
async def test_loop_run_max_iterations(fake_llm, basic_registry):
    """Cubre el retorno final de run() al agotar max_iterations."""
    fake_llm._responses = [
        LLMResponse(
            content="Pensando",
            tool_calls=[{"id": f"c{i}", "name": "add", "arguments": {"a": 1, "b": 2}}],
            usage={"total_tokens": i + 1},
        )
        for i in range(3)
    ]
    gate = PermissionGate(policies={"add": Decision.ALLOW})
    loop = AgentLoop(llm=fake_llm, tools=basic_registry,
                     permissions=gate, max_iterations=3)

    result = await loop.run("Suma 1 y 2")

    assert result.final_answer == "[Max iterations reached without final answer]"
    assert result.steps == 3
    assert result.tools_used == ["add", "add", "add"]
    assert result.usage_total["total_tokens"] == 6


@pytest.mark.asyncio
async def test_loop_stream_timeout_fallback_to_settings(fake_llm, basic_registry):
    """Cubre el fallback a settings.LLM_STREAM_TIMEOUT cuando timeout <= 0."""
    async def quick_stream(*args, **kwargs):
        yield "Respuesta rápida"

    from app.core.harness import loop as loop_module

    with patch.object(fake_llm, "stream_chat", side_effect=quick_stream):
        with patch.object(loop_module.settings, "LLM_STREAM_TIMEOUT", 30.0):
            loop = AgentLoop(llm=fake_llm, tools=basic_registry, max_iterations=1)
            events = [event async for event in loop.stream("Hola", timeout_seconds=0)]

    results = [e for e in events if e.type == "result"]
    assert len(results) == 1
    assert results[0].data["final_answer"] == "Respuesta rápida"


@pytest.mark.asyncio
async def test_loop_stream_critic_rejection_then_accept(fake_llm, basic_registry):
    """Cubre la rama de rechazo del crítico dentro de stream()."""
    critic = MagicMock()
    critic.run = AsyncMock(side_effect=[
        ToolResult(success=True, content="REJECTED: falta contexto"),
        ToolResult(success=True, content="OK"),
    ])
    ctx = ContextManager()
    loop = AgentLoop(llm=fake_llm, tools=basic_registry,
                     critic_tool=critic, max_iterations=3)

    events = [event async for event in loop.stream("Hola", context=ctx)]

    texts = [e.data for e in events if e.type == "text_chunk"]
    assert any(d.get("is_correction_marker") for d in texts)
    assert any("Corrección aplicada: falta contexto" in d.get("text", "") for d in texts)
    results = [e for e in events if e.type == "result"]
    assert len(results) == 1
    assert results[0].data["steps"] == 2
    assert critic.run.await_count == 2
    assert critic.run.await_args_list[0].kwargs["agent_rules"] == \
        "Sigue las instrucciones del sistema."
    all_content = " ".join(str(msg.get("content", ""))
                           for msg in ctx.get_messages())
    assert "falta contexto" in all_content


@pytest.mark.asyncio
async def test_loop_stream_critic_reflection_limit(fake_llm, basic_registry):
    """Cubre el aviso de límite de reflexiones en stream()."""
    critic = MagicMock()
    critic.run = AsyncMock(return_value=ToolResult(
        success=True, content="REJECTED: incompleto"))
    loop = AgentLoop(llm=fake_llm, tools=basic_registry,
                     critic_tool=critic, max_iterations=4)

    events = [event async for event in loop.stream("Hola")]

    assert critic.run.await_count == 2
    texts = [e.data.get("text", "") for e in events if e.type == "text_chunk"]
    assert any("límite de reflexiones" in text for text in texts)
    results = [e for e in events if e.type == "result"]
    assert len(results) == 1
    assert results[0].data["steps"] == 3


@pytest.mark.asyncio
async def test_loop_execute_tool_permission_denied(fake_llm, basic_registry, tmp_path):
    """Cubre la rama DENY de _execute_tool()."""
    gate = PermissionGate(policies={"add": Decision.DENY},
                          persist_file=tmp_path / "no_perms.json")
    loop = AgentLoop(llm=fake_llm, tools=basic_registry, permissions=gate)
    ctx = ContextManager()

    success, result = await loop._execute_tool(
        {"id": "c1", "name": "add", "arguments": {"a": 1, "b": 2}}, ctx)

    assert success is False
    assert result is None
    assert ctx.get_messages()[-1] == {
        "role": "tool",
        "tool_call_id": "c1",
        "content": "ERROR: Permission denied for 'add'.",
    }


@pytest.mark.asyncio
async def test_loop_calculate_cost_delegates_to_pricing(fake_llm, basic_registry):
    """Cubre _calculate_cost() y su delegación a get_cost_pricing()."""
    loop = AgentLoop(llm=fake_llm, tools=basic_registry)
    loop.pricing.get_cost_pricing = AsyncMock(
        return_value={"input_cost": 0.1, "output_cost": 0.2})

    cost = await loop._calculate_cost(
        {"prompt_tokens": 100, "completion_tokens": 50})

    assert cost == {"input_cost": 0.1, "output_cost": 0.2}
    loop.pricing.get_cost_pricing.assert_awaited_once_with("fake-model", 100, 50)


@pytest.mark.asyncio
async def test_loop_run_emits_prompt_and_stop(fake_llm, basic_registry):
    """El modo headless dispara UserPromptSubmit y Stop sin intervención del usuario."""
    fake_llm._responses = [LLMResponse(content="Listo")]
    loop = AgentLoop(llm=fake_llm, tools=basic_registry)

    with patch("app.core.harness.loop.emit_hook", new_callable=AsyncMock) as emit:
        result = await loop.run("Hola", context=ContextManager())

    assert result.final_answer == "Listo"
    events = [call.args[0] for call in emit.await_args_list]
    assert [event.hook_event_name for event in events] == [
        "UserPromptSubmit", "Stop"]
    assert events[0].prompt == "Hola"


@pytest.mark.asyncio
async def test_loop_execute_tool_emits_pre_and_post(fake_llm, basic_registry):
    gate = PermissionGate(policies={"add": Decision.ALLOW})
    loop = AgentLoop(llm=fake_llm, tools=basic_registry, permissions=gate)

    with patch("app.core.harness.loop.emit_hook", new_callable=AsyncMock) as emit:
        success, _ = await loop._execute_tool(
            {"id": "c1", "name": "add", "arguments": {"a": 1, "b": 2}},
            ContextManager(),
        )

    assert success is True
    events = [call.args[0] for call in emit.await_args_list]
    assert [event.hook_event_name for event in events] == [
        "PreToolUse", "PostToolUse"]
    assert events[0].tool_name == "add"
    assert events[0].tool_input == {"a": 1, "b": 2}
    assert events[1].success is True


@pytest.mark.asyncio
async def test_loop_denied_tool_emits_post_hook(fake_llm, basic_registry, tmp_path):
    gate = PermissionGate(policies={"add": Decision.DENY},
                          persist_file=tmp_path / "no_perms.json")
    loop = AgentLoop(llm=fake_llm, tools=basic_registry, permissions=gate)

    with patch("app.core.harness.loop.emit_hook", new_callable=AsyncMock) as emit:
        success, result = await loop._execute_tool(
            {"id": "c1", "name": "add", "arguments": {}}, ContextManager())

    assert (success, result) == (False, None)
    assert [call.args[0].hook_event_name for call in emit.await_args_list] == [
        "PreToolUse", "PostToolUse"]
    assert emit.await_args_list[1].args[0].success is False


@pytest.mark.asyncio
async def test_loop_missing_tool_emits_post_hook(fake_llm, basic_registry):
    loop = AgentLoop(llm=fake_llm, tools=basic_registry)

    with patch("app.core.harness.loop.emit_hook", new_callable=AsyncMock) as emit:
        success, result = await loop._execute_tool(
            {"id": "c1", "name": "ghost", "arguments": {}}, ContextManager())

    assert (success, result) == (False, None)
    assert [call.args[0].hook_event_name for call in emit.await_args_list] == [
        "PreToolUse", "PostToolUse"]
    assert emit.await_args_list[1].args[0].success is False


@pytest.mark.asyncio
async def test_loop_stream_emits_stop(fake_llm, basic_registry):
    async def mock_stream(*args, **kwargs):
        yield "Listo"

    with patch.object(fake_llm, "stream_chat", side_effect=mock_stream):
        loop = AgentLoop(llm=fake_llm, tools=basic_registry)
        with patch("app.core.harness.loop.emit_hook", new_callable=AsyncMock) as emit:
            events = [event async for event in loop.stream("Hola")]

    assert any(event.type == "result" for event in events)
    assert [call.args[0].hook_event_name for call in emit.await_args_list] == [
        "Stop"]


@pytest.mark.asyncio
async def test_loop_stream_emits_stop_failure_on_timeout():
    loop = AgentLoop(llm=HangingLLM(), tools=ToolRegistry())

    with patch("app.core.harness.loop.emit_hook", new_callable=AsyncMock) as emit:
        events = [event async for event in loop.stream(
            "Hola", timeout_seconds=0.1)]

    assert events[-1].type == "error"
    assert [call.args[0].hook_event_name for call in emit.await_args_list] == [
        "StopFailure"]


@pytest.mark.asyncio
async def test_loop_stream_emits_stop_failure_on_error(fake_llm):
    with patch.object(fake_llm, "stream_chat", side_effect=RuntimeError("boom")):
        loop = AgentLoop(llm=fake_llm, tools=ToolRegistry())
        with patch("app.core.harness.loop.emit_hook", new_callable=AsyncMock) as emit:
            events = [event async for event in loop.stream("Hola")]

    assert events[-1].type == "error"
    assert [call.args[0].hook_event_name for call in emit.await_args_list] == [
        "StopFailure"]


@pytest.mark.asyncio
async def test_loop_max_iterations_emits_stop(fake_llm, basic_registry):
    async def mock_stream(*args, **kwargs):
        yield {"type": "tool_call", "id": "c1", "name": "add",
               "arguments": {"a": 1, "b": 2}}

    gate = PermissionGate(policies={"add": Decision.ALLOW})
    with patch.object(fake_llm, "stream_chat", side_effect=mock_stream):
        loop = AgentLoop(llm=fake_llm, tools=basic_registry,
                         permissions=gate, max_iterations=1)
        with patch("app.core.harness.loop.emit_hook", new_callable=AsyncMock) as emit:
            events = [event async for event in loop.stream("Hola")]

    assert events[-1].type == "result"
    assert [call.args[0].hook_event_name for call in emit.await_args_list][-1] == "Stop"


@pytest.mark.asyncio
async def test_loop_hook_denial_blocks_tool(fake_llm, basic_registry):
    """Un hook PreToolUse con deny impide ejecutar la herramienta."""
    gate = PermissionGate(policies={"add": Decision.ALLOW})
    loop = AgentLoop(llm=fake_llm, tools=basic_registry, permissions=gate)
    tool = basic_registry.get("add")
    tool._func = MagicMock(return_value=3)
    ctx = ContextManager()

    async def emit_side_effect(event):
        if event.hook_event_name == "PreToolUse":
            return HookOutcome(denied=True, reason="Borrado prohibido por hook")
        return HookOutcome()

    with patch("app.core.harness.loop.emit_hook",
               side_effect=emit_side_effect) as emit:
        success, result = await loop._execute_tool(
            {"id": "c1", "name": "add", "arguments": {"a": 1, "b": 2}}, ctx)

    assert (success, result) == (False, None)
    tool._func.assert_not_called()
    assert loop.last_hook_denial == "Borrado prohibido por hook"
    assert "Borrado prohibido por hook" in ctx.messages[-1]["content"]
    assert [call.args[0].hook_event_name for call in emit.await_args_list] == [
        "PreToolUse", "PostToolUse"]
    assert emit.await_args_list[1].args[0].success is False


@pytest.mark.asyncio
async def test_loop_hook_denial_without_reason_uses_default(fake_llm, basic_registry):
    """Si el hook no da motivo, se ofrece uno genérico."""
    loop = AgentLoop(llm=fake_llm, tools=basic_registry)

    async def emit_side_effect(event):
        if event.hook_event_name == "PreToolUse":
            return HookOutcome(denied=True, reason="")
        return HookOutcome()

    with patch("app.core.harness.loop.emit_hook", side_effect=emit_side_effect):
        success, _ = await loop._execute_tool(
            {"id": "c1", "name": "add", "arguments": {}}, ContextManager())

    assert success is False
    assert loop.last_hook_denial == "El hook bloqueó la herramienta 'add'."


@pytest.mark.asyncio
async def test_loop_stream_yields_hook_denied(fake_llm, basic_registry):
    """El stream entrega el aviso y no ejecuta la herramienta bloqueada."""
    async def mock_stream(*args, **kwargs):
        yield {"type": "tool_call", "id": "c1", "name": "add",
               "arguments": {"a": 1, "b": 2}}

    tool = basic_registry.get("add")
    tool._func = MagicMock(return_value=3)
    gate = PermissionGate(policies={"add": Decision.ALLOW})

    async def emit_side_effect(event):
        if event.hook_event_name == "PreToolUse":
            return HookOutcome(denied=True, reason="No se pueden borrar archivos")
        return HookOutcome()

    with patch.object(fake_llm, "stream_chat", side_effect=mock_stream):
        loop = AgentLoop(llm=fake_llm, tools=basic_registry,
                         permissions=gate, max_iterations=1)
        with patch("app.core.harness.loop.emit_hook",
                   side_effect=emit_side_effect):
            events = [event async for event in loop.stream("Hola")]

    denials = [event for event in events if event.type == "hook_denied"]
    assert len(denials) == 1
    assert denials[0].data == {
        "tool": "add", "message": "No se pueden borrar archivos"}
    assert tool._func.assert_not_called() is None
    assert loop.last_hook_denial is None


@pytest.mark.asyncio
async def test_real_no_delete_hook_blocks_bash_rm(fake_llm, tmp_path):
    """Integración real: el script del hook bloquea un `rm` antes de la tool."""
    script = Path(__file__).resolve().parents[2] / ".harness" / "hooks" / "no_delete.py"
    config_file = tmp_path / "hooks.json"
    config_file.write_text(json.dumps({"hooks": {
        "PreToolUse": [{"matcher": "bash", "hooks": [
            {"command": f"{sys.executable} {script}"}]}]
    }}), encoding="utf-8")
    manager = HookManager(config_file=config_file)

    async def delete_file(**kwargs):
        return "borrado"

    registry = ToolRegistry()
    registry.register(FunctionTool(
        name="bash", description="Exec", parameters_schema={}, func=delete_file))
    func_spy = MagicMock(wraps=delete_file)
    registry._tools["bash"]._func = func_spy

    async def mock_stream(*args, **kwargs):
        yield {"type": "tool_call", "id": "c1", "name": "bash",
               "arguments": {"command": "rm -f archivo.txt"}}

    with patch.object(fake_llm, "stream_chat", side_effect=mock_stream):
        with patch("app.core.harness.hooks.hook_manager", manager):
            loop = AgentLoop(llm=fake_llm, tools=registry, max_iterations=1)
            events = [event async for event in loop.stream("Borra el archivo")]

    denials = [event for event in events if event.type == "hook_denied"]
    assert len(denials) == 1
    assert "eliminar" in denials[0].data["message"].lower()
    func_spy.assert_not_called()
