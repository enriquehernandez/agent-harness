# AGENTS.md — Agent Harness

An autonomous AI agent engine (Harness) built in Python with a Textual TUI, MCP client, subagents, and interactive permissions. Provider-agnostic and highly extensible.

## Stack & Structure

- **Language:** Python 3.11+
- **Package Manager:** `uv`
- **TUI:** `textual`, `rich`, `textual-image`
- **AI Integration:** `openai` SDK (compatible con OpenRouter, Groq, etc.)
- **Tool Protocol:** `mcp` (Model Context Protocol)
- **Orchestration:** Custom `AgentLoop` (ReAct pattern) + **A2A** (Supervisor, Sequential, Parallel, Swarm)
- **Testing:** `pytest`, `pytest-asyncio`, `pytest-cov` (100% coverage)
- **Memory:** SQLite with FTS5 (default), vectors (`sqlite-vec` + `fastembed`), files, or in-memory.
- **Pricing:** Provider API (`httpx`) with disk cache, JSON fallback.
- **Resilience:** `tenacity` for MCP retries.
- **Sessions:** JSON files in `.harness/sessions/`.
- **Skills:** Markdown files in `.agents/skills/`.

**Folder Structure:**
- `app/core/`: Core logic (LLM, Harness, Permissions, Memory, Pricing, Subagents, A2A, Sessions).
- `app/tui/`: User Interface (Textual, widgets, modals, dashboard, suggester).
- `app/tools/`: Local tools (bash, filesystem, memory, skills, **documents**).
- `app/mcp/`: Client for external MCP servers.
- `app/core/pricing/`: Pricing registry, sources (API, JSON, Fake).
- `tests/`: Unit and integration test suite.
- `scripts/`: Auxiliary scripts (local MCP servers, diagnostics).
- `.agents/skills/`: Installed skills.
- `.harness/`: Persistent data (memory, sessions, permissions, logs, pricing cache, agent_flow).
- `pricing_config.json`: Provider pricing configuration.
- `pricing.json`: Manual prices (OpenAI, Groq).

## Comandos

- **Instalar dependencias:** `uv sync`
- **Iniciar la TUI (desarrollo):** `uv run tom dev`
- **Ejecutar tests con cobertura:** `uv run tom test`
- **Ejecutar tests de integración (MCP + Vector):** `uv run tom test-integration`
- **Verificar pricing:** `uv run python scripts/check_pricing.py`
- **Construir y ejecutar con Docker:** `docker compose build && docker compose run --rm agent-harness`

## Convenciones

- **Language:** English for all code, variables, comments, and docstrings. Spanish only for user-facing messages (TUI/CLI).
- **Typing:** Strict typing (`list[str]`, `dict[str, Any]`, `Optional`).
- **Style:** 4-space indentation, max 100 chars per line. Follow PEP 8.
- **Error Handling:** Tools must return `ToolResult(success=False)` instead of raising exceptions. Use `try/except` in the loop to prevent crashes.
- **Logging:** Use `logger.debug()` for internal events and `logger.error()` for failures. Do not use `print()` in production code.

## Domain Rules / Known Pitfalls

- **Prompt Caching:** `OpenAICompatibleProvider` injects `cache_control` if `ENABLE_PROMPT_CACHING=True`. Only works on supported models.
- **Safe Split Point:** `SummarizationStrategy` never cuts a `tool` message from its corresponding `assistant` call.
- **Permission Gate:** Sensitive tools (`bash`, `write_file`) always ask for confirmation. Users can approve with `y`, always with `a` (saved to `.harness/permissions.json`), or deny with `n`.
- **MCP:** Servers are configured in `mcp_config.json`. They are connected at TUI startup. Failed servers are ignored.
- **TUI:** Use `await app.write_to_chat()` to add messages. Do not use `print()`.
- **Streaming:** `AgentLoop.stream()` yields text chunks. The TUI renders them in real-time with `Markdown.update()`. The `stream_to_chat` method has a timeout (300s) and handles `503` errors from the LLM provider gracefully.
- **Multimodal:** Images are encoded in Base64 and injected as `image_url` blocks. `FileAwareInput` intercepts file pastes to prevent them from being typed as text.
- **Export:** `/export` saves the transcript in Markdown or JSON using `render_transcript`.
- **Skills:** Skills are loaded from `.agents/skills/<name>/SKILL.md`. The agent can load them with the `load_skill` tool or the `@name` syntax. The `SkillSuggester` autocompletes skill names when typing `@`. Skills are discovered at startup and injected into the `system_prompt`.
- **Memory:** The `MemoryStore` interface supports three backends (`sqlite`, `files`, `memory`). The default is `sqlite`. The `preamble()` of the store is injected into the `system_prompt` at startup. Tools: `memory_save`, `memory_recall`.
- **Sessions:** The `SessionManager` saves the conversation history to `.harness/sessions/<id>.json` on exit. It loads the last session automatically at startup. Commands: `/session list`, `/session load <id>`, `/session save`, `/session delete <id>`.
- **Hooks:** `BashTool` intercepts commands containing `capture_snapshot.py` and injects `--tools observations.json` automatically, so the `agent-harness-explorer` skill includes the harness tools in its report.
- **Pricing:** El coste se calcula usando `PricingProvider`, que lee de una `PricingSource` (API o JSON). OpenRouter consulta su API con caché en `.harness/pricing_cache.json` (TTL configurable con `PRICING_CACHE_TTL_DAYS`). OpenAI/Groq leen `pricing.json`. El comando `/cost` muestra el coste de la última llamada y el acumulado de la sesión.
- **MCP Resilience:** `MCPClient` usa backoff exponencial (3 intentos) con `asyncio.sleep`. Si una tool falla en ejecución, `MCPToolProxy` reconecta automáticamente y reintenta una vez.
- **Rich Rendering:** `RichMessage` parsea bloques ```table, ```tree y ```json (listas de dicts) y los renderiza con Rich (Table, Tree, Syntax). El dashboard muestra el coste total acumulado.
- **Vector Memory:** Backend `vector` usa `sqlite-vec` + `fastembed` (BAAI/bge-small-en-v1.5). Se guarda en `.harness/vector.db`. Busca por similitud semántica, no por palabras exactas.
- **Agent-to-Agent (A2A):** El sistema A2A permite orquestar subagentes con 4 estrategias (`supervisor`, `sequential`, `parallel`, `swarm`). Se configura en `.env` (`A2A_STRATEGY`, `A2A_SEQUENCE`, etc.). Los agentes se definen con `AgentCard` (name, description, system_prompt, tools, mode, model).
- **Modelo por Agente:** Cada `AgentCard` puede tener un modelo específico (`model`). Si no se define, usa el modelo del padre. Se configura en `.env` (`A2A_ANALYST_MODEL`, etc.).
- **Flujo de Agentes:** El panel de debug (F1) muestra un `Tree` con el flujo de agentes en tiempo real (`start`, `end`, `handoff`). Se emite con `log_agent_flow()` en `logger.py`.
- **Renderizado de Imágenes:** La TUI usa `textual-image` para mostrar imágenes pegadas/arrastradas. El fallback es mostrar el nombre del archivo.
- **Document Reading:** La tool `read_document` extrae texto de PDFs, DOCX, XLSX y PPTX. El agente debe usarla cuando el usuario adjunte un documento binario. No se pasan como Base64 (eso solo para imágenes).
- **File Attachments:** El `FileAwareInput` limpia los escapes de la terminal (barras invertidas) y copia los archivos externos a `.harness/temp_attachments/` antes de pasárselos al agente. Para múltiples archivos, usa un debounce de 200ms.


## Working Style

- **Before coding:** Plan the change. Write the test first (TDD) if it's a new feature.
- **Commit size:** Keep commits small and atomic.
- **When done:** Run tests (`uv run tom test`) and ensure coverage stays at 100%. If you add a tool or command, update `/help`.
- **Documentation:** If you add a new component, update `PRODUCT_BLUEPRINT`.

## Limits

- ✅ **Always:** Use `uv` for dependencies. Write tests for new logic. Follow the Registry pattern for new tools.
- ⚠️ **Ask first:** Add new dependencies to `pyproject.toml`. Modify the signature of `BaseLLM` or `BaseTool`. Change the TUI design.
- 🛑 **Never:** Hardcode API keys. Use `print()` instead of `logger` or `app.write_to_chat()`. Delete existing tests without justification.

## Verification

- **Unit tests:** `uv run tom test` must pass with >99% coverage.
- **Integration tests:** `uv run tom test-integration` verifies that MCP servers respond.
- **Manual test:** `uv run tom dev` and verify:
    - TUI starts.
    - Chat works (streaming).
    - Permissions function (modals).
    - Debug panel (F1) shows events.
    - `@skill-name` loads a skill.
    - `/session list` shows sessions.
    - `/memory clear` clears memory.

## Agent-to-Agent (A2A)

El Harness soporta orquestación multi-agente configurable via `.env`:

- `A2A_STRATEGY`: `supervisor` (dinámico), `sequential` (pipeline), `parallel` (fan-out), `swarm` (handoff).
- `A2A_SEQUENCE`: Lista de agentes para sequential.
- `A2A_PARALLEL_AGENTS`: Agentes para parallel.
- `A2A_SWARM_START`: Agente inicial para swarm.
- **AgentCard**: Define `name`, `description`, `system_prompt`, `tools`, `mode` (`fork`/`isolated`) y `model` (opcional).
- **Modelo por agente**: Si `A2A_<AGENT>_MODEL` está definido en `.env`, el subagente usa ese modelo. Si no, usa el modelo del padre.
- **OrchestratorTool**: Tool `delegate_task` que el LLM principal usa para invocar el sistema A2A.
- **Permisos**: Los subagentes heredan el `PermissionGate` del padre y leen `.harness/permissions.json`.