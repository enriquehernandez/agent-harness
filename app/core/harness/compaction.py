from abc import ABC, abstractmethod
from typing import Any
from ..llm.base import BaseLLM


class CompactionStrategy(ABC):
    @abstractmethod
    async def compact(self, messages: list[dict[str, Any]], llm: BaseLLM) -> list[dict[str, Any]]:
        ...


class SummarizationStrategy(CompactionStrategy):
    def __init__(self, keep_last_n: int = 4):
        self.keep_last_n = keep_last_n

    def _find_safe_split_index(self, messages: list[dict[str, Any]]) -> int:
        start_index = max(0, len(messages) - self.keep_last_n)
        while start_index > 0 and messages[start_index].get("role") == "tool":
            start_index -= 1
        return start_index

    async def compact(self, messages: list[dict[str, Any]], llm: BaseLLM) -> list[dict[str, Any]]:
        if len(messages) <= self.keep_last_n + 1:
            return messages

        system_msg = messages[0] if messages[0]["role"] == "system" else None
        start_idx = 1 if system_msg else 0

        safe_split = self._find_safe_split_index(messages)
        if safe_split <= start_idx:
            return messages

        recent_msgs = messages[safe_split:]
        old_msgs = messages[start_idx:safe_split]

        if not old_msgs:
            return messages  # pragma: no cover

        summary_prompt = [
            {"role": "system", "content": "You are an assistant that summarizes conversations. Be concise and keep key facts, decisions, and tools used."},
            {"role": "user", "content": f"Summarize the following conversation:\n\n{old_msgs}"}
        ]

        try:
            response = await llm.chat(summary_prompt)
            summary_text = response.content or "Summary not available."
        except Exception as e:
            summary_text = f"[Error summarizing: {e}]"

        new_messages = []
        if system_msg:
            new_messages.append(system_msg)

        new_messages.append({
            "role": "system",
            "content": f"--- Summary of previous conversation ---\n{summary_text}\n----------------------------------------"
        })

        new_messages.extend(recent_msgs)
        return new_messages


class SlidingWindowStrategy(CompactionStrategy):
    def __init__(self, keep_last_n: int = 6):
        self.keep_last_n = keep_last_n

    async def compact(self, messages: list[dict[str, Any]], llm: BaseLLM) -> list[dict[str, Any]]:
        if len(messages) <= self.keep_last_n + 1:
            return messages
        system_msg = messages[0] if messages[0]["role"] == "system" else None
        recent_msgs = messages[-self.keep_last_n:]
        new_messages = []
        if system_msg:
            new_messages.append(system_msg)
        new_messages.extend(recent_msgs)
        return new_messages


class NoneStrategy(CompactionStrategy):
    async def compact(self, messages: list[dict[str, Any]], llm: BaseLLM) -> list[dict[str, Any]]:
        return messages
