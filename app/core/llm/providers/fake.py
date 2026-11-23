from typing import Any, AsyncIterator, Optional
from ..base import BaseLLM, LLMResponse


class FakeLLM(BaseLLM):
    """Simula respuestas predecibles para tests del Harness."""

    def __init__(
        self,
        responses: Optional[list[LLMResponse]] = None,
        max_tokens: int = 4096,
        model_name: str = "fake-model",
    ):
        self._responses = responses or []
        self._call_count = 0
        self._max_tokens = max_tokens
        self.model_name = model_name

    async def chat(self, messages, tools=None, **kwargs) -> LLMResponse:
        if self._call_count < len(self._responses):
            resp = self._responses[self._call_count]
            self._call_count += 1
            return resp
        return LLMResponse(content="Simulated response by FakeLLM.")

    async def stream_chat(self, messages, tools=None, **kwargs) -> AsyncIterator:
        resp = await self.chat(messages, tools, **kwargs)

        if resp.content:
            yield resp.content

        if resp.tool_calls:
            for tc in resp.tool_calls:
                yield {
                    "type": "tool_call",
                    "id": tc["id"],
                    "name": tc["name"],
                    "arguments": tc["arguments"],
                }

        if resp.usage:
            yield {"type": "usage", "usage": resp.usage}

    def count_tokens(self, text: str) -> int:
        return len(text) // 4

    @property
    def supports_tool_calling(self) -> bool:
        return True

    @property
    def max_context_window(self) -> int:
        return self._max_tokens
