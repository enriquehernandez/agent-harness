import asyncio
from app.core.llm import get_llm
from app.core.llm.base import LLMResponse
from app.core.harness import AgentLoop, ToolRegistry
from app.core.harness.permissions import PermissionGate, Decision
from app.mcp.client import MCPClient


async def main():
    mcp_client = MCPClient(
        command="uv",
        args=["run", "python", "scripts/dummy_mcp_server.py"]
    )

    print("Conectando al servidor MCP...")
    await mcp_client.connect()

    registry = ToolRegistry()
    await mcp_client.register_tools(registry)

    print(f"Herramientas descubiertas: {registry.names()}")
    print("-" * 40)

    fake_responses = [
        LLMResponse(
            content=None,
            tool_calls=[{
                "id": "call_mcp_1",
                "name": "get_system_info",
                "arguments": {},
            }],
            usage={"total_tokens": 10}
        ),
        LLMResponse(
            content="He consultado el sistema operativo usando MCP.",
            usage={"total_tokens": 10}
        ),
    ]

    fake = get_llm("fake", responses=fake_responses)

    # 🔥 SOLUCIÓN: Inyectar un PermissionGate configurado para permitir MCP
    gate = PermissionGate()
    gate.policies = {
        "get_system_info": Decision.ALLOW,
        "echo_message": Decision.ALLOW,
    }

    loop = AgentLoop(llm=fake, tools=registry, permissions=gate)
    result = await loop.run("¿Qué sistema operativo tengo?")

    print(f"Respuesta: {result.final_answer}")
    print(f"Tools usadas: {result.tools_used}")
    print("-" * 40)

    await mcp_client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
