import asyncio
from pathlib import Path

from app.core.llm import get_llm
from app.core.harness.loop import AgentLoop
from app.core.harness.tool import ToolRegistry
from app.core.harness.permissions import PermissionGate
from app.core.harness.context import ContextManager
from app.core.config import settings
from app.tools.critic import CriticTool


async def ejecutar_prueba(prompt: str, system_prompt: str, nombre_prueba: str):
    print(f"\n{'='*60}")
    print(f"🧪 {nombre_prueba}")
    print(f"{'='*60}\n")

    # 1. Configurar el Agente Principal
    agent_llm = get_llm(settings.LLM_PROVIDER)
    tools = ToolRegistry()
    permissions = PermissionGate()

    # 2. Configurar el Crítico
    critic_model = settings.A2A_REVIEWER_MODEL or None
    critic_llm = get_llm(settings.LLM_PROVIDER, model=critic_model)
    critic_tool = CriticTool(llm=critic_llm)

    # 3. Crear el AgentLoop
    agent = AgentLoop(
        llm=agent_llm,
        tools=tools,
        permissions=permissions,
        provider_name=settings.LLM_PROVIDER,
        critic_tool=critic_tool
    )

    ctx = ContextManager(system_prompt=system_prompt)

    print(f"👤 Usuario: {prompt}\n")
    print("🤖 Agente respondiendo...\n" + "-"*40)

    # 4. Consumir el stream
    async for event in agent.stream(prompt, context=ctx):
        if event.type == "text_chunk":
            print(event.data["text"], end="", flush=True)

        elif event.type == "result":
            print("\n" + "-"*40)
            print(f"✅ Proceso terminado con éxito.")
            print(
                f"📊 Tokens usados: {event.data.get('usage_total', {}).get('total_tokens', 0)}")

        elif event.type == "error":
            print("\n" + "-"*40)
            print(f"❌ Error: {event.data.get('message')}")


async def main():
    print("🚀 Iniciando pruebas del Hook de Auto-Reflexión...")

    # ====================================================================
    # PRUEBA 1: Caso casual (El crítico debe aprobar)
    # ====================================================================
    test_agents_file = Path("AGENTS_TEST.md")
    test_agents_file.write_text(
        "# Reglas de Prueba\n\n- Tienes prohibido usar la palabra 'HOLA'.\n",
        encoding="utf-8"
    )
    system_prompt_casual = (
        "Eres un asistente útil.\n"
        "Tus reglas están en AGENTS_TEST.md.\n"
        f"--- START OF AGENTS_TEST.md ---\n{test_agents_file.read_text(encoding='utf-8')}\n--- END ---"
    )
    await ejecutar_prueba(
        prompt="Dime 'HOLA' y cuéntame un chiste corto.",
        system_prompt=system_prompt_casual,
        nombre_prueba="PRUEBA 1: Regla prohibida (El agente se autocensura)"
    )

    # ====================================================================
    # PRUEBA 2: El crítico tiene una regla oculta (El agente no la sabe)
    # ====================================================================
    print("\n\n⏳ Esperando 3 segundos...")
    await asyncio.sleep(3)

    # Creamos un AGENTS.md falso SOLO para el crítico
    # El agente no leerá este archivo en su System Prompt
    fake_agents = test_agents_file  # Path("AGENTS.md")
    original_agents_content = ""
    if fake_agents.exists():
        original_agents_content = fake_agents.read_text(encoding="utf-8")

    # El crítico leerá que "print" está prohibido
    fake_agents.write_text(
        "# Reglas del Proyecto\n- TIENES ESTRICTAMENTE PROHIBIDO usar `print()` en el código. Debes usar `logger`.",
        encoding="utf-8"
    )

    # El System Prompt del agente NO menciona la regla del print
    system_prompt_codigo = (
        "Eres un ingeniero de software senior. Escribe código limpio y conciso."
    )

    # Le pedimos al agente que use print (él no sabe que está prohibido)
    prompt_conflictivo = (
        "Escribe una función de Python llamada 'saludar' que use `print('Hola Mundo')` "
        "para imprimir en pantalla. Usa `print` directamente."
    )

    await ejecutar_prueba(
        prompt=prompt_conflictivo,
        system_prompt=system_prompt_codigo,
        nombre_prueba="PRUEBA 2: Regla oculta (El crítico debe RECHAZAR)"
    )

    # # Restauramos el AGENTS.md original
    # if original_agents_content:
    #     fake_agents.write_text(original_agents_content, encoding="utf-8")
    # else:
    #     fake_agents.unlink()

    # Limpieza
    if test_agents_file.exists():
        test_agents_file.unlink()

if __name__ == "__main__":
    asyncio.run(main())
