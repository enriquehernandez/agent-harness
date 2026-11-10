import json
from typing import Any, AsyncIterator, Optional
from openai import AsyncOpenAI
from ..base import BaseLLM, LLMResponse
from app.core.logger import logger


class OpenAICompatibleProvider(BaseLLM):
    def __init__(self, api_key: str, model: str, base_url: Optional[str] = None, max_tokens: int = 128000, **client_kwargs: Any):
        self.model = model
        self._max_tokens = max_tokens
        self.client = AsyncOpenAI(
            api_key=api_key, base_url=base_url, **client_kwargs)

    async def chat(self, messages: list[dict[str, Any]], tools: Optional[list[dict[str, Any]]] = None, **kwargs: Any) -> LLMResponse:
        from app.core.config import settings
        if getattr(settings, "ENABLE_PROMPT_CACHING", False) and messages:
            if messages[0]["role"] == "system" and "content" in messages[0]:
                if isinstance(messages[0]["content"], str):
                    messages[0]["content"] = [
                        {"type": "text", "text": messages[0]["content"], "cache_control": {"type": "ephemeral"}}]

        # 🔥 LOGGEAMOS EL PAYLOAD COMPLETO PARA EL DEBUG PANEL
        payload = {
            "model": self.model,
            "messages": messages,
            "tools": tools,
        }
        logger.debug(json.dumps(payload, indent=2, ensure_ascii=False))

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
                tool_calls.append({"id": tc.id, "name": tc.function.name,
                                  "arguments": json.loads(tc.function.arguments)})

        usage = {}
        if response.usage:
            usage = {"prompt_tokens": response.usage.prompt_tokens, "completion_tokens":
                     response.usage.completion_tokens, "total_tokens": response.usage.total_tokens}
            if hasattr(response.usage, "prompt_tokens_details"):
                cached = getattr(
                    response.usage.prompt_tokens_details, "cached_tokens", 0)
                if cached > 0:
                    logger.debug(f"✅ Cache Hit: {cached} tokens ahorrados.")

        return LLMResponse(content=msg.content, tool_calls=tool_calls, usage=usage, raw=response)

    async def stream_chat(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        # (Mantenemos el stream_chat igual que antes)
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
