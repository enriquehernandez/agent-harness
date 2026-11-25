# Tareas Completadas

## Refactorización de contexto en texto plano

- **Objetivo:** Refactorizar el proyecto para usar la estructura de contexto en texto plano (`AGENTS.md`, `docs/`, `tasks/`, `checks/`).
- **Estado:** Completada en el arranque del contexto: `app/tui/app.py` lee `AGENTS.md` y `tasks/actual.md` y añade el `preamble()` de la memoria al System Prompt (`[Long-term memory]`). `docs/` y `checks/` **no** se leen ni se inyectan: el agente debe consultarlos con herramientas cuando los necesita. El prompt mencionaba `docs/` como «everything else below … is BACKGROUND CONTEXT»; se corrigió después (ver entrada «Corrección del system prompt sobre docs/»).

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

## Heredar el contexto en el modo A2A `fork`

- **Objetivo:** que un subagente `fork` reciba la conversación de la TUI al delegar, sin cambiar la firma de `BaseTool.run()`.
- **Estado:** Completada. `OrchestratorTool` acepta un `context_provider` opcional que la TUI resuelve en cada llamada (`lambda: self.ctx`), por lo que sobrevive a `/reload tools` y a `/session new`. `A2AStrategy._fork_context()` centraliza la preparación del contexto en las cuatro estrategias: hereda los mensajes no-`system` del padre y mantiene el `system_prompt` del `AgentCard`, evitando que las reglas del orquestador se conviertan en instrucciones del subagente. Cubierto por tests en `tests/core/test_a2a.py` y `tests/tui/test_app.py`.

## Preámbulo de continuación en el fork A2A

- **Objetivo:** que el subagente distinga el historial heredado de la tarea que debe ejecutar.
- **Estado:** Completada. `A2AStrategy._fork_context()` añade un mensaje `user` de continuación justo después del historial heredado (solo si hay mensajes heredados); `AgentLoop.run()` añade la tarea en el mensaje siguiente. No se añade nada en modo `isolated` ni cuando el contexto no tiene historial. Cubierto por tests en `tests/core/test_a2a.py`.

## Corrección del system prompt sobre `docs/`

- **Objetivo:** que el prompt no afirme que `docs/` se inyecta como BACKGROUND CONTEXT cuando solo se cargan `AGENTS.md`, `tasks/actual.md` y la memoria.
- **Estado:** Completada. Se quitó `docs,` de la frase del system prompt en `app/tui/app.py`; se optó por corregir la afirmación en lugar de cargar `docs/` y `checks/`, porque `AGENTS.md` ya indica leerlos bajo demanda. Actualizado `docs/herramientas.md`. Cubierto por `tests/tui/test_app.py::test_system_prompt_does_not_claim_docs_are_injected`.

## Alinear el proveedor por defecto

- **Objetivo:** que `cp .env.example .env` no cambie el proveedor respecto al default del código.
- **Estado:** Completada. `.env.example` usa ahora `LLM_PROVIDER=fake`, igual que `Settings.LLM_PROVIDER`, y explica cómo cambiar a un proveedor real. Actualizado `README.md` y el comentario sobre los modelos por agente A2A. Cubierto por `tests/core/test_llm_factory.py::test_env_example_provider_matches_settings_default`.

## Extraer texto de `.doc`, `.xls` y `.ppt`

- **Objetivo:** que los formatos Office 97-2003 que acepta `FileAwareInput` puedan leerse con `read_document`.
- **Diseño elegido:** previa aprobación, se añadieron `xlrd` y `olefile` con `uv`. `.xls` se lee con `xlrd` (conversión de celdas de fecha); `.doc` y `.ppt` se leen de los streams OLE `WordDocument` y `PowerPoint Document`, extrayendo cadenas imprimibles en UTF-16LE con fallback a Latin-1. Es best-effort: sin formato y con posible texto de metadatos.
- **Estado:** Completada. Cubierto por `tests/core/test_tools.py::test_read_document_legacy_formats` y `test_read_document_legacy_text_fallback`; documentado en `PRODUCT_BLUEPRINT/02_COMPONENTS/10_document_reading.md`, `docs/herramientas.md`, `README.md` y `PRODUCT_BLUEPRINT/03_SECURITY_AND_AUDIT/01_testing_y_mocks.md`.

## Verificar soporte del modelo antes de aplicar prompt caching

- **Objetivo:** no enviar `cache_control` a modelos que no soportan esa extensión de la API compatible con OpenAI.
- **Estado:** Completada. `_supports_prompt_caching(model)` comprueba que el nombre contenga `claude` o `anthropic` (sin distinción de mayúsculas); `OpenAICompatibleProvider.chat()` solo reescribe el mensaje `system` cuando la guardia pasa, sin mutar los mensajes del caller. Actualizado `docs/herramientas.md` y `.env.example`. Cubierto por `tests/core/test_openai_provider.py::test_prompt_caching_model_support` y `::test_openai_provider_prompt_caching_skipped_for_unsupported_model`, además del test de caching con `anthropic/claude-3-5-sonnet-20241022`.

## Códigos de respuesta de un solo uso

- **Objetivo:** añadir `/truth`, `/human`, `/nofluff`, `/devil`, `/decode` y `/genius` como códigos que cambian el estilo solo de la siguiente pregunta, sin `/normal`.
- **Estado:** Completada (flujo de entrada de `app/tui/app.py` autorizado por el usuario). `MODE_INSTRUCTIONS` y `mode_message()` viven en `app/tui/commands.py`; el comando fija `pending_mode` (y `pending_question` si lleva texto inline). `_begin_pending_mode()`/`_end_pending_mode()` inyectan el mensaje temporal y lo retiran en `_stream_user_message()` y en la rama de imágenes de `on_input_submitted()`, por lo que no queda en el historial y la pregunta siguiente vuelve al tono normal. Los códigos están en `AVAILABLE_COMMANDS` y `/help`. Cubierto por tests parametrizados en `tests/tui/test_commands.py` y por `tests/tui/test_app.py` (texto, inline e imágenes); documentado en `README.md` y `docs/herramientas.md`.

## Hooks del Harness — Fase 1 (observador)

- **Objetivo:** ejecutar comandos definidos por el usuario automáticamente en eventos del ciclo de vida, sin comando para activarlos.
- **Estado:** Completada. `app/core/harness/hooks.py` aporta `HookEvent`, `HookRegistry`, `HookManager` y `emit_hook()`; la config vive en `.harness/hooks.json` (`settings.hooks_file`) y admite `disableAllHooks`. Los handlers `command` se lanzan con `asyncio.create_subprocess_shell()` (el comando sale de la config de confianza; el evento va por stdin como JSON, sin interpolar), con timeout `TOOL_TIMEOUT` y fail-open. Disparadores: `UserPromptSubmit` (TUI y `AgentLoop.run()`), `PreToolUse`/`PostToolUse` (`_execute_tool()`), `PreCompact`/`PostCompact` (`ContextManager`) y `Stop`/`StopFailure` (`AgentLoop`). Cubierto por `tests/core/test_hooks.py` y por tests de integración en `test_agent_loop.py`, `test_context_compaction.py` y `test_app.py`. Documentado en `PRODUCT_BLUEPRINT/02_COMPONENTS/11_hooks.md` (y su índice), `docs/herramientas.md` y `README.md`.

## Hooks — Bloqueo de borrados (fase 2 parcial)

- **Objetivo:** antes de abordar las fases 2 y 3 completas, prohibir eliminar archivos del proyecto mediante un hook `command` que pare la herramienta y entregue un mensaje al usuario.
- **Estado:** Completada. `HookOutcome` parsea `deny` por JSON (`hookSpecificOutput.permissionDecision`, o `decision: block`) y por exit 2 con motivo en stderr; el primer deny gana y corta la cadena de hooks. `AgentLoop._execute_tool()` consulta el outcome antes de los permisos: no ejecuta la herramienta, escribe el motivo en el resultado de la tool y emite el evento `hook_denied`, que `stream_to_chat()` muestra en el chat. `.harness/hooks/no_delete.py` inspecciona `tool_input.command` de `bash` (`rm`, `rmdir`, `unlink`, `shred`, `git rm`, `find -delete`, `os.remove`, `Path.unlink`, `shutil.rmtree`) y devuelve el `deny`; se registró como `PreToolUse` con matcher `bash` en `.harness/hooks.json`. `.harness/hooks/audit.py` expone `log_event()` como registrador compartido y `no_delete.py` lo usa para dejar constancia del bloqueo en `audit.log`, sin duplicar entradas con un segundo hook `PostToolUse`. Fail-open intacto: stdout vacío o inválido, errores y timeouts siguen permitiendo la acción. Cubierto por tests unitarios, de integración real con el script y de la TUI en `tests/core/test_hooks.py`, `tests/core/test_agent_loop.py` y `tests/tui/test_app.py`. Documentado en `PRODUCT_BLUEPRINT/02_COMPONENTS/11_hooks.md`, `docs/herramientas.md` y `README.md`.

## Hooks — Feedback de `Stop` y `PostToolUse` (fase 2A)

- **Objetivo:** aprovechar el `decision: block` de los hooks de cierre y post-herramienta para realimentar al agente en vez de ignorarlo.
- **Estado:** Completada. `AgentLoop._apply_hook_feedback()` convierte un `denied` en `[SISTEMA - FEEDBACK DE HOOK]: ...` con motivo del hook o texto genérico. `_emit_post_tool()` centraliza los cuatro `PostToolUse` y añade el feedback después de ejecutar la tool. `_emit_stop_with_feedback()` se usa en todos los cierres de `run()`/`stream()`: si hay `block`, se añade el mensaje y se reanuda el bucle; si ya se alcanzó `max_iterations`, se registra el feedback y se devuelve el resultado. Sin cambios en la TUI. Cubierto por 8 tests nuevos en `tests/core/test_agent_loop.py` (cierre normal, máximo de iteraciones, límite de reflexiones, post-tool y motivos vacíos); documentado en `PRODUCT_BLUEPRINT/02_COMPONENTS/11_hooks.md`, `docs/herramientas.md` y `README.md`.

## Hooks — `additionalContext` temporal (fase 2B)

- **Objetivo:** permitir que los hooks entreguen contexto adicional al modelo sin persistirlo en la sesión ni tocar el system prompt.
- **Estado:** Completada. `HookOutcome.additional_context` lee `hookSpecificOutput.additionalContext` (o la clave raíz) y se conserva aunque el hook devuelva `deny`. `HookManager.emit()` concatena los aportes de todos los hooks ejecutados en `UserPromptSubmit`/`PreToolUse`/`PostToolUse`, los deja en `pending_context` y `drain_context()` los entrega una sola vez. `ContextManager.append_hook_context()` crea un único mensaje temporal `user` y `remove_hook_context()` lo retira por identidad, replicando el patrón `_begin_pending_mode()`/`_end_pending_mode()` de la TUI sin cambiar su diseño. `AgentLoop` inyecta antes de cada llamada al LLM (`run()` y `stream()`) y limpia al terminar el turno. Cubierto por tests nuevos en `tests/core/test_hooks.py`, `tests/core/test_context_hooks.py` y `tests/core/test_agent_loop.py`, con comprobación de que el mensaje temporal no queda en el historial; documentado en `PRODUCT_BLUEPRINT/02_COMPONENTS/11_hooks.md`, `docs/herramientas.md` y `README.md`.

## Hooks — Tipos avanzados e interfaz (fase 3)

- **Objetivo:** ampliar los hooks con `http`/`prompt`/`agent`, matchers completos, filtro `if` y un visor `/hooks` en el chat, con recarga sin reiniciar.
- **Estado:** Completada. `HookRegistry` acepta cuatro tipos (`command`, `http`, `prompt`, `agent`), matchers con nombres, `|` y regex, y filtro `if` con firmas `herramienta:detalle` estilo permisos. `HookOutcome.from_text()` entiende `ok: false`, `permissionDecision`, `decision: block` y `additionalContext`; `http` usa `httpx`, `prompt` una llamada LLM y `agent` un `DelegateTool` con timeout de 60 s y permisos hijos. `_hook_depth` evita la recursión de hooks y que el loop anidado del subagente drene el contexto del turno padre. `HookManager` registra errores por handler, los muestra en `describe()` y recarga la configuración por mtime en cada evento. `/hooks` y `/hooks reload` se añadieron a `AVAILABLE_COMMANDS` y a `/help` con el diseño aprobado en el chat (sin modal nuevo). Cubierto por tests nuevos en `tests/core/test_hooks.py`, `tests/core/test_agent_loop.py` y `tests/tui/test_commands.py` con cobertura del 100 %; documentado en `PRODUCT_BLUEPRINT/02_COMPONENTS/11_hooks.md`, `docs/herramientas.md` y `README.md`.

- **Decisiones de diseño conservadas:** activación automática (sin comando para dispararlos; `/hooks` es solo un visor), configuración en `.harness/hooks.json` y nunca en `.claude/settings.json`, sin dependencias nuevas (`httpx` ya estaba en `pyproject.toml`), fail-open ante errores y `agent_name`/`agent_depth` en los eventos de subagentes A2A. Los commits se hicieron solo con aprobación explícita del usuario.
