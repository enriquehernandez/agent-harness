from unittest.mock import patch

import pytest
from app.core.harness.loop import AgentLoop
from app.core.harness.permissions import PermissionGate, Decision
from app.core.harness.tool import FunctionTool, ToolResult
from app.core.llm.base import LLMResponse
from app.core.harness.context import ContextManager


@pytest.mark.asyncio
async def test_loop_direct_response(fake_llm, basic_registry):
    fake_llm._responses = [LLMResponse(content="Hola, soy un agente.")]
    gate = PermissionGate(policies={"add": Decision.ALLOW})
    loop = AgentLoop(llm=fake_llm, tools=basic_registry, permissions=gate)
    result = await loop.run("Hola")
    assert result.final_answer == "Hola, soy un agente."
    assert result.steps == 1


@pytest.mark.asyncio
async def test_loop_tool_chaining(fake_llm, basic_registry):
    fake_llm._responses = [
        LLMResponse(
            tool_calls=[{"id": "c1", "name": "add", "arguments": {"a": 2, "b": 3}}]),
        LLMResponse(content="El resultado es 5.")
    ]
    gate = PermissionGate(policies={"add": Decision.ALLOW})
    loop = AgentLoop(llm=fake_llm, tools=basic_registry, permissions=gate)
    result = await loop.run("Suma 2 y 3")
    assert result.final_answer == "El resultado es 5."
    assert "add" in result.tools_used


@pytest.mark.asyncio
async def test_loop_tool_fails_successfully(fake_llm, basic_registry):
    """Cubre la línea 94: cuando la tool devuelve success=False."""
    async def fail_tool():
        return ToolResult(success=False, content="", error="Error simulado")

    basic_registry.register(FunctionTool(
        name="fail_tool", description="", parameters_schema={}, func=fail_tool
    ))

    fake_llm._responses = [
        LLMResponse(
            tool_calls=[{"id": "c1", "name": "fail_tool", "arguments": {}}]),
        LLMResponse(content="Ocurrió un error.")
    ]
    gate = PermissionGate(policies={"fail_tool": Decision.ALLOW})
    loop = AgentLoop(llm=fake_llm, tools=basic_registry, permissions=gate)
    result = await loop.run("Ejecuta fail_tool")
    assert result.final_answer == "Ocurrió un error."


@pytest.mark.asyncio
async def test_loop_permission_denied(fake_llm, basic_registry):
    fake_llm._responses = [
        LLMResponse(
            tool_calls=[{"id": "c1", "name": "add", "arguments": {"a": 2, "b": 3}}]),
        LLMResponse(content="Entendido, no tengo permiso.")
    ]
    gate = PermissionGate(policies={"add": Decision.DENY})
    loop = AgentLoop(llm=fake_llm, tools=basic_registry, permissions=gate)
    result = await loop.run("Suma 2 y 3")
    assert result.final_answer == "Entendido, no tengo permiso."


@pytest.mark.asyncio
async def test_loop_tool_not_found(fake_llm, basic_registry):
    fake_llm._responses = [
        LLMResponse(
            tool_calls=[{"id": "c1", "name": "herramienta_fantasma", "arguments": {}}]),
        LLMResponse(content="Lo siento, esa herramienta no existe.")
    ]
    gate = PermissionGate(policies={"herramienta_fantasma": Decision.ALLOW})
    loop = AgentLoop(llm=fake_llm, tools=basic_registry, permissions=gate)
    result = await loop.run("Usa la herramienta fantasma")
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
    result = await loop.run("Suma infinitamente")
    assert result.steps == 3


@pytest.mark.asyncio
async def test_loop_covers_tool_error(fake_llm, basic_registry):
    """Cubre las líneas 93-95: el bloque else cuando la tool falla."""
    # 1. Registramos una tool que siempre falla
    async def fail_tool():
        return ToolResult(success=False, content="", error="Fallo crítico")

    basic_registry.register(FunctionTool(
        name="fail_tool", description="", parameters_schema={}, func=fail_tool
    ))

    # 2. Simulamos el LLM: pide la tool y luego responde
    fake_llm._responses = [
        LLMResponse(
            tool_calls=[{"id": "c1", "name": "fail_tool", "arguments": {}}]),
        LLMResponse(content="El agente vio el error y respondió.")
    ]

    # 3. Configuramos el gate para permitir la ejecución
    gate = PermissionGate(policies={"fail_tool": Decision.ALLOW})
    loop = AgentLoop(llm=fake_llm, tools=basic_registry, permissions=gate)

    # 4. Usamos un ContextManager real para verificar que se inyecta el error
    ctx = ContextManager(system_prompt="System")
    result = await loop.run("Ejecuta fail_tool", context=ctx)

    # 5. Verificaciones
    assert result.final_answer == "El agente vio el error y respondió."

    # Buscamos en los mensajes inyectados el error de la tool
    error_msg = [m for m in ctx.messages if m.get(
        "role") == "tool" and "Fallo crítico" in m.get("content", "")]
    assert len(error_msg) == 1


@pytest.mark.asyncio
async def test_loop_tool_execution_failure(fake_llm, basic_registry):
    """Cubre las líneas 94-95: bloque else de error de la tool."""
    from app.core.harness.tool import FunctionTool, ToolResult

    # 1. Registramos una tool normal
    async def dummy_tool(): return ToolResult(
        success=True, content="ok", error=None)
    basic_registry.register(FunctionTool(
        name="fail_tool", description="", parameters_schema={}, func=dummy_tool))

    # 2. Simulamos el LLM
    fake_llm._responses = [
        LLMResponse(
            tool_calls=[{"id": "c1", "name": "fail_tool", "arguments": {}}]),
        LLMResponse(content="Error manejado.")
    ]

    gate = PermissionGate(policies={"fail_tool": Decision.ALLOW})
    loop = AgentLoop(llm=fake_llm, tools=basic_registry, permissions=gate)

    # 3. 🔥 EL TRUCO: Parcheamos el método `run` de la tool para que devuelva un fallo
    with patch.object(loop.tools.get("fail_tool"), "run", return_value=ToolResult(success=False, content="", error="Fallo forzado")):
        result = await loop.run("Ejecuta fail_tool")

    assert result.final_answer == "Error manejado."


@pytest.mark.asyncio
async def test_loop_tool_fails_successfully(fake_llm, basic_registry):
    """Cubre las líneas 93-94: bloque else de error de la tool."""
    from app.core.harness.tool import FunctionTool, ToolResult
    from app.core.harness.permissions import PermissionGate, Decision

    async def dummy_tool():
        return ToolResult(success=True, content="ok", error=None)

    basic_registry.register(FunctionTool(
        name="fail_tool", description="", parameters_schema={}, func=dummy_tool
    ))

    fake_llm._responses = [
        LLMResponse(
            tool_calls=[{"id": "c1", "name": "fail_tool", "arguments": {}}]),
        LLMResponse(content="Error manejado.")
    ]

    gate = PermissionGate(policies={"fail_tool": Decision.ALLOW})
    loop = AgentLoop(llm=fake_llm, tools=basic_registry, permissions=gate)

    # 🔥 Forzamos el fallo con patch
    with patch.object(loop.tools.get("fail_tool"), "run", return_value=ToolResult(success=False, content="", error="Fallo forzado")):
        result = await loop.run("Ejecuta fail_tool")

    assert result.final_answer == "Error manejado."


@pytest.mark.asyncio
async def test_loop_accumulate_usage(fake_llm, basic_registry):
    """Cubre la línea 105: suma de tokens cuando hay múltiples turnos."""
    from app.core.harness.permissions import PermissionGate, Decision

    # Simulamos un flujo con tool para que haya 2 turnos y sume los tokens de ambos
    fake_llm._responses = [
        LLMResponse(
            tool_calls=[{"id": "c1", "name": "add",
                         "arguments": {"a": 1, "b": 2}}],
            usage={"prompt_tokens": 10, "completion_tokens": 5,
                   "total_tokens": 15}  # Turno 1
        ),
        LLMResponse(
            content="El resultado es 3.",
            usage={"prompt_tokens": 20, "completion_tokens": 10,
                   "total_tokens": 30}  # Turno 2
        )
    ]

    gate = PermissionGate(policies={"add": Decision.ALLOW})
    loop = AgentLoop(llm=fake_llm, tools=basic_registry, permissions=gate)

    result = await loop.run("Suma 1 y 2")

    # Al ejecutarse dos veces, el _accumulate_usage debería haber sumado 15 + 30
    assert result.usage_total["total_tokens"] == 45
    assert result.usage_total["prompt_tokens"] == 30
