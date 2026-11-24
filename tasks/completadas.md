# Tareas Completadas

## Refactorización de contexto en texto plano

- **Objetivo:** Refactorizar el proyecto para usar la estructura de contexto en texto plano (`AGENTS.md`, `docs/`, `tasks/`, `checks/`).
- **Estado:** Completada en el arranque del contexto: `app/tui/app.py` lee `AGENTS.md` y `tasks/actual.md` y añade el `preamble()` de la memoria al System Prompt (`[Long-term memory]`). `docs/` y `checks/` **no** se leen ni se inyectan: el texto del prompt solo los menciona como «everything else below … is BACKGROUND CONTEXT»; el agente debe consultarlos con herramientas cuando los necesita.

## Ctrl+L limpia también el `ContextManager`

- **Objetivo:** Igualar `Ctrl+L` a `/clear`: vaciar el historial conservando el system prompt.
- **Estado:** Completada. `action_clear_chat()` (`app/tui/app.py`) llama a `self.ctx.clear()` cuando hay contexto, además de limpiar los widgets. Cubierto por `tests/tui/test_app.py::test_app_clear_chat_clears_context`.

## Unificar el formato de descripción de las tools MCP

- **Objetivo:** que las tools remotas se clasifiquen como MCP en `/tools`, `/skills` y `export_observations`, sin perder el nombre del servidor.
- **Estado:** Completada. `MCPToolProxy` (`app/mcp/client.py`) emite ahora `[MCP] (servidor) descripción`, formato que ya reconocen los consumidores. Cubierto por `tests/mcp/test_mcp_client.py`, `tests/core/test_tools.py::test_observations_classifies_real_mcp_tool` y `tests/tui/test_commands.py::test_cmd_tools_marks_mcp_tool_as_mcp`.

## Corregir las tools copiadas a los subagentes

- **Objetivo:** que el reviewer legacy y los agentes A2A reciban tools presentes en el registry.
- **Estado:** Completada. La TUI (`app/tui/app.py`) copia ahora `read_file` y `bash` en lugar de los nombres inexistentes `read_text_file` y `list_directory`. Cubierto por `tests/tui/test_app.py::test_app_subagents_receive_registered_tools`.
