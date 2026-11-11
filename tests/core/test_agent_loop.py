import pytest
from unittest.mock import patch, AsyncMock
from app.core.harness.loop import AgentLoop
from app.core.harness.permissions import PermissionGate, Decision
from app.core.harness.tool import FunctionTool, ToolResult
from app.core.llm.base import LLMResponse
from app.core.harness.context import ContextManager
from app.core.llm.providers.fake import FakeLLM


@pytest.mark.asyncio
async def test_loop_direct_response(fake_llm, basic_registry):
    fake_llm._responses = [LLMResponse(content="Hello, I am an agent.")]
    gate = PermissionGate(policies={"add": Decision.ALLOW})
    loop = AgentLoop(llm=fake_llm, tools=basic_registry, permissions=gate)
    result = await loop.run("Hello")
    assert result.final_answer == "Hello, I am an agent."
    assert result.steps == 1


@pytest.mark.asyncio
async def test_loop_tool_chaining(fake_llm, basic_registry):
    fake_llm._responses = [
        LLMResponse(
            tool_calls=[{"id": "c1", "name": "add", "arguments": {"a": 2, "b": 3}}]),
        LLMResponse(content="The result is 5.")
    ]
    gate = PermissionGate(policies={"add": Decision.ALLOW})
    loop = AgentLoop(llm=fake_llm, tools=basic_registry, permissions=gate)
    result = await loop.run("Add 2 and 3")
    assert result.final_answer == "The result is 5."
    assert "add" in result.tools_used


@pytest.mark.asyncio
async def test_loop_permission_denied(fake_llm, basic_registry):
    fake_llm._responses = [
        LLMResponse(
            tool_calls=[{"id": "c1", "name": "add", "arguments": {"a": 2, "b": 3}}]),
        LLMResponse(content="Understood, I don't have permission.")
    ]
    gate = PermissionGate(policies={"add": Decision.DENY})
    loop = AgentLoop(llm=fake_llm, tools=basic_registry, permissions=gate)
    result = await loop.run("Add 2 and 3")
    assert result.final_answer == "Understood, I don't have permission."


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
    assert len(result.tools_used) == 0


@pytest.mark.asyncio
async def test_loop_max_iterations(fake_llm, basic_registry):
    fake_llm._responses = [
        LLMResponse(
            tool_calls=[{"id": "c1", "name": "add", "arguments": {"a": 1, "b": 1}}])
    ] * 5
    gate = PermissionGate(policies={"add": Decision.ALLOW})
    loop = AgentLoop(llm=fake_llm, tools=basic_registry,
                     permissions=gate, max_iterations=3)
    result = await loop.run("Add infinitely")
    assert result.steps == 3


@pytest.mark.asyncio
async def test_loop_accumulate_usage(fake_llm, basic_registry):
    fake_llm._responses = [
        LLMResponse(
            tool_calls=[{"id": "c1", "name": "add",
                         "arguments": {"a": 1, "b": 2}}],
            usage={"prompt_tokens": 10,
                   "completion_tokens": 5, "total_tokens": 15}
        ),
        LLMResponse(
            content="The result is 3.",
            usage={"prompt_tokens": 20,
                   "completion_tokens": 10, "total_tokens": 30}
        )
    ]
    gate = PermissionGate(policies={"add": Decision.ALLOW})
    loop = AgentLoop(llm=fake_llm, tools=basic_registry, permissions=gate)
    result = await loop.run("Add 1 and 2")
    assert result.usage_total["total_tokens"] == 45
    assert result.usage_total["prompt_tokens"] == 30


@pytest.mark.asyncio
async def test_loop_tool_repair_limit(fake_llm, basic_registry):
    """Cubre las líneas 99-100: cuando una tool falla 3 veces."""
    from app.core.harness.tool import FunctionTool, ToolResult
    from unittest.mock import patch

    async def fail_tool():
        return ToolResult(success=False, content="", error="Forced failure")

    basic_registry.register(FunctionTool(
        name="fail_tool", description="", parameters_schema={}, func=fail_tool
    ))

    # 🔥 Forzamos 5 respuestas que piden la tool
    fake_llm._responses = [
        LLMResponse(
            tool_calls=[{"id": "c1", "name": "fail_tool", "arguments": {}}])
    ] * 5

    gate = PermissionGate(policies={"fail_tool": Decision.ALLOW})
    loop = AgentLoop(llm=fake_llm, tools=basic_registry, permissions=gate)
    loop.max_iterations = 5

    # 🔥 Parcheamos la tool para que siempre falle
    with patch.object(loop.tools.get("fail_tool"), "run", return_value=ToolResult(success=False, content="", error="Forced failure")):
        result = await loop.run("Execute fail_tool")

    # Verificamos que el contador llegó a 3
    assert loop.repair_counts.get("fail_tool", 0) >= 3
