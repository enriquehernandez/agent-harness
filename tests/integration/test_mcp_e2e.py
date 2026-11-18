import pytest
from app.mcp.client import MCPClient
from app.core.harness.tool import ToolRegistry
from app.core.harness.loop import AgentLoop
from app.core.harness.permissions import PermissionGate, Decision
from app.core.llm.providers.fake import FakeLLM
from app.core.llm.base import LLMResponse
import os
os.environ["HARNESS_E2E"] = "1"


@pytest.mark.asyncio
async def test_mcp_local_server_e2e():
    print("\n" + "="*50)
    print("🚀 STARTING MCP INTEGRATION TEST")
    print("="*50)

    print("\n1️⃣ Starting local MCP server...")
    client = MCPClient(
        command="uv",
        args=["run", "python", "scripts/local_mcp_server.py"]
    )
    await client.connect()
    print("✅ Server connected.")

    print("\n2️⃣ Discovering tools...")
    registry = ToolRegistry()
    await client.register_tools(registry, server_name="local_dev")

    tools = registry.names()
    print(f"✅ Tools discovered: {tools}")
    assert "get_system_info" in tools
    assert "echo_message" in tools
    assert "analyze_code_complexity" in tools
    assert "run_tests" in tools

    gate = PermissionGate()
    for tool in tools:
        gate.policies[tool] = Decision.ALLOW

    print("\n3️⃣ Testing: get_system_info...")
    fake_llm_1 = FakeLLM(responses=[
        LLMResponse(
            tool_calls=[{"id": "c1", "name": "get_system_info", "arguments": {}}]),
        LLMResponse(content="The system is working.")
    ])
    loop1 = AgentLoop(llm=fake_llm_1, tools=registry, permissions=gate)
    result1 = await loop1.run("Tell me the OS")
    print(f"✅ get_system_info executed.")
    assert "get_system_info" in result1.tools_used

    print("\n4️⃣ Testing: echo_message...")
    fake_llm_2 = FakeLLM(responses=[
        LLMResponse(tool_calls=[{"id": "c2", "name": "echo_message", "arguments": {
                    "message": "Hello Harness"}}]),
        LLMResponse(content="The message was sent.")
    ])
    loop2 = AgentLoop(llm=fake_llm_2, tools=registry, permissions=gate)
    result2 = await loop2.run("Echo")
    print(f"✅ echo_message executed.")
    assert "echo_message" in result2.tools_used

    print("\n5️⃣ Testing: analyze_code_complexity...")
    fake_llm_3 = FakeLLM(responses=[
        LLMResponse(tool_calls=[{"id": "c3", "name": "analyze_code_complexity", "arguments": {
                    "file_path": "app/core/harness/loop.py"}}]),
        LLMResponse(content="The file has several classes.")
    ])
    loop3 = AgentLoop(llm=fake_llm_3, tools=registry, permissions=gate)
    result3 = await loop3.run("Analyze the loop")
    print(f"✅ analyze_code_complexity executed.")
    assert "analyze_code_complexity" in result3.tools_used

    print("\n6️⃣ Testing: run_tests...")
    fake_llm_4 = FakeLLM(responses=[
        LLMResponse(
            tool_calls=[{"id": "c4", "name": "run_tests", "arguments": {}}]),
        LLMResponse(content="Tests passed.")
    ])
    loop4 = AgentLoop(llm=fake_llm_4, tools=registry, permissions=gate)
    print("⏳ Running tests (this may take a while)...")
    result4 = await loop4.run("Run tests")
    print(f"✅ run_tests executed.")
    assert "run_tests" in result4.tools_used

    print("\n7️⃣ Closing MCP server...")
    await client.disconnect()
    print("✅ Server closed.")
    print("\n" + "="*50)
    print("🎉 ALL E2E TESTS PASSED")
    print("="*50 + "\n")
