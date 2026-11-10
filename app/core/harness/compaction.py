# app/core/harness/compaction.py
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
        """
        Encuentra el índice seguro para dividir el historial.
        Garantiza que no se separe un 'tool' de su 'assistant' que lo llamó.
        """
        # Empezamos desde el final - keep_last_n
        start_index = max(0, len(messages) - self.keep_last_n)

        # Retrocedemos mientras el mensaje en start_index sea de tipo 'tool'
        # (porque no podemos dejar huérfano un 'tool' al inicio del historial reciente)
        while start_index > 0 and messages[start_index].get("role") == "tool":
            start_index -= 1

        return start_index

    async def compact(self, messages: list[dict[str, Any]], llm: BaseLLM) -> list[dict[str, Any]]:
        if len(messages) <= self.keep_last_n + 1:
            return messages

        system_msg = messages[0] if messages[0]["role"] == "system" else None
        start_idx = 1 if system_msg else 0

        recent_msgs = messages[-self.keep_last_n:]
        old_msgs = messages[start_idx:-self.keep_last_n]

        if not old_msgs:
            return messages

        summary_prompt = [
            {"role": "system", "content": "Eres un asistente que resume conversaciones. Sé conciso."},
            {"role": "user", "content": f"Resume la siguiente conversación:\n\n{old_msgs}"}
        ]

        try:
            response = await llm.chat(summary_prompt)
            summary_text = response.content or "Resumen no disponible."
        except Exception as e:
            summary_text = f"[Error al resumir: {e}]"

        new_messages = []
        if system_msg:
            new_messages.append(system_msg)

        new_messages.append({
            "role": "system",
            "content": f"--- Resumen de la conversación anterior ---\n{summary_text}\n-------------------------------------------"
        })

        new_messages.extend(recent_msgs)
        return new_messages

# 🔥 NUEVA ESTRATEGIA: Sliding Window (Descartar los más viejos)


class SlidingWindowStrategy(CompactionStrategy):
    def __init__(self, keep_last_n: int = 6):
        self.keep_last_n = keep_last_n

    async def compact(self, messages: list[dict[str, Any]], llm: BaseLLM) -> list[dict[str, Any]]:
        if len(messages) <= self.keep_last_n + 1:
            return messages

        # Mantenemos el system prompt original y los últimos N mensajes
        system_msg = messages[0] if messages[0]["role"] == "system" else None
        recent_msgs = messages[-self.keep_last_n:]

        new_messages = []
        if system_msg:
            new_messages.append(system_msg)
        new_messages.extend(recent_msgs)

        return new_messages

# 🔥 NUEVA ESTRATEGIA: None (No hacer nada)


class NoneStrategy(CompactionStrategy):
    async def compact(self, messages: list[dict[str, Any]], llm: BaseLLM) -> list[dict[str, Any]]:
        return messages
