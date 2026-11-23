# app/core/harness/events.py
from dataclasses import dataclass
from typing import Any


@dataclass
class AgentEvent:
    type: str
    data: dict[str, Any]

# Tipos de eventos que emitiremos:
# - "text_chunk": Un pedazo de texto del LLM.
# - "tool_start": El agente va a usar una herramienta.
# - "tool_end": La herramienta terminó.
# - "result": El loop terminó con éxito.
# - "error": Hubo un problema.
