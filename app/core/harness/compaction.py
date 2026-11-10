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

        # 🔥 Usamos el índice seguro en lugar de un corte ciego
        safe_split = self._find_safe_split_index(messages)

        # Si el punto seguro es antes del system prompt, no podemos compactar
        if safe_split <= start_idx:
            return messages

        recent_msgs = messages[safe_split:]
        old_msgs = messages[start_idx:safe_split]

        if not old_msgs:
            return messages

        summary_prompt = [
            {"role": "system", "content": "Eres un asistente que resume conversaciones. Sé conciso y mantén los hechos clave, decisiones y herramientas usadas."},
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
