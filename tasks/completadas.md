# Tareas Completadas

> Cada tarea registrada debe cumplir `tasks/DEFINITION_OF_DONE.md`: tests/cobertura, pasos de verificación en TUI documentados en `Prueba en TUI`, seguridad, documentación y puerta de commit. Los pasos de las entradas históricas quedan escritos para poder repetirlos; ejecutarlos o confirmarlos antes de proponer cualquier commit.

## Refactorización de contexto en texto plano

- **Objetivo:** Refactorizar el proyecto para usar la estructura de contexto en texto plano (`AGENTS.md`, `docs/`, `tasks/`, `checks/`).
- **Estado:** Completada en el arranque del contexto: `app/tui/app.py` lee `AGENTS.md` y `tasks/actual.md` y añade el `preamble()` de la memoria al System Prompt (`[Long-term memory]`). `docs/` y `checks/` **no** se leen ni se inyectan: el agente debe consultarlos con herramientas cuando los necesita. El prompt mencionaba `docs/` como «everything else below … is BACKGROUND CONTEXT»; se corrigió después (ver entrada «Corrección del system prompt sobre docs/»).
- **Prueba en TUI:** Arrancar la TUI (`uv run python -m app.main`) → `/doctor` sin errores; preguntar «¿qué reglas sigues?» → responde según `AGENTS.md`, sin afirmar que `docs/` está inyectado.

## Ctrl+L limpia también el `ContextManager`

- **Objetivo:** Igualar `Ctrl+L` a `/clear`: vaciar el historial conservando el system prompt.
- **Estado:** Completada. `action_clear_chat()` (`app/tui/app.py`) llama a `self.ctx.clear()` cuando hay contexto, además de limpiar los widgets. Cubierto por `tests/tui/test_app.py::test_app_clear_chat_clears_context`.
- **Prueba en TUI:** Enviar un mensaje privado, pulsar Ctrl+L y ejecutar `/tokens` → contador al mínimo; preguntar por ese dato → el agente no lo recuerda.

## Unificar el formato de descripción de las tools MCP

- **Objetivo:** que las tools remotas se clasifiquen como MCP en `/tools`, `/skills` y `export_observations`, sin perder el nombre del servidor.
- **Estado:** Completada. `MCPToolProxy` (`app/mcp/client.py`) emite ahora `[MCP] (servidor) descripción`, formato que ya reconocen los consumidores. Cubierto por `tests/mcp/test_mcp_client.py`, `tests/core/test_tools.py::test_observations_classifies_real_mcp_tool` y `tests/tui/test_commands.py::test_cmd_tools_marks_mcp_tool_as_mcp`.
- **Prueba en TUI:** Con `mcp_config.json` activo: `/tools` y `/skills` → las tools remotas figuran como `[MCP] (servidor)`; pedir al agente que use `export_observations` → clasifica esas herramientas como MCP.

## Corregir las tools copiadas a los subagentes

- **Objetivo:** que el reviewer legacy y los agentes A2A reciban tools presentes en el registry.
- **Estado:** Completada. La TUI (`app/tui/app.py`) copia ahora `read_file` y `bash` en lugar de los nombres inexistentes `read_text_file` y `list_directory`. Cubierto por `tests/tui/test_app.py::test_app_subagents_receive_registered_tools`.
- **Prueba en TUI:** `/subagents` → el reviewer lista `read_file` y `bash`; pedirle que lea un archivo del repo → devuelve el contenido sin error de tool inexistente.

## Registrar una tool `edit_file`

- **Objetivo:** permitir cambios puntuales con `path` + `edits` (`oldText`/`newText`), reutilizando el diff que ya genera `PermissionGate`.
- **Diseño elegido:** `EditFileTool` en `app/tools/filesystem.py`, registrada por `register_core_tools()`. Valida `base_dir`, existencia del archivo y coincidencia exacta de cada `oldText`; aplica las sustituciones en orden.
- **Estado:** Completada. Cubierto por `tests/core/test_tools.py` (éxito, registro y casos de error) y documentado en `AGENTS.md`, `README.md`, `docs/herramientas.md` y `PRODUCT_BLUEPRINT/02_COMPONENTS/01_harness_loop.md`.
- **Prueba en TUI:** `/tools` → aparece `edit_file`; pedir «cambia X por Y en <archivo>» → el modal muestra el diff y, tras aprobar, el archivo queda modificado solo en ese tramo.

## Exigir 100% de cobertura en `tom test`

- **Objetivo:** que un descenso de cobertura haga fallar el comando usado por CI.
- **Estado:** Completada. El script `test` de `pyproject.toml` incluye `--cov-fail-under=100` (sin tocar `addopts`, para no romper ejecuciones parciales). Cubierto por `tests/test_init_files.py::test_tom_test_enforces_full_coverage`.
- **Prueba en TUI:** N/A (sin superficie TUI): `uv run tom test` → verde con `Required test coverage of 100% reached`; arrancar la TUI → `/doctor` sin errores.

## Mostrar el comando de recarga en `/help`

- **Objetivo:** que la ayuda de la TUI liste el comando de recarga.
- **Estado:** Completada. Se añadió la fila en la tabla de `help_text` (`app/tui/commands.py`), actualizada después a `/reload`. Cubierto por `tests/tui/test_commands.py::test_cmd_help_lists_reload`.
- **Prueba en TUI:** `/help` → la tabla contiene `/reload` y ya no aparece `/reload-skills`.

## Quitar imports sin usar

- **Objetivo:** eliminar `UnicodeImage` y `unquote` de `app/tui/app.py`, y `pandas` de `app/tools/documents.py` (la dependencia sigue declarada en `pyproject.toml`).
- **Estado:** Completada. Cubierto por `tests/test_init_files.py::test_no_known_unused_imports`.
- **Prueba en TUI:** N/A (limpieza de imports): arrancar la TUI sin `ImportError` y ejecutar `uv run tom test` → verde.

## Unificar la recarga en `/reload [skills|permissions|tools]`

- **Objetivo:** sustituir `/reload-skills` por un comando genérico con objetivos y arreglar el marcador `Available skills:` del system prompt.
- **Estado:** Completada. `/reload skills` actualiza el prompt y el autocompletado; `/reload permissions` recarga `.harness/permissions.json` vía `PermissionGate.reload_persisted()`; `/reload tools` desconecta los clientes MCP, reinicializa herramientas y conserva el contexto. La lista de comandos del autocompletado vive en `AVAILABLE_COMMANDS` (`app/tui/commands.py`). Cubierto por tests en `tests/tui/test_commands.py`, `tests/tui/test_app.py` y `tests/core/test_permissions.py`.
- **Prueba en TUI:** `/help` → solo `/reload`; con la TUI abierta, `/reload skills`, `/reload permissions` y `/reload tools` → el contexto del chat se conserva y skills/permisos se actualizan.

## Permisos persistidos y gate compartido en subagentes A2A

- **Objetivo:** que `ParallelStrategy` respete las aprobaciones persistidas y que los subagentes (A2A y `DelegateTool`) no pierdan las aprobaciones del padre.
- **Estado:** Completada. `A2AStrategy._child_gate()` centraliza la creación del gate para las cuatro estrategias y carga `.harness/permissions.json` en todas, incluida `parallel`. `PermissionGate.child()` comparte `session_allowed`, `ask_user` y `persist_file` con el padre, copia las `policies` y permite `allow=` para las tools propias del reviewer. La TUI pasa su gate a `DelegateTool`. Nota: el test de regresión mostró que el constructor de `PermissionGate` ya cargaba el archivo, así que el fallo real era la copia aislada de `session_allowed`, no la carga en `parallel`. Cubierto por tests en `tests/core/test_a2a.py`, `tests/core/test_permissions.py` y `tests/core/test_subagents.py`.
- **Prueba en TUI:** Aprobar una tool con «a», reiniciar la TUI y volver a usarla → no vuelve a preguntar; `/permissions` y `/subagents` → la aprobación aparece compartida con los subagentes.

## Heredar el contexto en el modo A2A `fork`

- **Objetivo:** que un subagente `fork` reciba la conversación de la TUI al delegar, sin cambiar la firma de `BaseTool.run()`.
- **Estado:** Completada. `OrchestratorTool` acepta un `context_provider` opcional que la TUI resuelve en cada llamada (`lambda: self.ctx`), por lo que sobrevive a `/reload tools` y a `/session new`. `A2AStrategy._fork_context()` centraliza la preparación del contexto en las cuatro estrategias: hereda los mensajes no-`system` del padre y mantiene el `system_prompt` del `AgentCard`, evitando que las reglas del orquestador se conviertan en instrucciones del subagente. Cubierto por tests en `tests/core/test_a2a.py` y `tests/tui/test_app.py`.
- **Prueba en TUI:** Tras hablar de un tema, pedir al orquestador una tarea A2A en modo `fork` que dependa de ese historial → el subagente lo usa; F1 → flujo con `agent_depth`, sin las reglas del orquestador como instrucciones propias.

## Preámbulo de continuación en el fork A2A

- **Objetivo:** que el subagente distinga el historial heredado de la tarea que debe ejecutar.
- **Estado:** Completada. `A2AStrategy._fork_context()` añade un mensaje `user` de continuación justo después del historial heredado (solo si hay mensajes heredados); `AgentLoop.run()` añade la tarea en el mensaje siguiente. No se añade nada en modo `isolated` ni cuando el contexto no tiene historial. Cubierto por tests en `tests/core/test_a2a.py`.
- **Prueba en TUI:** Repetir un fork con historial → la respuesta no repite la tarea como mensaje heredado; en modo `isolated` → no aparece ningún mensaje de continuación.

## Corrección del system prompt sobre `docs/`

- **Objetivo:** que el prompt no afirme que `docs/` se inyecta como BACKGROUND CONTEXT cuando solo se cargan `AGENTS.md`, `tasks/actual.md` y la memoria.
- **Estado:** Completada. Se quitó `docs,` de la frase del system prompt en `app/tui/app.py`; se optó por corregir la afirmación en lugar de cargar `docs/` y `checks/`, porque `AGENTS.md` ya indica leerlos bajo demanda. Actualizado `docs/herramientas.md`. Cubierto por `tests/tui/test_app.py::test_system_prompt_does_not_claim_docs_are_injected`.
- **Prueba en TUI:** Preguntar «¿qué archivos tienes inyectados en el prompt?» → responde `AGENTS.md`, `tasks/actual.md` y memoria; no `docs/` ni `checks/`.

## Alinear el proveedor por defecto

- **Objetivo:** que `cp .env.example .env` no cambie el proveedor respecto al default del código.
- **Estado:** Completada. `.env.example` usa ahora `LLM_PROVIDER=fake`, igual que `Settings.LLM_PROVIDER`, y explica cómo cambiar a un proveedor real. Actualizado `README.md` y el comentario sobre los modelos por agente A2A. Cubierto por `tests/core/test_llm_factory.py::test_env_example_provider_matches_settings_default`.
- **Prueba en TUI:** Con `.env` copiado de `.env.example`, arrancar la TUI → `/provider` muestra `fake` y no pide API key; `/model` muestra el modelo fake.

## Extraer texto de `.doc`, `.xls` y `.ppt`

- **Objetivo:** que los formatos Office 97-2003 que acepta `FileAwareInput` puedan leerse con `read_document`.
- **Diseño elegido:** previa aprobación, se añadieron `xlrd` y `olefile` con `uv`. `.xls` se lee con `xlrd` (conversión de celdas de fecha); `.doc` y `.ppt` se leen de los streams OLE `WordDocument` y `PowerPoint Document`, extrayendo cadenas imprimibles en UTF-16LE con fallback a Latin-1. Es best-effort: sin formato y con posible texto de metadatos.
- **Estado:** Completada. Cubierto por `tests/core/test_tools.py::test_read_document_legacy_formats` y `test_read_document_legacy_text_fallback`; documentado en `PRODUCT_BLUEPRINT/02_COMPONENTS/10_document_reading.md`, `docs/herramientas.md`, `README.md` y `PRODUCT_BLUEPRINT/03_SECURITY_AND_AUDIT/01_testing_y_mocks.md`.
- **Prueba en TUI:** Adjuntar un `.doc`, `.xls` y `.ppt` antiguos (barra de adjuntos o `@`) y pedir «lee estos documentos» → aparece el texto extraído; con formatos raros, aviso de extracción best-effort.

## Verificar soporte del modelo antes de aplicar prompt caching

- **Objetivo:** no enviar `cache_control` a modelos que no soportan esa extensión de la API compatible con OpenAI.
- **Estado:** Completada. `_supports_prompt_caching(model)` comprueba que el nombre contenga `claude` o `anthropic` (sin distinción de mayúsculas); `OpenAICompatibleProvider.chat()` solo reescribe el mensaje `system` cuando la guardia pasa, sin mutar los mensajes del caller. Actualizado `docs/herramientas.md` y `.env.example`. Cubierto por `tests/core/test_openai_provider.py::test_prompt_caching_model_support` y `::test_openai_provider_prompt_caching_skipped_for_unsupported_model`, además del test de caching con `anthropic/claude-3-5-sonnet-20241022`.
- **Prueba en TUI:** `/provider openrouter` + `/model` con un modelo Claude y con otro que no lo sea → ambas respuestas llegan sin error; F1 → sin errores de `cache_control` en el modelo no soportado.

## Códigos de respuesta de un solo uso

- **Objetivo:** añadir `/truth`, `/human`, `/nofluff`, `/devil`, `/decode` y `/genius` como códigos que cambian el estilo solo de la siguiente pregunta, sin `/normal`.
- **Estado:** Completada (flujo de entrada de `app/tui/app.py` autorizado por el usuario). `MODE_INSTRUCTIONS` y `mode_message()` viven en `app/tui/commands.py`; el comando fija `pending_mode` (y `pending_question` si lleva texto inline). `_begin_pending_mode()`/`_end_pending_mode()` inyectan el mensaje temporal y lo retiran en `_stream_user_message()` y en la rama de imágenes de `on_input_submitted()`, por lo que no queda en el historial y la pregunta siguiente vuelve al tono normal. Los códigos están en `AVAILABLE_COMMANDS` y `/help`. Cubierto por tests parametrizados en `tests/tui/test_commands.py` y por `tests/tui/test_app.py` (texto, inline e imágenes); documentado en `README.md` y `docs/herramientas.md`.
- **Prueba en TUI:** `/devil ¿qué fallos tiene este plan?` → tono crítico; hacer la pregunta siguiente sin código → vuelve al tono normal; `/help` → los seis códigos listados.

## Hooks del Harness — Fase 1 (observador)

- **Objetivo:** ejecutar comandos definidos por el usuario automáticamente en eventos del ciclo de vida, sin comando para activarlos.
- **Estado:** Completada. `app/core/harness/hooks.py` aporta `HookEvent`, `HookRegistry`, `HookManager` y `emit_hook()`; la config vive en `.harness/hooks.json` (`settings.hooks_file`) y admite `disableAllHooks`. Los handlers `command` se lanzan con `asyncio.create_subprocess_shell()` (el comando sale de la config de confianza; el evento va por stdin como JSON, sin interpolar), con timeout `TOOL_TIMEOUT` y fail-open. Disparadores: `UserPromptSubmit` (TUI y `AgentLoop.run()`), `PreToolUse`/`PostToolUse` (`_execute_tool()`), `PreCompact`/`PostCompact` (`ContextManager`) y `Stop`/`StopFailure` (`AgentLoop`). Cubierto por `tests/core/test_hooks.py` y por tests de integración en `test_agent_loop.py`, `test_context_compaction.py` y `test_app.py`. Documentado en `PRODUCT_BLUEPRINT/02_COMPONENTS/11_hooks.md` (y su índice), `docs/herramientas.md` y `README.md`.
- **Prueba en TUI:** Con un hook `command` en `.harness/hooks.json`: `/hooks` lo lista; enviar un prompt → se ejecuta el script y F1 muestra evento/handler con duración; `.harness/hooks/audit.log` registra la acción.

## Hooks — Bloqueo de borrados (fase 2 parcial)

- **Objetivo:** antes de abordar las fases 2 y 3 completas, prohibir eliminar archivos del proyecto mediante un hook `command` que pare la herramienta y entregue un mensaje al usuario.
- **Estado:** Completada. `HookOutcome` parsea `deny` por JSON (`hookSpecificOutput.permissionDecision`, o `decision: block`) y por exit 2 con motivo en stderr; el primer deny gana y corta la cadena de hooks. `AgentLoop._execute_tool()` consulta el outcome antes de los permisos: no ejecuta la herramienta, escribe el motivo en el resultado de la tool y emite el evento `hook_denied`, que `stream_to_chat()` muestra en el chat. `.harness/hooks/no_delete.py` inspecciona `tool_input.command` de `bash` (`rm`, `rmdir`, `unlink`, `shred`, `git rm`, `find -delete`, `os.remove`, `Path.unlink`, `shutil.rmtree`) y devuelve el `deny`; se registró como `PreToolUse` con matcher `bash` en `.harness/hooks.json`. `.harness/hooks/audit.py` expone `log_event()` como registrador compartido y `no_delete.py` lo usa para dejar constancia del bloqueo en `audit.log`, sin duplicar entradas con un segundo hook `PostToolUse`. Fail-open intacto: stdout vacío o inválido, errores y timeouts siguen permitiendo la acción. Cubierto por tests unitarios, de integración real con el script y de la TUI en `tests/core/test_hooks.py`, `tests/core/test_agent_loop.py` y `tests/tui/test_app.py`. Documentado en `PRODUCT_BLUEPRINT/02_COMPONENTS/11_hooks.md`, `docs/herramientas.md` y `README.md`.
- **Prueba en TUI:** Pedir «borra <archivo> con rm» → el chat muestra `🚫 Bloqueado por un hook` con el motivo y el archivo sigue existiendo; F1 → `status: denied`; `audit.log` → entrada del bloqueo.

## Hooks — Feedback de `Stop` y `PostToolUse` (fase 2A)

- **Objetivo:** aprovechar el `decision: block` de los hooks de cierre y post-herramienta para realimentar al agente en vez de ignorarlo.
- **Estado:** Completada. `AgentLoop._apply_hook_feedback()` convierte un `denied` en `[SISTEMA - FEEDBACK DE HOOK]: ...` con motivo del hook o texto genérico. `_emit_post_tool()` centraliza los cuatro `PostToolUse` y añade el feedback después de ejecutar la tool. `_emit_stop_with_feedback()` se usa en todos los cierres de `run()`/`stream()`: si hay `block`, se añade el mensaje y se reanuda el bucle; si ya se alcanzó `max_iterations`, se registra el feedback y se devuelve el resultado. Sin cambios en la TUI. Cubierto por 8 tests nuevos en `tests/core/test_agent_loop.py` (cierre normal, máximo de iteraciones, límite de reflexiones, post-tool y motivos vacíos); documentado en `PRODUCT_BLUEPRINT/02_COMPONENTS/11_hooks.md`, `docs/herramientas.md` y `README.md`.
- **Prueba en TUI:** Configurar un hook `Stop` con `decision: block` y hacer una pregunta → aparece `[SISTEMA - FEEDBACK DE HOOK]` y el agente continúa en lugar de cerrar el turno; F1 → evento `Stop` con su denegación.

## Hooks — `additionalContext` temporal (fase 2B)

- **Objetivo:** permitir que los hooks entreguen contexto adicional al modelo sin persistirlo en la sesión ni tocar el system prompt.
- **Estado:** Completada. `HookOutcome.additional_context` lee `hookSpecificOutput.additionalContext` (o la clave raíz) y se conserva aunque el hook devuelva `deny`. `HookManager.emit()` concatena los aportes de todos los hooks ejecutados en `UserPromptSubmit`/`PreToolUse`/`PostToolUse`, los deja en `pending_context` y `drain_context()` los entrega una sola vez. `ContextManager.append_hook_context()` crea un único mensaje temporal `user` y `remove_hook_context()` lo retira por identidad, replicando el patrón `_begin_pending_mode()`/`_end_pending_mode()` de la TUI sin cambiar su diseño. `AgentLoop` inyecta antes de cada llamada al LLM (`run()` y `stream()`) y limpia al terminar el turno. Cubierto por tests nuevos en `tests/core/test_hooks.py`, `tests/core/test_context_hooks.py` y `tests/core/test_agent_loop.py`, con comprobación de que el mensaje temporal no queda en el historial; documentado en `PRODUCT_BLUEPRINT/02_COMPONENTS/11_hooks.md`, `docs/herramientas.md` y `README.md`.
- **Prueba en TUI:** Hook `UserPromptSubmit` que devuelve `additionalContext`; enviar un prompt → el modelo lo usa y F1 lo muestra; `/session save`, reiniciar y `/session load` → el mensaje temporal NO está en el historial.

## Hooks — Tipos avanzados e interfaz (fase 3)

- **Objetivo:** ampliar los hooks con `http`/`prompt`/`agent`, matchers completos, filtro `if` y un visor `/hooks` en el chat, con recarga sin reiniciar.
- **Estado:** Completada. `HookRegistry` acepta cuatro tipos (`command`, `http`, `prompt`, `agent`), matchers con nombres, `|` y regex, y filtro `if` con firmas `herramienta:detalle` estilo permisos. `HookOutcome.from_text()` entiende `ok: false`, `permissionDecision`, `decision: block` y `additionalContext`; `http` usa `httpx`, `prompt` una llamada LLM y `agent` un `DelegateTool` con timeout de 60 s y permisos hijos. `_hook_depth` evita la recursión de hooks y que el loop anidado del subagente drene el contexto del turno padre. `HookManager` registra errores por handler, los muestra en `describe()` y recarga la configuración por mtime en cada evento. `/hooks` y `/hooks reload` se añadieron a `AVAILABLE_COMMANDS` y a `/help` con el diseño aprobado en el chat (sin modal nuevo). Cubierto por tests nuevos en `tests/core/test_hooks.py`, `tests/core/test_agent_loop.py` y `tests/tui/test_commands.py` con cobertura del 100 %; documentado en `PRODUCT_BLUEPRINT/02_COMPONENTS/11_hooks.md`, `docs/herramientas.md` y `README.md`.
- **Prueba en TUI:** Ejecutar `uv run python server/test_hook_types.py`, arrancar la TUI y `/hooks` → listados `command`, `http`, `prompt` y `agent`; editar `hooks.json` con la TUI abierta → se recarga por mtime; F1 → detalle JSON por handler.

- **Decisiones de diseño conservadas:** activación automática (sin comando para dispararlos; `/hooks` es solo un visor), configuración en `.harness/hooks.json` y nunca en `.claude/settings.json`, sin dependencias nuevas (`httpx` ya estaba en `pyproject.toml`), fail-open ante errores y `agent_name`/`agent_depth` en los eventos de subagentes A2A. Los commits se hicieron solo con aprobación explícita del usuario.

## Hooks — Latencia percibida al enviar un prompt

- **Objetivo:** que un hook `prompt`/`agent` lento en `UserPromptSubmit` no retrase la respuesta visual de la TUI.
- **Estado:** Completada. `_stream_user_message()` y la rama de imágenes pintan el mensaje y activan «Pensando…» antes de esperar `emit_hook(..., parallel=True)`. `HookManager.emit(parallel=True)` ejecuta los handlers concurrentemente pero reduce los resultados en orden de configuración: mismo `additionalContext` concatenado y mismo primer deny ganador; los eventos de herramientas siguen en modo serie. Los tests de TUI y loop se aislaron del `hooks.json` local con fixtures en `tests/conftest.py` y `tests/tui/conftest.py`. Cubierto por tests nuevos y documentado en `PRODUCT_BLUEPRINT/02_COMPONENTS/11_hooks.md`, `docs/herramientas.md` y `README.md`.
- **Prueba en TUI:** Configurar un hook `prompt` lento en `UserPromptSubmit`; enviar un mensaje → tu texto y «Pensando…» aparecen de inmediato, antes de que termine el hook; F1 → duración del handler.

## Hooks — Observabilidad en el panel de debug

- **Objetivo:** ver el ciclo de vida completo de los hooks (evento, matcher, input, output, estado y duración) sin depender de sondeos externos.
- **Estado:** Completada. `HookManager._run_handler()` publica un JSON por handler y `emit()` otro con el resumen agregado; `DebugEventCollector` los formatea como entradas `🪝 ...` con detalle JSON en el modal. Cubierto por tests nuevos en `tests/core/test_hooks.py` y `tests/core/test_logger.py`, y documentado en `PRODUCT_BLUEPRINT/02_COMPONENTS/11_hooks.md`, `docs/herramientas.md` y `README.md`.
- **Prueba en TUI:** Tras usar herramientas y hooks, pulsar F1 → entradas `🪝` con evento, matcher, input, output, estado y duración; pulsar una entrada → se abre el detalle JSON.

## Hooks — Motivos de error legibles

- **Objetivo:** evitar warnings y trazas de debug con el motivo vacío cuando un hook agota su timeout.
- **Estado:** Completada. `HookManager._format_hook_error()` añade el tipo de excepción y el límite de tiempo (`TimeoutError: superó 10s`) en `command`, `http`, `prompt` y `agent`; `_record_error()` usa `error sin motivo` como fallback. El panel de debug marca estos casos como `status: error` con el motivo visible. Cubierto por tests nuevos y documentado en `PRODUCT_BLUEPRINT/02_COMPONENTS/11_hooks.md` y `docs/herramientas.md`.
- **Prueba en TUI:** Configurar un hook con timeout de 1 s que tarde más; `/hooks` → `⚠️ TimeoutError: superó 1s`; F1 → `status: error` con el motivo, sin traza vacía.

## Hooks — Contrato `http` y diagnóstico de timeouts de `agent`

- **Objetivo:** dejar por escrito el contrato de respuesta de los hooks `http` y la causa de los timeouts del hook `agent`, que hasta ahora solo estaban explicados en el chat.
- **Estado:** Completada (documentación). `PRODUCT_BLUEPRINT/02_COMPONENTS/11_hooks.md` detalla que la ruta HTTP es solo una etiqueta, que el efecto lo decide el JSON de respuesta, que el texto plano se ignora y que un `>= 400` es fail-open; también registra que el hook `agent` hereda `settings.LLM_PROVIDER`, que su timeout por defecto es 60 s y que con `OPENROUTER` tardó 17,51 s en una ejecución real, por lo que 1–10 s son insuficientes. `docs/herramientas.md` incluye el resumen. Sin cambios de código ni commits nuevos.
- **Prueba en TUI:** Con `server/test_hook_types.py`: `/context` añade contexto adicional y `/deny` bloquea la tool aunque la ruta sea solo una etiqueta; `/hooks` → sin errores; contrato reflejado en `PRODUCT_BLUEPRINT/02_COMPONENTS/11_hooks.md`.

## Logs — Nombre diario del archivo

- **Objetivo:** sustituir `harness_debug.log` por un archivo identificable por día (`yyyy_MM_dd_harness.log`).
- **Estado:** Completada. `Settings.log_file` calcula la ruta diaria y `app/core/logger.py` la usa para el `FileHandler`. `DailyFileHandler` rota automáticamente al cambiar de día, incluso con la TUI abierta. Cubierto por test en `tests/core/test_logger.py`; documentado en `README.md` y `docs/herramientas.md`, y actualizado el mensaje de `scripts/verify_memory_backends.py`.
- **Prueba en TUI:** Enviar un prompt y comprobar `.harness/logs/yyyy_MM_dd_harness.log` con la fecha de hoy → contiene los eventos; F1 sigue mostrando los mismos eventos.

## P0.1 Cerrar el bypass de permisos en subagentes

- **Objetivo:** ningún subagente puede heredar `ALLOW` para `bash` ni `write_file` sin una decisión explícita del usuario.
- **Diseño elegido:** `DelegateTool.run()` y el hook `agent` derivan el gate con `child()` sin `allow`: comparten `session_allowed`, `ask_user` y `persist_file` con el padre, copian las `policies` y dejan las tools sensibles en `ASK`. El campo `tools` del hook `agent` ya no concede permisos. P0.9 queda pendiente para el modelo de petición pendiente por sesión en background/paralelo real.
- **Estado:** Completada. Cambios en `app/core/harness/subagents.py` y `app/core/harness/hooks.py`; blueprint actualizado (`02_permission_gate.md`, `05_subagents.md`, `08_a2a.md`, `03_SECURITY_AND_AUDIT/02_a2a_security.md` y `11_hooks.md`).
- **Tests:** `tests/core/test_subagents.py` (herencia sin auto-allow y `DENY` sin `ask_user`), `tests/core/test_hooks.py` (el hook `agent` no auto-aprueba `tools`) y `tests/tui/test_app.py::test_reviewer_subagent_asks_for_bash_in_tui`. `uv run tom test` → 565 passed, 100 % de cobertura.
- **Prueba en TUI:** ejecutada con el piloto de Textual: arrancar `AgentHarnessApp`, inicializar agente con `bash` registrado, lanzar `delegate_to_reviewer` con una tarea que pide `bash` → aparece `PermissionModal`; pulsar «y» → el subagente recibe `allow`. Esperado y observado: sin modal no se ejecuta la tool. Para repetirlo en la TUI interactiva: `/subagents` → reviewer; pedir una tarea con `bash` → modal de permisos; F1 → sin `ALLOW` implícito en el gate hijo.
- **DoD:** ✅ tests/cobertura · ✅ TUI (piloto Textual) · ✅ seguridad (sin secretos, `logger`, permisos diff-first) · ✅ docs · ✅ commiteado en `85fdaad` (aprobación explícita del usuario).

## P0.3 Tratar las aprobaciones persistentes como texto literal

- **Objetivo:** una firma aprobada con `a` y persistida en `.harness/permissions.json` autoriza solo esa firma exacta; `*`, `?` y `[...]` no pueden actuar como globs.
- **Diseño elegido:** `PermissionGate._is_allowed()` usa `signature in self.session_allowed` y se elimina `import fnmatch` de `permissions.py`. El `fnmatch` de `hooks.py` se conserva: es del filtro `if` de hooks, no de permisos.
- **Estado:** Completada. Los tests de regresión se escribieron primero: 4 fallaban con `fnmatch` ( `*`, `?`, `[...]` y persistencia tras reinicio) y pasan con la comparación exacta. Documentación actualizada en `PRODUCT_BLUEPRINT/02_COMPONENTS/02_permission_gate.md`, `PRODUCT_BLUEPRINT/02_COMPONENTS/11_hooks.md` y `docs/herramientas.md`.
- **Tests:** `tests/core/test_permissions.py` (aprobación literal en memoria y tras recargar JSON; se añadió `AsyncMock` a los imports) y `tests/tui/test_app.py::test_tui_persisted_approval_is_literal_after_restart`. `uv run tom test` → 571 passed, 100 % de cobertura.
- **Prueba en TUI:** ejecutada con el piloto de Textual: arrancar `AgentHarnessApp`, pedir `bash` con comando `grep *.log` → aparece `PermissionModal`; pulsar «a» → se guarda `bash:grep *.log` en `.harness/permissions.json`; simular reinicio con un gate nuevo → `grep *.log` sigue autorizado y `grep secrets.log` / `grep .env` vuelven a pedir permiso (observado: `DENY` con `ask_user` que responde «n»). Para repetirlo en la TUI interactiva: aprobar `grep *.log` con «a», reiniciar la TUI, pedir `grep .env` → debe aparecer el modal.
- **DoD:** ✅ tests/cobertura · ✅ TUI (piloto Textual) · ✅ seguridad (sin secretos, permisos literales) · ✅ docs · ✅ commiteado en `79cfcad` (aprobación explícita del usuario).

## P0.2 Aprobar exactamente el comando que se ejecuta

- **Objetivo:** `BashTool` ejecuta literalmente el comando aprobado por `PermissionGate`; ninguna escritura derivada se dispara sin permiso.
- **Diseño elegido:** se eliminó el hook de `BashTool` que inyectaba `--tools observations.json` y llamaba a `export_observations.run()` sin gate. `export_observations` sigue registrado como tool independiente (`app/tools/__init__.py`), así que el modelo debe pedirlo explícitamente y esa escritura pasa por `PermissionGate`. `BashTool` pierde el parámetro `export_observations` y ya no importa `json`, `re`, `Path` ni `logger`.
- **Estado:** Completada. Los tests de regresión se escribieron primero (3 fallaban: el comando se reescribía y la tool seguía teniendo el exportador) y pasan con el fix. Documentación actualizada en `docs/herramientas.md`, `docs/analogia-cocina.md` y la skill `agent-harness-explorer`.
- **Tests:** `tests/core/test_tools.py::test_bash_tool_executes_approved_command_verbatim` (con y sin `--out`) y `tests/tui/test_app.py::test_tui_bash_approved_command_is_executed_verbatim`. `uv run tom test` → 572 passed, 100 % de cobertura.
- **Prueba en TUI:** ejecutada con el piloto de Textual: `AgentLoop._execute_tool` pide `bash` con `python scripts/capture_snapshot.py --out report.md` → aparece `PermissionModal` mostrando exactamente ese comando, sin `--tools`; pulsar «y» → `asyncio.create_subprocess_shell` recibe el comando aprobado sin modificaciones y `export_observations` no se invoca ni aparece `observations.json`. Para repetirlo en la TUI interactiva: pedir `capture_snapshot.py`, aprobar con «y» y comprobar en F1 el comando ejecutado y que no se creó `observations.json`.
- **DoD:** ✅ tests/cobertura · ✅ TUI (piloto Textual) · ✅ seguridad (sin escrituras implícitas) · ✅ docs · ✅ commiteado en `67a511f` (aprobación explícita del usuario).

## P0.4 Sanear IDs de sesión y validar el historial cargado

- **Objetivo:** los IDs de sesión no pueden escapar del directorio de sesiones; un historial manipulado no puede inyectar mensajes `system` ni reventar el arranque de la TUI.
- **Diseño elegido:** `SessionManager` valida el ID con una allowlist (`^[A-Za-z0-9_-]+$`) en el constructor, `list_sessions()` y `delete_session()`; `load()` tolera JSON corrupto/ilegible y filtra los mensajes `system` del archivo. `merge_session_history()` antepone los mensajes `system` del contexto vigente al restaurar, y lo usan tanto el arranque de la TUI como `/session load`. Ese comando captura el `ValueError` del ID y avisa sin llamar a `load()`.
- **Estado:** Completada. Tests de regresión escritos antes que el código: fallaban 12 comprobaciones (IDs inseguros, `system` inyectado, JSON corrupto, borrado inseguro y las dos rutas de restauración) y pasan con el fix. Documentación actualizada en `docs/herramientas.md`, `docs/analogia-cocina.md` y `PRODUCT_BLUEPRINT/02_COMPONENTS/03_context_compaction.md`, sin IDs de tarea ni números de línea.
- **Tests:** `tests/core/test_session.py` (IDs inseguros, borrado inseguro, filtro de `system`, JSON corrupto), `tests/tui/test_commands.py` (rechazo de `/session load ../../mcp_config` sin llamar a `load()` y conservación del prompt al cargar) y `tests/tui/test_app.py::test_tui_session_load_ignores_injected_system_message`. `uv run tom test` → 584 passed, 100 % de cobertura.
- **Prueba en TUI:** ejecutada con el piloto de Textual: crear una sesión con un mensaje `role: system` y arrancar `AgentHarnessApp` → el historial queda con el `system` original («Reglas originales») seguido del mensaje de usuario, sin la instrucción inyectada; `/session load ../../mcp_config` → responde «ID de sesión no válido» y `SessionManager.load()` no se llama; `/session load` con repair counts → vuelve a cargar el historial y los contadores. Para repetirlo en la TUI interactiva: guardar una sesión con un mensaje `system` manipulado, reiniciar y comprobar que el prompt sigue siendo el de `AGENTS.md` + memoria; probar `/session load ../../mcp_config` y verificar que `mcp_config.json` permanece intacto.
- **DoD:** ✅ tests/cobertura · ✅ TUI (piloto Textual) · ✅ seguridad (IDs con allowlist, sin inyección de `system`, JSON tolerante) · ✅ docs · ✅ commiteado con aprobación explícita del usuario.

## P0.5 No filtrar secretos a servidores MCP y fijar versiones

- **Objetivo:** los servidores MCP solo reciben variables de entorno permitidas explícitamente, sin secretos por defecto, y los comandos externos usan versiones fijas.
- **Diseño elegido:** `MCPClient` dejó de copiar `os.environ`: `_build_server_env()` entrega un conjunto mínimo de variables de ejecución no sensibles más las que cada servidor declara en `allowed_env`; `env` fija valores literales y prevalece sobre lo heredado. La TUI pasa `allowed_env` desde `mcp_config.json`. Los paquetes `uvx` y el wrapper `npx` quedan fijados a versiones concretas. El test de integración estaba obsoleto: comprobaba nombres de tools sin el prefijo `mcp_local_dev_` y, al fallar, dejaba el cliente sin desconectar; se actualizó para usar los nombres reales.
- **Estado:** Completada. Los tests de regresión se escribieron antes que el código: 4 fallaban (herencia de secretos, allowlist, versiones sin fijar y propagación desde la TUI) y pasan con el fix. Documentación actualizada en `README.md`, `docs/herramientas.md` y `PRODUCT_BLUEPRINT/02_COMPONENTS/04_mcp_integration.md`, sin IDs de tarea ni números de línea.
- **Tests:** `tests/mcp/test_mcp_client.py` (sin secretos heredados, allowlist y versiones fijadas) y `tests/tui/test_app.py::test_app_initialize_agent_passes_allowed_mcp_env`. `uv run tom test` → 588 passed, 100 % de cobertura. `uv run tom test-integration` → 9 passed (incluye el servidor MCP local con `HARNESS_E2E` permitido explícitamente).
- **Prueba en TUI:** ejecutada con el piloto de Textual: inicializar `AgentHarnessApp` con el `mcp_config.json` real → `MCPClient` recibe `allowed_env=['HARNESS_E2E']` para `local_dev` y `None` para el resto; comprobación directa del proceso hijo → ve `HARNESS_E2E=1`, ejecuta `echo_message` y `run_tests` vuelve «saltado en modo E2E», sin `OPENAI_API_KEY` ni `LANGFUSE_SECRET_KEY`. Para repetirlo en la TUI interactiva: con MCP activo, `/tools` → tools remotas con prefijo `mcp_<servidor>_`; `/doctor` → sin errores; inspeccionar el entorno del proceso del servidor → sin claves de LLM/Langfuse.
- **DoD:** ✅ tests/cobertura · ✅ TUI (piloto Textual) · ✅ seguridad (sin secretos heredados, allowlist por servidor, versiones fijadas) · ✅ docs · ✅ commiteado con aprobación explícita del usuario.

## P0.6 Restringir hooks `command`/`http` y aplicar sus denegaciones en la TUI

- **Objetivo:** los hooks `command` y `http` solo apunten a destinos permitidos y un `denied` en `UserPromptSubmit` bloquee el prompt de verdad.
- **Diseño elegido:** `HookRegistry.load()` valida cada handler antes de registrararlo: comandos sin operadores de shell (ni encadenamiento, expansión ni sustitución) y URLs HTTP(S) de loopback sin credenciales. Lo rechazado se guarda en `registry.rejected`, se publica en `HookManager.errors` y `/hooks` lo muestra bajo «Hooks descartados». `_launch()` y `_launch_http()` repiten la comprobación por si un handler se construye fuera de la configuración. En la TUI, `_reject_prompt()` muestra el motivo, apaga el indicador y evita llamar a `agent_loop.stream()`; en la rama de imágenes el hook se dispara antes de `add_user_with_image()` para que ni el texto ni la imagen lleguen al contexto.
- **Estado:** Completada. Los tests de regresión se escribieron antes que el código y fallaban (funciones de validación inexistentes, handlers remotos aceptados, prompt denegado enviado al agente); pasan con el fix. Documentación actualizada en `README.md`, `docs/herramientas.md` y `PRODUCT_BLUEPRINT/02_COMPONENTS/11_hooks.md`, sin IDs de tarea ni números de línea.
- **Tests:** `tests/core/test_hooks.py` (URLs loopback, comandos seguros, rechazos visibles en `/hooks` y guards en ejecución) y `tests/tui/test_app.py` (bloqueo del prompt de texto y multimodal). `uv run tom test` → 612 passed, 100 % de cobertura. `uv run tom test-integration` → 9 passed (HTTP de hooks incluido en la verificación manual).
- **Prueba en TUI:** ejecutado `uv run python server/test_hook_types.py --seconds 3` → los cuatro tipos se instalan, el servidor HTTP arranca en loopback y el `hooks.json` original se restaura. Después, con un servidor HTTP real en `127.0.0.1` y la configuración de ejemplo más un `/deny` en `UserPromptSubmit`, se levantó `AgentHarnessApp` con el piloto de Textual: `/hooks` → `agent`, `command`, `http` y `prompt`; `PreToolUse` con `bash:ls -la` → deny «Bloqueado por el hook http de prueba»; prompt «Hola» → mensaje de bloqueo en el chat, `stream.call_count == 0` y F1 mostrando el ciclo `🪝 emit · UserPromptSubmit`. El archivo `.harness/hooks.json` del usuario quedó restaurado.
- **DoD:** ✅ tests/cobertura · ✅ TUI (piloto Textual con HTTP real) · ✅ seguridad (URLs loopback, comandos sin operadores, deny respetado) · ✅ docs · ✅ commiteado con aprobación explícita del usuario.

## P0.7 Evitar que los scripts destructivos toquen datos reales

- **Objetivo:** los scripts de diagnóstico usen directorios temporales, restauren backups y devuelvan código de salida no cero si fallan; el checklist deje de obligar a ejecutar el script que borraba la caché real.
- **Diseño elegido:** `scripts/_isolated_data.py` aporta `isolated_data_dir()`, un context manager que redirige `settings.DATA_DIR` a un directorio temporal (o al que se le pase, para sembrar datos en los tests) y lo restaura en `finally`. Como memoria, caché de pricing, sesiones y logs derivan de `DATA_DIR`, ningún script alcanza datos reales. `verify_memory_backends.main()` ejecuta las comprobaciones dentro de ese contexto, recoge los resultados y devuelve 1 si alguno falla. `check_pricing._diagnose()` aparta la caché a `.bak` y la restaura en `finally` tanto en éxito como en error; `main()` devuelve el código de salida. `checks/tests.md` ya no obliga a ejecutar el script y el DoD ya no apunta a una tarea pendiente.
- **Estado:** Completada. Los 6 tests de regresión se escribieron antes que el código y fallaban (retorno `None`, borrado de la ruta real, helper inexistente, backup no restaurado); pasan con el fix. Documentación actualizada en `checks/tests.md` y `tasks/DEFINITION_OF_DONE.md`, sin IDs de tarea ni números de línea en la documentación de producto. No se añadió nada al blueprint porque los scripts de diagnóstico no son componentes del producto.
- **Tests:** `tests/test_diagnostic_scripts.py` (aislamiento de memoria y caché, códigos de salida, restauración en `finally` y configuración ausente). `uv run tom test` → 618 passed, 100 % de cobertura. `uv run tom test-integration` → 9 passed (el diagnóstico de pricing usa HTTP).
- **Prueba en TUI:** ejecutada con el piloto de Textual: `/doctor` → «Diagnóstico del Sistema» y `/cost` → «Coste de la Última Llamada», ambos añaden su mensaje al chat sin errores. Como las pruebas previstas también cubrían los scripts, se ejecutaron por CLI: `uv run python scripts/verify_memory_backends.py` → 4/4 comprobaciones «PASÓ», `EXIT_CODE=0`, hashes de `.harness/memory.db` y `.harness/pricing_cache.json` idénticos antes y después; `scripts/check_pricing.py` contra servidor HTTP local en `127.0.0.1` con configuración temporal → `EXIT_CODE=0` y «Diagnóstico completado»; con URL inalcanzable → `EXIT_CODE=1`, «La API no devolvió precios», caché real intacta y sin `.bak`. El `hooks.json` del usuario no se tocó.
- **DoD:** ✅ tests/cobertura · ✅ TUI (`/doctor` y `/cost` con piloto Textual, más sustitución por CLI) · ✅ seguridad (directorios temporales, backup restaurado en finally, sin borrados reales) · ✅ docs · ✅ commiteado con aprobación explícita del usuario.

## P0.8 Dejar de inflar la cobertura

- **Objetivo:** medir el manejo de errores y los handlers de TUI, dejar de silenciar `RuntimeWarning` y no ignorar los tests de integración en la configuración por defecto.
- **Diseño elegido:** `[tool.coverage.report].exclude_lines` se reduce a las tres exclusiones que el intérprete no puede ejecutar (`pragma: no cover`, bloques `if __name__ == ...` y cuerpos `...`). Se eliminan `filterwarnings = ["ignore::RuntimeWarning"]` y `--ignore=tests/integration` de `addopts`, y se mantiene `--cov-fail-under=100`. Los tests nuevos provocan las ramas defensivas (tools que lanzan, cachés corruptas, apps que no arrancan, timeouts, eventos de Textual) y comprueban el resultado observable en lugar de números de línea. Los coroutines filtrados se corrigen en los tests (generadores asíncronos y `AsyncMock` con valor de retorno realista), no se ocultan.
- **Estado:** Completada. Cambios en `pyproject.toml`, tests de regresión en `tests/test_init_files.py`, `tests/core/`, `tests/mcp/` y `tests/tui/`, y documentación en `README.md`, `PRODUCT_BLUEPRINT/03_SECURITY_AND_AUDIT/01_testing_y_mocks.md` y `tasks/DEFINITION_OF_DONE.md`, sin IDs de tarea ni números de línea en la documentación de producto.
- **Tests:** medición previa con configuración estricta (`cov_real.ini`) → `TOTAL 3775 0 100 %` con 657 tests; `uv run tom test` → **667 passed, 100 % de cobertura real**, sin exclusiones artificiales ni integración ignorada; `uv run tom test-integration` → **9 passed**; `uv run pytest tests/ -q -W always::RuntimeWarning` → **667 passed sin resumen de warnings**. Entre los tests nuevos: configuración sin exclusiones, manejo de errores de Langfuse y tools, cachés Pricing corruptas, archivos de memoria ilegibles, timeouts de MCP y modales de permisos.
- **Prueba en TUI:** N/A (proceso de tests y configuración) con sustitución ejecutada: `uv run tom test` y la comprobación de warnings en toda la suite; además se arrancó `AgentHarnessApp` con el piloto de Textual y `LLM_PROVIDER=fake` y se ejecutó `/doctor` → «Diagnóstico del Sistema» en el chat, sin errores. Durante la verificación se terminaron los servidores de prueba huérfanos (`test_hook_types.py` y `local_mcp_server.py`); el `hooks.json` local quedó en su estado previo y no se incluye en el commit.
- **DoD:** ✅ tests/cobertura (100 % real) · ✅ TUI (smoke con piloto Textual) · ✅ seguridad (sin secretos ni filtros que oculten fallos) · ✅ docs · ✅ commiteado con aprobación explícita del usuario; `.harness/hooks.json` se dejó fuera.

## P0.9 Desacoplar la aprobación del modal: petición pendiente por sesión

- **Objetivo:** las decisiones `ALLOW`/`DENY` se resuelven localmente sin modal; un `ASK` encola una petición con `sessionID` del subagente, `requestID`, firma/recursos y patrones propuestos, y el tool call espera la respuesta. La TUI puede listar y responder peticiones del hijo aunque el padre siga trabajando: `once` vale solo para esa petición, `always` guarda patrones literales y nunca vence a un `deny` configurado, `reject` cierra esa y todas las pendientes de la misma sesión. Sin cliente (background/headless) la petición queda pendiente o se rechaza según política, nunca se auto-aprueba.
- **Diseño elegido:** `PermissionBroker`, `PermissionRequest`, `PermissionReply` y `normalize_reply()` viven en `app/core/harness/permissions.py`; `PermissionGate.check()` usa el broker y conserva `ask_user` solo para llamadores antiguos. El `deny` configurado se evalúa antes que las aprobaciones y se vuelve a comprobar mientras la petición espera. Los gates hijos comparten broker y `session_allowed` con `session_id`: `main`, `a2a:<agente>`, `delegate:<nombre>` y `hook:agent`. La TUI tiene un listener no bloqueante, `/permissions pending`, `/permissions reply <requestID> <once|always|reject>`, el panel F1 y un worker `permissions` separado de `conversation`; el modal legacy sigue disponible. Headless usa `PermissionBroker(unattended="deny")` por defecto y `"pending"` deja la petición en cola sin aprobar.
- **Estado:** Completada. Cambios en `app/core/harness/permissions.py`, `app/tui/app.py`, `app/tui/commands.py`, los gates de A2A/delegate/hooks y `app/core/llm/__init__.py`; documentación actualizada en `README.md`, `docs/herramientas.md`, `docs/analogia-cocina.md` y `PRODUCT_BLUEPRINT/` sin IDs de tarea ni números de línea.
- **Tests:** tests de regresión escritos antes del código en `tests/core/test_permission_requests.py`, `tests/tui/test_app.py`, `tests/tui/test_commands.py` y `tests/core/test_llm_factory.py` (cola, `once`/`always`/`reject`, headless, A2A paralelo, F1, worker separado, proveedor fake con `model=None`). Dos fallos aparecidos en la verificación real se arreglaron también con test previo: `get_llm("fake", model=None)` y el refresco concurrente del panel (`DuplicateIds`), serializado con un lock. `uv run tom test` → **712 passed, 100 % de cobertura**; `uv run tom test-integration` → **9 passed**; `uv run python -m pytest tests/ -q -W error::RuntimeWarning --cov=app --cov-report=term --cov-fail-under=100` → **712 passed, sin warnings, 100 % real**.
- **Prueba en TUI:** ejecutada con `LLM_PROVIDER=fake`, `MEMORY_BACKEND=memory` y `AgentHarnessApp().run_test()` en un directorio temporal: arranque correcto; `/tools` lista `bash`; `/permissions pending` sin peticiones; A2A `parallel` con dos agentes → dos peticiones `bash:ls` con sesiones `a2a:analyst` y `a2a:reviewer`; F1 muestra ambos `requestID`; `/permissions reply <requestID> once` deja solo la del reviewer; `always` devuelve `## analyst allow --- ## reviewer allow`; `reject` cierra `bash:pwd` y `bash:date` de esa sesión con `Decision.DENY`; `permissions.json` queda con `{'session_allowed': ['bash:ls']}`. Sin suscriptor, headless deniega; al reiniciar sobre el mismo directorio la firma exacta devuelve `Decision.ALLOW` y una distinta, `Decision.DENY`. El padre sigue trabajando durante todas las respuestas; no se cancela.
- **DoD:** ✅ tests/cobertura (100 % real) · ✅ TUI (piloto Textual con A2A real, F1 y comandos) · ✅ seguridad (`deny` prevalece, sin autoaprobación, firma literal, sin secretos) · ✅ docs · ⛔ commit pendiente de aprobación explícita; `.harness/hooks.json` es ajeno y queda fuera.
