from typing import Callable, Type
from .base import BaseLLM

# Diccionario interno: nombre_proveedor -> función constructora
_PROVIDER_REGISTRY: dict[str, Callable[..., BaseLLM]] = {}


def register_provider(name: str, builder: Callable[..., BaseLLM]) -> None:
    """Registra una función que construye un LLM. Se llama al inicio."""
    _PROVIDER_REGISTRY[name.lower()] = builder


def get_llm(provider: str, **kwargs) -> BaseLLM:
    """Obtiene una instancia del LLM según el proveedor configurado."""
    key = provider.lower()
    if key not in _PROVIDER_REGISTRY:
        available = ", ".join(_PROVIDER_REGISTRY.keys())
        raise ValueError(
            f"Proveedor '{provider}' no registrado. Disponibles: {available}")
    return _PROVIDER_REGISTRY[key](**kwargs)


def list_providers() -> list[str]:
    return list(_PROVIDER_REGISTRY.keys())
