# AGENTS.md — Agent Harness

An autonomous AI agent engine (Harness) built in Python with a Textual TUI, MCP client, subagents, and interactive permissions. Provider-agnostic and highly extensible.

## Stack & Structure

- **Language:** Python 3.11+
- **Package Manager:** `uv`
- **TUI:** `textual`, `rich`
- **AI Integration:** `openai` SDK (compatible with OpenRouter, Groq, etc.)
- **Tool Protocol:** `mcp` (Model Context Protocol)
- **Orchestration:** Custom `AgentLoop` (ReAct pattern)
- **Testing:** `pytest`, `pytest-asyncio`, `pytest-cov` (100% coverage)

**Folder Structure:**
- `app/core/`: Core logic (LLM, Harness, Permissions, Memory, Subagents).
- `app/tui/`: User Interface (Textual, modals, dashboard).
- `app/tools/`: Local tools (bash, filesystem, memory).
- `app/mcp/`: Client for external MCP servers.
- `tests/`: Unit and integration test suite.
- `scripts/`: Auxiliary scripts (local MCP servers).

## Comandos

- **Instalar dependencias:** `uv sync`
- **Iniciar la TUI (desarrollo):** `uv run tom dev`
- **Ejecutar tests con cobertura:** `uv run tom test`
- **Ejecutar tests de integración (MCP):** `uv run tom test-integration`
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
- **Permission Gate:** Sensitive tools (`bash`, `write_file`) always ask for confirmation. Users can approve with `y`, always with `a` (saved to `.harness_permissions.json`), or deny with `n`.
- **MCP:** Servers are configured in `mcp_config.json`. They are connected at TUI startup. Failed servers are ignored.
- **TUI:** Use `await app.write_to_chat()` to add messages. Do not use `print()`.
- **Streaming:** El `AgentLoop` ahora tiene un método `stream` que devuelve chunks de texto. La TUI los renderiza en tiempo real usando `Markdown.update()`.
- **Multimodalidad:** Las imágenes se codifican en Base64 y se inyectan como bloques `image_url` en el contexto. El `FileAwareInput` intercepta el pegado de archivos para evitar que se escriban como texto.
- **Exportación:** El comando `/export` permite guardar la transcripción en Markdown o JSON usando `render_transcript`.

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
- **Manual test:** `uv run tom dev` and verify the TUI starts, chat works, permissions function, and the debug panel (F1) shows events.