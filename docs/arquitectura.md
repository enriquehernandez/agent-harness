# Arquitectura y Stack del Proyecto

## Stack Tecnológico
- **Lenguaje:** Python 3.11+
- **Gestor de Paquetes:** `uv`
- **TUI:** `textual`, `rich`, `textual-image`
- **IA:** `openai` SDK (compatible con OpenRouter, Groq, etc.)
- **Protocolo de Tools:** `mcp` (Model Context Protocol)
- **Orquestación:** `AgentLoop` custom (ReAct) + **A2A** (Supervisor, Sequential, Parallel, Swarm)
- **Testing:** `pytest`, `pytest-asyncio`, `pytest-cov` (100% cobertura)
- **Memoria:** SQLite con FTS5 (default), vectores (`sqlite-vec` + `fastembed`), archivos o en memoria.
- **Resiliencia:** `tenacity` para reintentos de MCP.

## Estructura de Carpetas
- `app/core/`: Lógica central (LLM, Harness, Permissions, Memory, Pricing, Subagents, A2A, Sessions).
- `app/tui/`: Interfaz de usuario (Textual, widgets, modales, dashboard, suggester).
- `app/tools/`: Herramientas locales (bash, filesystem, memory, skills, documents).
- `app/mcp/`: Cliente para servidores MCP externos.
- `.agents/skills/`: Skills instaladas.
- `.harness/`: Datos persistentes (memoria, sesiones, permisos, logs, cache).
- `scripts/`: Scripts auxiliares (servidores MCP locales, diagnósticos).

## Agent-to-Agent (A2A)
- Soporta 4 estrategias configurables en `.env`: `supervisor` (dinámico), `sequential` (pipeline), `parallel` (fan-out), `swarm` (handoff).
- Los agentes se definen con `AgentCard` (name, description, system_prompt, tools, mode, model).
- Si `A2A_<AGENT>_MODEL` está en `.env`, el subagente usa ese modelo. Si no, usa el del padre.