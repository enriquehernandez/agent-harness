import os
from .registry import register_provider, get_llm, list_providers
from .base import BaseLLM, LLMResponse
from .providers.openai_provider import OpenAICompatibleProvider
from .providers.fake import FakeLLM

# Registrar OpenAI directo
register_provider(
    "openai",
    lambda **kw: OpenAICompatibleProvider(
        api_key=os.getenv("OPENAI_API_KEY", ""),
        model=kw.pop("model", os.getenv("OPENAI_MODEL", "gpt-4o")),
        **kw,
    ),
)

# Registrar OpenRouter
register_provider(
    "openrouter",
    lambda **kw: OpenAICompatibleProvider(
        api_key=os.getenv("OPENROUTER_API_KEY", ""),
        model=kw.pop("model", os.getenv("OPENROUTER_MODEL", "openai/gpt-4o")),
        base_url="https://openrouter.ai/api/v1",
        **kw,
    ),
)

# Registrar Groq
register_provider(
    "groq",
    lambda **kw: OpenAICompatibleProvider(
        api_key=os.getenv("GROQ_API_KEY", ""),
        model=kw.pop("model", os.getenv(
            "GROQ_MODEL", "llama-3.3-70b-versatile")),
        base_url="https://api.groq.com/openai/v1",
        **kw,
    ),
)

# Registrar FakeLLM para tests
register_provider("fake", lambda **kw: FakeLLM(**kw))

__all__ = ["BaseLLM", "LLMResponse", "get_llm",
           "list_providers", "register_provider"]
