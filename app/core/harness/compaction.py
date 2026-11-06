from abc import ABC, abstractmethod
from typing import Any
from ..llm.base import BaseLLM


class CompactionStrategy(ABC):
    @abstractmethod
    async def compact(self, messages: list[dict[str, Any]], llm: BaseLLM) -> list[dict[str, Any]]:
        """Toma los mensajes actuales y devuelve una versión compactada."""
        ...


class SummarizationStrategy(CompactionStrategy):
    """Usa el LLM para resumir los mensajes antiguos."""

    def __init__(self, keep_last_n: int = 4):
        self.keep_last_n = keep_last_n

    async def compact(self, messages: list[dict[str, Any]], llm: BaseLLM) -> list[dict[str, Any]]:
        # Necesitamos al menos un par de mensajes extra para que valga la pena resumir
        if len(messages) <= self.keep_last_n + 1:
            return messages

        # 1. Separar system prompt, mensajes antiguos y recientes
        system_msg = messages[0] if messages[0]["role"] == "system" else None
        start_idx = 1 if system_msg else 0

        # Los últimos N mensajes se quedan intactos
        recent_msgs = messages[-self.keep_last_n:]
        # El resto se va a resumir
        old_msgs = messages[start_idx:-self.keep_last_n]

        if not old_msgs:
            return messages  # pragma: no cover

        # 2. Pedir al LLM que resuma
        summary_prompt = [
            {"role": "system", "content": "Eres un asistente que resume conversaciones. Sé conciso y mantén los hechos clave, decisiones y herramientas usadas."},
            {"role": "user", "content": f"Resume la siguiente conversación:\n\n{old_msgs}"}
        ]

        try:
            response = await llm.chat(summary_prompt)
            summary_text = response.content or "Resumen no disponible."
        except Exception as e:
            summary_text = f"[Error al resumir la conversación antigua: {e}]"

        # 3. Construir el nuevo historial
        new_messages = []
        if system_msg:
            new_messages.append(system_msg)

        # Inyectamos el resumen como un mensaje de sistema
        new_messages.append({
            "role": "system",
            "content": f"--- Resumen de la conversación anterior ---\n{summary_text}\n-------------------------------------------"
        })

        new_messages.extend(recent_msgs)
        return new_messages
