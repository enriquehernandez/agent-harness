from .registry import register_provider, get_llm, list_providers
from .base import BaseLLM, LLMResponse
from .providers.openai_provider import OpenAICompatibleProvider
from .providers.fake import FakeLLM
from app.core.config import settings

# Registrar OpenAI directo
register_provider(
    "openai",
    lambda **kw: OpenAICompatibleProvider(
        api_key=settings.OPENAI_API_KEY,
        model=kw.pop("model", settings.OPENAI_MODEL),
        **kw,
    ),
)

# Registrar OpenRouter
register_provider(
    "openrouter",
    lambda **kw: OpenAICompatibleProvider(
        api_key=settings.OPENROUTER_API_KEY,
        model=kw.pop("model", settings.OPENROUTER_MODEL),
        base_url="https://openrouter.ai/api/v1",
        **kw,
    ),
)

# Registrar Groq
register_provider(
    "groq",
    lambda **kw: OpenAICompatibleProvider(
        api_key=settings.GROQ_API_KEY,
        model=kw.pop("model", settings.GROQ_MODEL),
        base_url="https://api.groq.com/openai/v1",
        **kw,
    ),
)

# Registrar FakeLLM para tests
register_provider("fake", lambda **kw: FakeLLM(**kw))

__all__ = ["BaseLLM", "LLMResponse", "get_llm",
           "list_providers", "register_provider"]
