# Arquitectura y Stack del Proyecto

## Stack Tecnológico
- **Lenguaje:** Python 3.11+
- **Gestor de Paquetes:** `uv`
- **TUI:** `textual`, `rich`, `textual-image`
- **IA:** `openai` SDK (compatible con OpenRouter, Groq, etc.)
- **Protocolo de Tools:** `mcp` (Model Context Protocol)
- **Orquestación:** `AgentLoop` custom (ReAct) + **A2A** (Supervisor, Sequential, Parallel, Swarm)
- **Observabilidad:** `langfuse` (generación `agent_stream` con usage y coste en `AgentLoop.stream()`).
- **Testing:** `pytest`, `pytest-asyncio`, `pytest-cov` (100% de cobertura en el informe)
- **Memoria:** SQLite con FTS5 (default), vectores (`sqlite-vec` + `fastembed`), archivos o en memoria.
- **Resiliencia:** `tenacity` para reintentos de MCP.

## Estructura de Carpetas
- `app/core/`: Lógica central (LLM, Harness, Permissions, Memory, Pricing, Subagents, A2A, Sessions).
- `app/tui/`: Interfaz de usuario (Textual, widgets, modales, dashboard, suggester).
- `app/tools/`: Herramientas locales (bash, filesystem, memory, skills, documents).
- `app/mcp/`: Cliente para servidores MCP externos.
- `.agents/skills/`: Skills instaladas (incluye `token-budget-guard`).
- `.harness/` (`DATA_DIR`, por defecto): Datos persistentes (memoria, sesiones, permisos, logs, cache).
- `scripts/`: Scripts auxiliares (servidores MCP locales, diagnósticos).

## Flujo del Loop (AgentLoop)
- `AgentLoop.run()` y `AgentLoop.stream()` (`app/core/harness/loop.py`) ejecutan el ciclo ReAct: compactan el contexto, consultan al LLM y ejecutan tools pasando por `PermissionGate`.
- `stream()` emite `AgentEvent(type, data)` (`app/core/harness/events.py`): `text_chunk`, `tool_start`, `tool_end`, `result` y `error`. La TUI consume esos eventos y va redibujando el Markdown de la respuesta.
- Si el LLM no pide tools, entra la auto-reflexión del crítico (`CriticTool`, `app/tools/critic.py`): una respuesta `REJECTED: …` se inyecta como feedback del sistema y fuerza otro intento (máx. 2), con avisos `⚠️` en el chat. `run()` aplica la misma revisión sin emitir eventos.
- Langfuse registra la generación con `usage_details` y `cost_details`; los fallos de tools se normalizan en `ToolResult` y se comunican al modelo (3 fallos consecutivos → pedir ayuda al usuario).

## Agent-to-Agent (A2A)
- Soporta 4 estrategias configurables en `.env`: `supervisor` (dinámico), `sequential` (pipeline), `parallel` (fan-out), `swarm` (handoff).
- Los agentes se definen con `AgentCard` (name, description, system_prompt, tools, mode, model).
- Modelos por agente: `A2A_ANALYST_MODEL`, `A2A_WRITER_MODEL` y `A2A_REVIEWER_MODEL` (`app/core/config.py`). Si la variable está vacía, se usa el modelo por defecto del proveedor (`get_llm(provider)` sin `model`). El crítico de auto-reflexión reutiliza `A2A_REVIEWER_MODEL` (`app/tui/app.py`).

## MCP
- Los servidores se declaran en `mcp_config.json`. `MCPClient.connect()` hace 3 intentos con backoff exponencial (`tenacity`) y un timeout de conexión de `MCP_CONNECT_TIMEOUT=10`; si falla la conexión inicial, la TUI lo muestra en el chat.
- `register_tools()` registra cada herramienta con el prefijo `mcp_<servidor>_` (`app/mcp/client.py`). `MCPToolProxy` llama a `call_tool` con `TOOL_TIMEOUT=30s` y, si falla la ejecución, reconecta y reintenta una vez (`client.py`).
