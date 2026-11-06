import pytest
from unittest.mock import AsyncMock
from app.core.harness.context import ContextManager
from app.core.llm.base import LLMResponse


@pytest.mark.asyncio
async def test_context_compaction_trigger(fake_llm):
    """Verifica que la compactación se dispare cuando se supera el 80% del límite."""
    fake_llm._max_tokens = 100
    # Simulamos que el LLM responderá un resumen
    fake_llm._responses = [LLMResponse(content="[Resumen de mensajes viejos]")]

    ctx = ContextManager(system_prompt="System prompt")
    # Llenamos el contexto para pasar el 80% (100 * 0.8 = 80 tokens)
    for _ in range(10):
        ctx.add_user("A" * 50)

    compacted = await ctx.maybe_compact(fake_llm)

    assert compacted is True
    assert len(ctx.messages) == 6  # system original + resumen + ultimos 4
    assert "[Resumen de mensajes viejos]" in ctx.messages[1]["content"]


@pytest.mark.asyncio
async def test_compaction_llm_error(fake_llm):
    """Cubre el bloque except cuando el LLM falla al intentar resumir."""
    fake_llm._max_tokens = 100
    fake_llm.chat = AsyncMock(side_effect=Exception("API Error"))

    ctx = ContextManager(system_prompt="System")
    for _ in range(10):
        ctx.add_user("A" * 50)

    await ctx.maybe_compact(fake_llm)
    # Debe inyectar el mensaje de error en el resumen
    assert "[Error al resumir la conversación antigua: API Error]" in ctx.messages[1]["content"]


@pytest.mark.asyncio
async def test_compaction_no_old_messages(fake_llm):
    """Cubre la línea 34: retorno temprano cuando no hay old_msgs que resumir."""
    ctx = ContextManager(system_prompt="System")
    # keep_last_n es 4. Si tenemos 5 mensajes (1 system + 4 user), el código entra en el if not old_msgs
    for i in range(4):
        ctx.add_user(f"Msg {i}")

    assert len(ctx.messages) == 5
    await ctx.force_compact(fake_llm)
    # Al no haber mensajes viejos, debe retornar el mismo contexto intacto
    assert len(ctx.messages) == 5


@pytest.mark.asyncio
async def test_force_compact(fake_llm):
    """Cubre la llamada directa a force_compact."""
    fake_llm._responses = [LLMResponse(content="[Resumen Forzado]")]
    ctx = ContextManager(system_prompt="System")
    ctx.add_user("Mensaje 1")
    ctx.add_user("Mensaje 2")

    await ctx.force_compact(fake_llm)
    assert len(ctx.messages) <= 3


def test_context_add_system_overwrite():
    """Cubre la rama donde ya existe un system prompt y se sobrescribe."""
    ctx = ContextManager(system_prompt="Original")
    ctx.add_system("Nuevo")
    assert ctx.messages[0]["content"] == "Nuevo"
    assert len(ctx.messages) == 1


def test_context_clear():
    ctx = ContextManager(system_prompt="System")
    ctx.add_user("Hola")
    assert len(ctx.messages) == 2

    ctx.clear()
    assert len(ctx.messages) == 1
    assert ctx.messages[0]["role"] == "system"
