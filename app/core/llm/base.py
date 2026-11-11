from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Optional


@dataclass
class LLMResponse:
    """Normalized response, provider-independent."""
    content: Optional[str] = None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    usage: dict[str, int] = field(default_factory=dict)
    raw: Any = None


class BaseLLM(ABC):
    """Abstract interface for any LLM provider."""

    @abstractmethod
    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Send messages and get normalized response."""
        ...

    @abstractmethod
    async def stream_chat(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Streaming version (text only, for simplicity)."""
        ...

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """Token estimation (for compaction)."""
        ...

    @property
    @abstractmethod
    def supports_tool_calling(self) -> bool:
        """Indicates if the model natively supports tools."""
        ...

    @property
    @abstractmethod
    def max_context_window(self) -> int:
        """Model token limit (e.g., 128000 for GPT-4o)."""
        ...
