from typing import Callable, Type
from .base import BaseLLM

# Internal dictionary: provider_name -> builder_function
_PROVIDER_REGISTRY: dict[str, Callable[..., BaseLLM]] = {}


def register_provider(name: str, builder: Callable[..., BaseLLM]) -> None:
    """Registers a function that builds an LLM. Called at startup."""
    _PROVIDER_REGISTRY[name.lower()] = builder


def get_llm(provider: str, **kwargs) -> BaseLLM:
    """Gets an LLM instance based on the configured provider."""
    key = provider.lower()
    if key not in _PROVIDER_REGISTRY:
        available = ", ".join(_PROVIDER_REGISTRY.keys())
        raise ValueError(
            f"Provider '{provider}' not registered. Available: {available}")
    return _PROVIDER_REGISTRY[key](**kwargs)


def list_providers() -> list[str]:
    return list(_PROVIDER_REGISTRY.keys())
