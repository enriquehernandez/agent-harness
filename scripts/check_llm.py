import asyncio
from app.core.llm import get_llm


async def main():
    # Prueba con FakeLLM (sin API key, sin coste)
    llm = get_llm("fake")
    resp = await llm.chat([{"role": "user", "content": "Hola"}])
    print("FakeLLM dice:", resp.content)

    # Si tienes OPENROUTER_API_KEY en .env, prueba el real:
    # llm = get_llm("openrouter")
    # resp = await llm.chat([{"role": "user", "content": "Hola"}])
    # print("OpenRouter dice:", resp.content)

if __name__ == "__main__":
    asyncio.run(main())
