import pytest
from app.core.llm.base import BaseLLM, LLMResponse


@pytest.mark.asyncio
async def test_llm_stream_contract(fake_llm):
    """Verifica que cualquier LLM cumpla el contrato de stream_chat."""
    fake_llm._responses = [
        LLMResponse(
            content="Hola",
            tool_calls=[{"id": "1", "name": "test", "arguments": {}}],
            usage={"total_tokens": 10}
        )
    ]

    chunks = []
    async for chunk in fake_llm.stream_chat([]):
        chunks.append(chunk)

    # 1. Debe emitir al menos un string
    assert any(isinstance(c, str)
               for c in chunks), "Falta el texto en el stream"

    # 2. Debe emitir los tool_calls
    tool_chunks = [c for c in chunks if isinstance(
        c, dict) and c.get("type") == "tool_call"]
    assert len(tool_chunks) > 0, "Faltan los tool_calls en el stream"

    # 3. Debe emitir el usage
    usage_chunks = [c for c in chunks if isinstance(
        c, dict) and c.get("type") == "usage"]
    assert len(usage_chunks) > 0, "Falta el usage en el stream"
