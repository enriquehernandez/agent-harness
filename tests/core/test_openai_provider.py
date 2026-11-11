import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.core.llm.providers.openai_provider import OpenAICompatibleProvider


@pytest.mark.asyncio
@patch("app.core.llm.providers.openai_provider.AsyncOpenAI")
async def test_openai_provider_chat_and_stream(mock_async_openai):
    mock_client_instance = mock_async_openai.return_value

    mock_message = MagicMock()
    mock_message.content = "Hello from mock"
    mock_message.tool_calls = None
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_usage = MagicMock()
    mock_usage.prompt_tokens = 10
    mock_usage.completion_tokens = 5
    mock_usage.total_tokens = 15
    mock_usage.prompt_tokens_details.cached_tokens = 0
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_response.usage = mock_usage

    mock_client_instance.chat.completions.create = AsyncMock(
        return_value=mock_response)

    provider = OpenAICompatibleProvider(api_key="fake_key", model="fake_model")
    result = await provider.chat([])

    assert result.content == "Hello from mock"
    assert result.usage["total_tokens"] == 15

    async def mock_stream_generator():
        chunk = MagicMock()
        chunk.choices[0].delta.content = "Chunk"
        yield chunk

    mock_client_instance.chat.completions.create = AsyncMock(
        return_value=mock_stream_generator())

    chunks = []
    async for c in provider.stream_chat([]):
        chunks.append(c)
    assert chunks == ["Chunk"]
    assert provider.max_context_window == 128000
    assert provider.supports_tool_calling is True
    assert provider.count_tokens("1234") == 1


@pytest.mark.asyncio
@patch("app.core.llm.providers.openai_provider.AsyncOpenAI")
async def test_openai_provider_error(mock_async_openai):
    mock_client = mock_async_openai.return_value
    mock_client.chat.completions.create = AsyncMock(
        side_effect=Exception("API Error"))

    provider = OpenAICompatibleProvider(api_key="key", model="model")
    with pytest.raises(Exception, match="API Error"):
        await provider.chat([])


@pytest.mark.asyncio
@patch("app.core.llm.providers.openai_provider.AsyncOpenAI")
async def test_openai_provider_tool_calls(mock_async_openai):
    mock_client = mock_async_openai.return_value

    mock_tc = MagicMock()
    mock_tc.id = "call_1"
    mock_tc.function.name = "my_tool"
    mock_tc.function.arguments = '{"a": 1}'

    mock_message = MagicMock()
    mock_message.content = None
    mock_message.tool_calls = [mock_tc]

    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=mock_message)]
    mock_response.usage = None

    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    provider = OpenAICompatibleProvider(api_key="key", model="model")
    res = await provider.chat([])

    assert len(res.tool_calls) == 1
    assert res.tool_calls[0]["name"] == "my_tool"
    assert res.tool_calls[0]["arguments"] == {"a": 1}


@pytest.mark.asyncio
@patch("app.core.llm.providers.openai_provider.AsyncOpenAI")
async def test_openai_provider_prompt_caching_and_error(mock_async_openai):
    mock_client = mock_async_openai.return_value

    # Simulamos una respuesta válida
    mock_message = MagicMock()
    mock_message.content = "Cached response"
    mock_message.tool_calls = None
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_usage = MagicMock()
    mock_usage.prompt_tokens = 10
    mock_usage.completion_tokens = 5
    mock_usage.total_tokens = 15
    mock_usage.prompt_tokens_details.cached_tokens = 8  # 🔥 Simulamos Cache Hit
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_response.usage = mock_usage

    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    provider = OpenAICompatibleProvider(api_key="key", model="model")
    # Enviamos un system prompt para activar el caching
    messages = [{"role": "system", "content": "System prompt"}]

    # Forzamos ENABLE_PROMPT_CACHING = True
    with patch("app.core.config.settings.ENABLE_PROMPT_CACHING", True):
        res = await provider.chat(messages)

    assert res.content == "Cached response"
    # Verificamos que el system prompt se transformó en lista con cache_control
    assert isinstance(messages[0]["content"], list)
    assert messages[0]["content"][0]["cache_control"]["type"] == "ephemeral"
