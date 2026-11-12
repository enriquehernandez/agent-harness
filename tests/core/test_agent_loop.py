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


@pytest.mark.asyncio
async def test_loop_stream_with_tools(fake_llm, basic_registry):
    """Cubre el método stream() del AgentLoop."""
    from unittest.mock import AsyncMock, patch

    # Mockeamos stream_chat para que devuelva texto y tool_calls
    async def mock_stream(*args, **kwargs):
        yield "Pensando..."
        yield {"type": "tool_call", "id": "c1", "name": "add", "arguments": {"a": 1, "b": 2}}
        yield "El resultado es 3."
        yield {"type": "usage", "usage": {"total_tokens": 100}}
        yield {"type": "result", "final_answer": "El resultado es 3.", "steps": 2, "tools_used": ["add"], "usage_total": {"total_tokens": 100}}

    with patch.object(fake_llm, "stream_chat", side_effect=mock_stream):
        gate = PermissionGate(policies={"add": Decision.ALLOW})
        loop = AgentLoop(llm=fake_llm, tools=basic_registry, permissions=gate)

        chunks = []
        async for chunk in loop.stream("Suma 1 y 2"):
            chunks.append(chunk)

        # Verificamos que hay texto, tool_call y result
        assert any(isinstance(c, str) for c in chunks)
        assert any(isinstance(c, dict) and c.get(
            "type") == "tool_call" for c in chunks)
        assert any(isinstance(c, dict) and c.get(
            "type") == "result" for c in chunks)


@pytest.mark.asyncio
async def test_loop_stream_edge_cases(fake_llm, basic_registry):
    """Cubre las ramas de error del stream()."""
    from unittest.mock import patch

    # 1. Permission denied
    async def mock_stream_denied(*args, **kwargs):
        yield {"type": "tool_call", "id": "c1", "name": "add", "arguments": {"a": 1, "b": 2}}
        yield {"type": "result", "final_answer": "Denied", "steps": 1, "tools_used": [], "usage_total": {}}

    with patch.object(fake_llm, "stream_chat", side_effect=mock_stream_denied):
        gate = PermissionGate(policies={"add": Decision.DENY})
        loop = AgentLoop(llm=fake_llm, tools=basic_registry, permissions=gate)
        async for _ in loop.stream("Suma"):
            pass

    # 2. Tool not found
    async def mock_stream_not_found(*args, **kwargs):
        yield {"type": "tool_call", "id": "c1", "name": "ghost", "arguments": {}}
        yield {"type": "result", "final_answer": "Not found", "steps": 1, "tools_used": [], "usage_total": {}}

    with patch.object(fake_llm, "stream_chat", side_effect=mock_stream_not_found):
        gate = PermissionGate(policies={"ghost": Decision.ALLOW})
        loop = AgentLoop(llm=fake_llm, tools=basic_registry, permissions=gate)
        async for _ in loop.stream("Ghost"):
            pass

    # 3. Tool fails
    from app.core.harness.tool import FunctionTool, ToolResult

    async def fail_tool(): return ToolResult(
        success=False, content="", error="Fail")
    basic_registry.register(FunctionTool(
        name="fail", description="", parameters_schema={}, func=fail_tool))

    async def mock_stream_fail(*args, **kwargs):
        yield {"type": "tool_call", "id": "c1", "name": "fail", "arguments": {}}
        yield {"type": "result", "final_answer": "Failed", "steps": 1, "tools_used": ["fail"], "usage_total": {}}

    with patch.object(fake_llm, "stream_chat", side_effect=mock_stream_fail):
        gate = PermissionGate(policies={"fail": Decision.ALLOW})
        loop = AgentLoop(llm=fake_llm, tools=basic_registry, permissions=gate)
        async for _ in loop.stream("Fail"):
            pass

    # 4. Max iterations
    async def mock_stream_loop(*args, **kwargs):
        yield {"type": "tool_call", "id": "c1", "name": "add", "arguments": {"a": 1, "b": 1}}
        # No emitimos result para forzar el max_iterations
        yield "texto"

    with patch.object(fake_llm, "stream_chat", side_effect=mock_stream_loop):
        gate = PermissionGate(policies={"add": Decision.ALLOW})
        loop = AgentLoop(llm=fake_llm, tools=basic_registry,
                         permissions=gate, max_iterations=2)
        async for _ in loop.stream("Loop"):
            pass


@pytest.mark.asyncio
async def test_loop_stream_edge_cases(fake_llm, basic_registry):
    """Cubre las ramas de error del stream()."""
    from unittest.mock import patch

    # 1. Cubre if not tool_calls (línea 154-155)
    async def mock_stream_no_tools(*args, **kwargs):
        yield "Solo texto"
        yield {"type": "result", "final_answer": "Solo texto", "steps": 1, "tools_used": [], "usage_total": {}}

    with patch.object(fake_llm, "stream_chat", side_effect=mock_stream_no_tools):
        gate = PermissionGate(policies={})
        loop = AgentLoop(llm=fake_llm, tools=basic_registry, permissions=gate)
        async for _ in loop.stream("Hola"):
            pass

    # 2. Cubre else de result.success (línea 189)
    from app.core.harness.tool import FunctionTool, ToolResult

    async def fail_tool(): return ToolResult(
        success=False, content="", error="Fail")
    basic_registry.register(FunctionTool(
        name="fail", description="", parameters_schema={}, func=fail_tool))

    async def mock_stream_fail(*args, **kwargs):
        yield {"type": "tool_call", "id": "c1", "name": "fail", "arguments": {}}
        yield {"type": "result", "final_answer": "Failed", "steps": 1, "tools_used": ["fail"], "usage_total": {}}

    with patch.object(fake_llm, "stream_chat", side_effect=mock_stream_fail):
        gate = PermissionGate(policies={"fail": Decision.ALLOW})
        loop = AgentLoop(llm=fake_llm, tools=basic_registry, permissions=gate)
        async for _ in loop.stream("Fail"):
            pass


@pytest.mark.asyncio
async def test_loop_stream_all_error_branches(fake_llm, basic_registry):
    """Cubre todas las ramas de error del stream()."""
    from unittest.mock import patch
    from app.core.harness.tool import FunctionTool, ToolResult

    # 1. Permission DENY (línea 173)
    async def mock_stream_denied(*args, **kwargs):
        yield {"type": "tool_call", "id": "c1", "name": "add", "arguments": {"a": 1, "b": 2}}
        yield {"type": "result", "final_answer": "Denied", "steps": 1, "tools_used": [], "usage_total": {}}

    with patch.object(fake_llm, "stream_chat", side_effect=mock_stream_denied):
        gate = PermissionGate(policies={"add": Decision.DENY})
        loop = AgentLoop(llm=fake_llm, tools=basic_registry, permissions=gate)
        async for _ in loop.stream("Suma"):
            pass

    # 2. Tool not found (línea 179)
    async def mock_stream_not_found(*args, **kwargs):
        yield {"type": "tool_call", "id": "c1", "name": "ghost", "arguments": {}}
        yield {"type": "result", "final_answer": "Not found", "steps": 1, "tools_used": [], "usage_total": {}}

    with patch.object(fake_llm, "stream_chat", side_effect=mock_stream_not_found):
        gate = PermissionGate(policies={"ghost": Decision.ALLOW})
        loop = AgentLoop(llm=fake_llm, tools=basic_registry, permissions=gate)
        async for _ in loop.stream("Ghost"):
            pass

    # 3. Tool fails (línea 189)
    async def fail_tool(): return ToolResult(
        success=False, content="", error="Fail")
    basic_registry.register(FunctionTool(
        name="fail", description="", parameters_schema={}, func=fail_tool))

    async def mock_stream_fail(*args, **kwargs):
        yield {"type": "tool_call", "id": "c1", "name": "fail", "arguments": {}}
        yield {"type": "result", "final_answer": "Failed", "steps": 1, "tools_used": ["fail"], "usage_total": {}}

    with patch.object(fake_llm, "stream_chat", side_effect=mock_stream_fail):
        gate = PermissionGate(policies={"fail": Decision.ALLOW})
        loop = AgentLoop(llm=fake_llm, tools=basic_registry, permissions=gate)
        async for _ in loop.stream("Fail"):
            pass


@pytest.mark.asyncio
async def test_loop_stream_tool_fails(fake_llm, basic_registry):
    """Cubre el else de result.success en stream()."""
    from unittest.mock import patch
    from app.core.harness.tool import FunctionTool, ToolResult

    async def fail_tool():
        return ToolResult(success=False, content="", error="Forced failure")

    basic_registry.register(FunctionTool(
        name="fail_stream", description="", parameters_schema={}, func=fail_tool
    ))

    async def mock_stream(*args, **kwargs):
        yield {"type": "tool_call", "id": "c1", "name": "fail_stream", "arguments": {}}
        yield {"type": "result", "final_answer": "Failed", "steps": 1, "tools_used": ["fail_stream"], "usage_total": {}}

    with patch.object(fake_llm, "stream_chat", side_effect=mock_stream):
        gate = PermissionGate(policies={"fail_stream": Decision.ALLOW})
        loop = AgentLoop(llm=fake_llm, tools=basic_registry, permissions=gate)

        async for _ in loop.stream("Fail"):
            pass


@pytest.mark.asyncio
async def test_loop_stream_tool_fails_successfully(fake_llm, basic_registry):
    """Cubre la línea 189: tool falla en stream y se inyecta el error."""
    from unittest.mock import patch
    from app.core.harness.tool import FunctionTool, ToolResult

    # 1. Registramos una tool que falla
    async def fail_tool():
        return ToolResult(success=False, content="", error="Forced stream failure")

    basic_registry.register(FunctionTool(
        name="fail_stream", description="", parameters_schema={}, func=fail_tool
    ))

    # 2. Mockeamos stream_chat para que emita un tool_call y luego un texto
    # (el texto hace que no haya más tool_calls, y el bucle termine)
    async def mock_stream(*args, **kwargs):
        yield {"type": "tool_call", "id": "c1", "name": "fail_stream", "arguments": {}}
        yield "Texto después de la tool"  # 🔥 Esto evita que el bucle itere de nuevo

    # 3. Ejecutamos el stream con max_iterations=1 para asegurar
    with patch.object(fake_llm, "stream_chat", side_effect=mock_stream):
        gate = PermissionGate(policies={"fail_stream": Decision.ALLOW})
        loop = AgentLoop(
            llm=fake_llm,
            tools=basic_registry,
            permissions=gate,
            max_iterations=1  # 🔥 Solo 1 iteración
        )

        chunks = []
        async for chunk in loop.stream("Fail"):
            chunks.append(chunk)

        # 4. Verificamos que el error se inyectó en el contexto
        # (Esto cubre la línea 189)
        result_chunks = [c for c in chunks if isinstance(
            c, dict) and c.get("type") == "result"]
        assert len(result_chunks) > 0
        assert "fail_stream" in result_chunks[0]["tools_used"]
