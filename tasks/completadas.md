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

## Registrar una tool `edit_file`

- **Objetivo:** permitir cambios puntuales con `path` + `edits` (`oldText`/`newText`), reutilizando el diff que ya genera `PermissionGate`.
- **Diseño elegido:** `EditFileTool` en `app/tools/filesystem.py`, registrada por `register_core_tools()`. Valida `base_dir`, existencia del archivo y coincidencia exacta de cada `oldText`; aplica las sustituciones en orden.
- **Estado:** Completada. Cubierto por `tests/core/test_tools.py` (éxito, registro y casos de error) y documentado en `AGENTS.md`, `README.md`, `docs/herramientas.md` y `PRODUCT_BLUEPRINT/02_COMPONENTS/01_harness_loop.md`.

## Exigir 100% de cobertura en `tom test`

- **Objetivo:** que un descenso de cobertura haga fallar el comando usado por CI.
- **Estado:** Completada. El script `test` de `pyproject.toml` incluye `--cov-fail-under=100` (sin tocar `addopts`, para no romper ejecuciones parciales). Cubierto por `tests/test_init_files.py::test_tom_test_enforces_full_coverage`.

## Mostrar el comando de recarga en `/help`

- **Objetivo:** que la ayuda de la TUI liste el comando de recarga.
- **Estado:** Completada. Se añadió la fila en la tabla de `help_text` (`app/tui/commands.py`), actualizada después a `/reload`. Cubierto por `tests/tui/test_commands.py::test_cmd_help_lists_reload`.

## Quitar imports sin usar

- **Objetivo:** eliminar `UnicodeImage` y `unquote` de `app/tui/app.py`, y `pandas` de `app/tools/documents.py` (la dependencia sigue declarada en `pyproject.toml`).
- **Estado:** Completada. Cubierto por `tests/test_init_files.py::test_no_known_unused_imports`.

## Unificar la recarga en `/reload [skills|permissions|tools]`

- **Objetivo:** sustituir `/reload-skills` por un comando genérico con objetivos y arreglar el marcador `Available skills:` del system prompt.
- **Estado:** Completada. `/reload skills` actualiza el prompt y el autocompletado; `/reload permissions` recarga `.harness/permissions.json` vía `PermissionGate.reload_persisted()`; `/reload tools` desconecta los clientes MCP, reinicializa herramientas y conserva el contexto. La lista de comandos del autocompletado vive en `AVAILABLE_COMMANDS` (`app/tui/commands.py`). Cubierto por tests en `tests/tui/test_commands.py`, `tests/tui/test_app.py` y `tests/core/test_permissions.py`.

## Permisos persistidos y gate compartido en subagentes A2A

- **Objetivo:** que `ParallelStrategy` respete las aprobaciones persistidas y que los subagentes (A2A y `DelegateTool`) no pierdan las aprobaciones del padre.
- **Estado:** Completada. `A2AStrategy._child_gate()` centraliza la creación del gate para las cuatro estrategias y carga `.harness/permissions.json` en todas, incluida `parallel`. `PermissionGate.child()` comparte `session_allowed`, `ask_user` y `persist_file` con el padre, copia las `policies` y permite `allow=` para las tools propias del reviewer. La TUI pasa su gate a `DelegateTool`. Nota: el test de regresión mostró que el constructor de `PermissionGate` ya cargaba el archivo, así que el fallo real era la copia aislada de `session_allowed`, no la carga en `parallel`. Cubierto por tests en `tests/core/test_a2a.py`, `tests/core/test_permissions.py` y `tests/core/test_subagents.py`.
