import pytest
from app.mcp.client import MCPClient
from app.core.harness.tool import ToolRegistry
from app.core.harness.loop import AgentLoop
from app.core.harness.permissions import PermissionGate, Decision
from app.core.llm.providers.fake import FakeLLM
from app.core.llm.base import LLMResponse


@pytest.mark.asyncio
async def test_mcp_local_server_e2e():
    print("\n" + "="*50)
    print("🚀 INICIANDO TEST DE INTEGRACIÓN MCP")
    print("="*50)

    print("\n1️⃣ Levantando servidor MCP local...")
    client = MCPClient(
        command="uv",
        args=["run", "python", "scripts/local_mcp_server.py"]
    )
    await client.connect()
    print("✅ Servidor conectado.")

    print("\n2️⃣ Descubriendo herramientas...")
    registry = ToolRegistry()
    await client.register_tools(registry, server_name="local_dev")

    tools = registry.names()
    print(f"✅ Herramientas descubiertas: {tools}")
    assert "get_system_info" in tools
    assert "echo_message" in tools
    assert "analyze_code_complexity" in tools
    assert "run_tests" in tools

    gate = PermissionGate()
    for tool in tools:
        gate.policies[tool] = Decision.ALLOW

    # ---------------------------------------------------------
    print("\n3️⃣ Probando: get_system_info...")
    fake_llm_1 = FakeLLM(responses=[
        LLMResponse(
            tool_calls=[{"id": "c1", "name": "get_system_info", "arguments": {}}]),
        LLMResponse(content="El sistema está funcionando.")
    ])
    loop1 = AgentLoop(llm=fake_llm_1, tools=registry, permissions=gate)
    result1 = await loop1.run("Dime el sistema operativo")
    print(f"✅ get_system_info ejecutado.")
    assert "get_system_info" in result1.tools_used

    # ---------------------------------------------------------
    print("\n4️⃣ Probando: echo_message...")
    fake_llm_2 = FakeLLM(responses=[
        LLMResponse(tool_calls=[{"id": "c2", "name": "echo_message", "arguments": {
                    "message": "Hola Harness"}}]),
        LLMResponse(content="El mensaje fue enviado.")
    ])
    loop2 = AgentLoop(llm=fake_llm_2, tools=registry, permissions=gate)
    result2 = await loop2.run("Haz eco")
    print(f"✅ echo_message ejecutado.")
    assert "echo_message" in result2.tools_used

    # ---------------------------------------------------------
    print("\n5️⃣ Probando: analyze_code_complexity...")
    fake_llm_3 = FakeLLM(responses=[
        LLMResponse(tool_calls=[{"id": "c3", "name": "analyze_code_complexity", "arguments": {
                    "file_path": "app/core/harness/loop.py"}}]),
        LLMResponse(content="El archivo tiene varias clases.")
    ])
    loop3 = AgentLoop(llm=fake_llm_3, tools=registry, permissions=gate)
    result3 = await loop3.run("Analiza el loop")
    print(f"✅ analyze_code_complexity ejecutado.")
    assert "analyze_code_complexity" in result3.tools_used

    # ---------------------------------------------------------
    print("\n6️⃣ Probando: run_tests...")
    fake_llm_4 = FakeLLM(responses=[
        LLMResponse(
            tool_calls=[{"id": "c4", "name": "run_tests", "arguments": {}}]),
        LLMResponse(content="Los tests pasaron.")
    ])
    loop4 = AgentLoop(llm=fake_llm_4, tools=registry, permissions=gate)

    # 🔥 ADVERTENCIA: Esto es lo que tarda 60s (el bucle recursivo de pytest)
    print("⏳ Ejecutando run_tests (esto puede tardar)...")
    result4 = await loop4.run("Corre los tests")
    print(f"✅ run_tests ejecutado.")
    assert "run_tests" in result4.tools_used

    print("\n7️⃣ Cerrando servidor MCP...")
    await client.disconnect()
    print("✅ Servidor cerrado.")
    print("\n" + "="*50)
    print("🎉 TODOS LOS TESTS E2E PASARON")
    print("="*50 + "\n")
