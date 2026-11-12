import asyncio
import json
from typing import Any, AsyncIterator, Optional
from openai import AsyncOpenAI
from ..base import BaseLLM, LLMResponse
from app.core.logger import logger


class OpenAICompatibleProvider(BaseLLM):
    """Works with OpenAI, OpenRouter, Groq, etc. (same API)."""

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

        # 🔥 PROMPT CACHING LOGIC
        from app.core.config import settings
        if getattr(settings, "ENABLE_PROMPT_CACHING", False) and messages:
            if messages[0]["role"] == "system" and "content" in messages[0]:
                if isinstance(messages[0]["content"], str):
                    messages[0]["content"] = [
                        {
                            "type": "text",
                            "text": messages[0]["content"],
                            "cache_control": {"type": "ephemeral"}
                        }
                    ]

        payload = {
            "model": self.model,
            "messages": messages,
            "tools": tools,
        }
        logger.debug(json.dumps(payload, indent=2, ensure_ascii=False))

        # response = await self.client.chat.completions.create(
        #     model=self.model,
        #     messages=messages,
        #     tools=tools,
        #     **kwargs,
        # )

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools,
                **kwargs,
            )
        except Exception as e:
            error_str = str(e)
            if "503" in error_str or "Provider returned error" in error_str:
                raise Exception(
                    f"⚠️ El proveedor del LLM ({self.model}) está caído o sobrecargado. "
                    f"Intenta de nuevo en unos segundos o cambia de modelo con /model."
                )
            raise e

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
            if hasattr(response.usage, "prompt_tokens_details"):
                cached = getattr(
                    response.usage.prompt_tokens_details, "cached_tokens", 0)
                if cached > 0:
                    logger.debug(f"✅ Cache Hit: {cached} tokens saved.")

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
    ) -> AsyncIterator[Any]:
        # 🔥 Logging
        payload = {
            "model": self.model,
            "messages": messages,
            "tools": tools,
        }
        logger.debug(json.dumps(payload, indent=2, ensure_ascii=False))

        # stream = await self.client.chat.completions.create(
        #     model=self.model,
        #     messages=messages,
        #     tools=tools,
        #     stream=True,
        #     stream_options={"include_usage": True},  # 🔥 Para obtener usage
        #     **kwargs,
        # )
        stream = await asyncio.wait_for(
            self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools,
                stream=True,
                stream_options={"include_usage": True},
                **kwargs,
            ),
            timeout=60.0  # 🔥 Timeout de 60s para la conexión
        )

        # 🔥 Acumulamos los tool_calls mientras llegan por partes
        current_tool_calls = []
        final_usage = {}

        async for chunk in stream:
            if hasattr(chunk, "usage") and chunk.usage:
                final_usage = {
                    "prompt_tokens": chunk.usage.prompt_tokens,
                    "completion_tokens": chunk.usage.completion_tokens,
                    "total_tokens": chunk.usage.total_tokens,
                }

            delta = chunk.choices[0].delta if chunk.choices else None
            if not delta:
                continue

            # 1. Emitimos texto
            if delta.content:
                yield delta.content

            # 2. Acumulamos tool_calls
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    # Si es un tool_call nuevo, lo añadimos
                    if tc.index is not None:
                        if len(current_tool_calls) <= tc.index:
                            current_tool_calls.append({
                                "id": tc.id or "",
                                "name": tc.function.name or "",
                                "arguments": ""
                            })
                        # Si es una parte del mismo tool_call, actualizamos
                        if tc.id:
                            current_tool_calls[tc.index]["id"] = tc.id
                        if tc.function.name:
                            current_tool_calls[tc.index]["name"] = tc.function.name
                        if tc.function.arguments:
                            current_tool_calls[tc.index]["arguments"] += tc.function.arguments

        # 🔥 Al terminar el stream, emitimos los tool_calls completos
        for tc in current_tool_calls:
            if tc["name"]:
                yield {
                    "type": "tool_call",
                    "id": tc["id"] or f"call_{tc['name']}",
                    "name": tc["name"],
                    "arguments": json.loads(tc["arguments"] or "{}"),
                }

        # 🔥 Emitimos el usage final (para el AgentLoop)
        if final_usage:
            yield {"type": "usage", "usage": final_usage}

    def count_tokens(self, text: str) -> int:
        return len(text) // 4

    @property
    def supports_tool_calling(self) -> bool:
        return True

    @property
    def max_context_window(self) -> int:
        return self._max_tokens
