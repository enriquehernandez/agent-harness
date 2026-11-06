import pytest
from app.core.llm import get_llm, list_providers
from app.core.llm.base import BaseLLM


def test_list_providers():
    providers = list_providers()
    assert "fake" in providers
    assert "openai" in providers
    assert "openrouter" in providers


def test_get_fake_llm():
    llm = get_llm("fake")
    assert isinstance(llm, BaseLLM)
    assert llm.supports_tool_calling is True
    assert llm.max_context_window == 4096


def test_get_unknown_provider():
    with pytest.raises(ValueError, match="Proveedor 'inventado' no registrado"):
        get_llm("inventado")


@pytest.mark.asyncio
async def test_fake_llm_stream_and_count():
    from app.core.llm.providers.fake import FakeLLM
    from app.core.llm.base import LLMResponse

    fake = FakeLLM(responses=[LLMResponse(content="Hola")])

    # Cubrir count_tokens
    assert fake.count_tokens("12345678") == 2

    # Cubrir stream_chat
    chunks = []
    async for chunk in fake.stream_chat([]):
        chunks.append(chunk)
    assert chunks == ["Hola"]


@pytest.mark.asyncio
async def test_fake_llm_default_response():
    from app.core.llm.providers.fake import FakeLLM
    fake = FakeLLM(responses=[])
    resp = await fake.chat([])  # Se queda sin respuestas
    assert resp.content == "Respuesta simulada por FakeLLM."
