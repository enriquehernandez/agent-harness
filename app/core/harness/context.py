import json
from typing import Any
from ..llm.base import BaseLLM
from .compaction import CompactionStrategy, SummarizationStrategy


class ContextManager:
    def __init__(
        self,
        system_prompt: str | None = None,
        strategy: CompactionStrategy | None = None
    ):
        self.messages: list[dict[str, Any]] = []
        self.strategy = strategy or SummarizationStrategy()
        if system_prompt:
            self.add_system(system_prompt)

    def add_system(self, content: str) -> None:
        if self.messages and self.messages[0]["role"] == "system":
            self.messages[0]["content"] = content
        else:
            self.messages.insert(0, {"role": "system", "content": content})

    def add_user(self, content: str) -> None:
        self.messages.append({"role": "user", "content": content})

    def add_assistant(self, content: str | None, tool_calls: list[dict] | None = None) -> None:
        msg: dict[str, Any] = {"role": "assistant", "content": content or ""}
        if tool_calls:
            msg["tool_calls"] = [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {
                        "name": tc["name"],
                        "arguments": json.dumps(tc["arguments"]),
                    },
                }
                for tc in tool_calls
            ]
        self.messages.append(msg)

    def add_tool_result(self, tool_call_id: str, content: str) -> None:
        self.messages.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": content,
        })

    def get_messages(self) -> list[dict[str, Any]]:
        return self.messages

    def estimate_tokens(self) -> int:
        """Estimación rápida (1 token ~ 4 caracteres)."""
        total_chars = sum(len(str(m.get("content", "")))
                          for m in self.messages)
        return total_chars // 4

    def clear(self) -> None:
        """Limpia la conversación manteniendo el system prompt."""
        system = self.messages[0] if self.messages and self.messages[0]["role"] == "system" else None
        self.messages = [system] if system else []

    async def maybe_compact(self, llm: BaseLLM) -> bool:
        """Si se supera el 80% del contexto, compacta. Devuelve True si compactó."""
        estimated = self.estimate_tokens()
        limit = llm.max_context_window

        if estimated > (limit * 0.8):
            self.messages = await self.strategy.compact(self.messages, llm)
            return True
        return False

    async def force_compact(self, llm: BaseLLM) -> None:
        """Fuerza la compactación (usado por el comando /compact)."""
        self.messages = await self.strategy.compact(self.messages, llm)
