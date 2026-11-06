import asyncio
from app.core.llm import get_llm
from app.core.llm.base import LLMResponse
from app.core.harness import AgentLoop, ToolRegistry
from app.tools import register_core_tools


async def main():
    # 1. Preparamos el registro y las tools
    registry = ToolRegistry()
    register_core_tools(registry)

    # 2. Simulamos un LLM que "razona" en 3 pasos:
    # Turno 1: Quiere leer el pyproject.toml
    # Turno 2: Quiere ejecutar un comando bash
    # Turno 3: Da la respuesta final
    fake = get_llm("fake", responses=[
        LLMResponse(
            content=None,
            tool_calls=[{
                "id": "call_1",
                "name": "read_file",
                "arguments": {"path": "pyproject.toml"},
            }],
        ),
        LLMResponse(
            content=None,
            tool_calls=[{
                "id": "call_2",
                "name": "bash",
                "arguments": {"command": "echo 'Hola desde el agente!' && ls app"},
            }],
        ),
        LLMResponse(
            content="He revisado el pyproject y el sistema. Todo listo.",
            usage={"total_tokens": 50},
        ),
    ])

    # 3. Ejecutamos el bucle
    loop = AgentLoop(llm=fake, tools=registry)
    result = await loop.run("Revisa la configuración del proyecto.")

    print("=== Resultado del AgentLoop con Herramientas Locales ===")
    print(f"Respuesta final : {result.final_answer}")
    print(f"Pasos           : {result.steps}")
    print(f"Tools usadas    : {result.tools_used}")


if __name__ == "__main__":
    asyncio.run(main())
