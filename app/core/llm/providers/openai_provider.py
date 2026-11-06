import json
from typing import Any, AsyncIterator, Optional
from openai import AsyncOpenAI
from ..base import BaseLLM, LLMResponse


class OpenAICompatibleProvider(BaseLLM):
    """Funciona con OpenAI, OpenRouter, Groq, etc. (misma API)."""

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: Optional[str] = None,
        max_tokens: int = 128000,
        **client_kwargs: Any,
    ):
        self.model = model
        self._max_tokens = max_tokens
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            **client_kwargs,
        )

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tools,
            **kwargs,
        )
        choice = response.choices[0]
        msg = choice.message

        tool_calls = []
        if msg.tool_calls:
            for tc in msg.tool_calls:
                tool_calls.append({
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": json.loads(tc.function.arguments),
                })

        usage = {}
        if response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }

        return LLMResponse(
            content=msg.content,
            tool_calls=tool_calls,
            usage=usage,
            raw=response,
        )

    async def stream_chat(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tools,
            stream=True,
            **kwargs,
        )
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    def count_tokens(self, text: str) -> int:
        return len(text) // 4

    @property
    def supports_tool_calling(self) -> bool:
        return True

    @property
    def max_context_window(self) -> int:
        return self._max_tokens
