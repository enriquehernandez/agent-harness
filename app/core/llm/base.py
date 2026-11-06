from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Optional


@dataclass
class LLMResponse:
    """Respuesta normalizada, independiente del proveedor."""
    content: Optional[str] = None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    # Formato: {"id": str, "name": str, "arguments": dict}
    usage: dict[str, int] = field(default_factory=dict)
    raw: Any = None  # Respuesta original por si se necesita debuggear


class BaseLLM(ABC):
    """Interfaz abstracta para cualquier proveedor de LLM."""

    @abstractmethod
    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Enviar mensajes y obtener respuesta normalizada."""
        ...

    @abstractmethod
    async def stream_chat(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Versión streaming (solo texto, por simplicidad)."""
        ...

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """Estimación de tokens (para compaction)."""
        ...

    @property
    @abstractmethod
    def supports_tool_calling(self) -> bool:
        """Indica si el modelo soporta tools nativamente."""
        ...

    # 🔥 NUEVO: Límite de contexto del modelo
    @property
    @abstractmethod
    def max_context_window(self) -> int:
        """Límite de tokens del modelo (ej. 128000 para GPT-4o)."""
        ...
