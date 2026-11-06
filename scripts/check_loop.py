import asyncio
from app.core.llm import get_llm
from app.core.llm.base import LLMResponse
from app.core.harness import AgentLoop, FunctionTool, ToolRegistry, ContextManager


def add_numbers(a: int, b: int) -> int:
    return a + b


async def main():
    # 1. Registramos una tool
    registry = ToolRegistry()
    registry.register(FunctionTool(
        name="add_numbers",
        description="Suma dos números enteros.",
        parameters_schema={
            "type": "object",
            "properties": {
                "a": {"type": "integer"},
                "b": {"type": "integer"},
            },
            "required": ["a", "b"],
        },
        func=add_numbers,
    ))

    # 2. Le decimos al FakeLLM qué debe responder en cada turno
    fake = get_llm("fake", responses=[
        # Turno 1: pide usar la tool
        LLMResponse(
            content=None,
            tool_calls=[{
                "id": "call_1",
                "name": "add_numbers",
                "arguments": {"a": 2, "b": 3},
            }],
            usage={"total_tokens": 20},
        ),
        # Turno 2: da la respuesta final usando el resultado inyectado
        LLMResponse(content="El resultado es 5.", usage={"total_tokens": 15}),
    ])

    # 3. Ejecutamos el bucle
    loop = AgentLoop(llm=fake, tools=registry)
    result = await loop.run("¿Cuánto es 2 + 3?")

    print("=== Resultado del AgentLoop ===")
    print(f"Respuesta final : {result.final_answer}")
    print(f"Pasos           : {result.steps}")
    print(f"Tools usadas    : {result.tools_used}")
    print(f"Tokens totales  : {result.usage_total}")


if __name__ == "__main__":
    asyncio.run(main())
