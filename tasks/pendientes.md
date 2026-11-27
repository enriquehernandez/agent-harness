# Tareas Pendientes

> Inventario de funcionalidad pendiente. Las tareas en ejecución están en `tasks/actual.md`; las completadas, en `tasks/completadas.md`.
> La auditoría de los commits del 16–24 de noviembre de 2026 quedó cerrada. El inventario siguiente sale de la revisión completa del 27 de noviembre de 2026 y está ordenado por prioridad: **P0** (bloqueantes), **P1** (funcionales/estabilidad), **P2** (calidad y tooling).
> La Definition of Done (tests, cobertura, pasos en TUI y puerta de commit) está en `tasks/DEFINITION_OF_DONE.md`, con plantillas para pendiente, en curso y completada. Las tareas P0 ya traen `Prueba en TUI prevista`; el resto la añade al pasar a `tasks/actual.md`.
> Las referencias son a archivos y símbolos, nunca a números de línea: el código cambia y esas referencias se quedan obsoletas.

## P0 — Bloqueantes (seguridad e integridad de datos)

### P0.4 Sanear IDs de sesión y validar el historial cargado
- **Problema:** `app/core/harness/session.py` construye rutas con el ID del usuario sin validar; `app/tui/app.py` inyecta como `system` mensajes de un JSON manipulado.
- **Criterio:** IDs rechazados si contienen `/`, `..` o son absolutos; `load()` filtra/desarma mensajes `system`; JSON corrupto no revienta `on_mount`. Tests para `/session load ../../mcp_config` y para un session file con `role: system`.
- **Prueba en TUI prevista:** `/session load ../../mcp_config` → rechazado sin tocar otros JSON; meter un mensaje `role: system` en una sesión, reiniciar la TUI → el system prompt no se sustituye.
- **DoD:** ⛔ pendiente — se completa al pasar a `tasks/actual.md` y cerrar en `tasks/completadas.md`.

### P0.5 No filtrar secretos a servidores MCP y fijar versiones
- **Problema:** `app/mcp/client.py` copia `os.environ` completo (API keys, Langfuse) en cada servidor; `mcp_config.json` usa `uvx`/`npx` sin versión fija.
- **Criterio:** allowlist explícita de variables por servidor, sin secretos por defecto; versiones pinnadas; test que compruebe que las claves no aparecen en `client.env`.
- **Prueba en TUI prevista:** Con MCP activo, `/tools` → las tools siguen funcionando; inspeccionar el proceso del servidor → sin API keys en su entorno; `/doctor` sin errores.
- **DoD:** ⛔ pendiente — se completa al pasar a `tasks/actual.md` y cerrar en `tasks/completadas.md`.

### P0.6 Restringir hooks `command`/`http` y aplicar sus denegaciones en la TUI
- **Problema:** `app/core/harness/hooks.py` ejecuta shell y URLs arbitrarias de `.harness/hooks.json`; `app/tui/app.py` descarta el `denied` de `UserPromptSubmit`.
- **Criterio:** validación/allowlist de URLs (mínimo: solo loopback) y comandos; un `denied` en `UserPromptSubmit` bloquea el prompt realmente. Usar `server/test_hook_types.py` como prueba manual (los cuatro tipos: `command`, `http`, `prompt`, `agent`).
- **Prueba en TUI prevista:** Ejecutar `uv run python server/test_hook_types.py`, `/hooks` → los cuatro tipos listados; el hook `http /deny` bloquea `bash:ls`; un `UserPromptSubmit` con deny impide enviar el prompt; F1 muestra el ciclo.
- **DoD:** ⛔ pendiente — se completa al pasar a `tasks/actual.md` y cerrar en `tasks/completadas.md`.

### P0.7 Evitar que los scripts destructivos toquen datos reales
- **Problema:** `scripts/verify_memory_backends.py` borra `.harness` y siempre termina con éxito; `scripts/check_pricing.py` elimina la caché si falla la descarga; `checks/tests.md` obliga a ejecutarlo.
- **Criterio:** los scripts usan directorios temporales, restauran backups en `finally` y devuelven código de salida no cero si fallan; quitar la instrucción obligatoria del checklist.
- **Prueba en TUI prevista:** N/A en TUI (scripts de diagnóstico): ejecutarlos contra un repo temporal → la memoria y la caché reales siguen intactas; `/doctor` y `/cost` sin errores.
- **DoD:** ⛔ pendiente — se completa al pasar a `tasks/actual.md` y cerrar en `tasks/completadas.md`.

### P0.8 Dejar de inflar la cobertura
- **Problema:** `pyproject.toml` excluye `except`, `continue`, `return` y `on_*/watch_*/compose` y silencia `RuntimeWarning`; `tests/integration` se ignora en `addopts`.
- **Criterio:** medir el manejo de errores y los handlers de TUI; aceptar que el porcentaje baje temporalmente y cubrirlo con tests de comportamiento; no silenciar `RuntimeWarning`.
- **Prueba en TUI prevista:** N/A en TUI (proceso): `uv run tom test` con las exclusiones reducidas → cobertura real sin `RuntimeWarning`; arrancar la TUI y `/doctor` sin errores.
- **DoD:** ⛔ pendiente — se completa al pasar a `tasks/actual.md` y cerrar en `tasks/completadas.md`.

### P0.9 Desacoplar la aprobación del modal: petición pendiente por sesión
- **Problema:** `PermissionGate.check()` hace `await self.ask_user(...)` en el mismo proceso (`app/core/harness/permissions.py`). En background (`ask_user=None`) deniega sin poder preguntar y en A2A `parallel` (`app/core/harness/a2a/strategies/parallel.py`) se apilan modales. OpenCode resuelve el `ask` como una `PermissionRequest(sessionID, requestID, resources, save)` y espera un `reply` externo `once|always|reject`.
- **Criterio:** las decisiones `ALLOW`/`DENY` se resuelven localmente sin modal; un `ASK` encola una petición con `sessionID` del subagente, `requestID`, firma/recursos y patrones propuestos, y el tool call espera la respuesta. La TUI puede listar y responder peticiones del hijo aunque el padre siga trabajando: `once` vale solo para esa petición, `always` guarda patrones literales (depende de P0.3) y nunca vence a un `deny` configurado, `reject` cierra esa y todas las pendientes de la misma sesión. Sin cliente (background/headless) la petición queda pendiente o se rechaza según política, nunca se auto-aprueba.
- **Dependencias:** P0.1 y P0.3; deja P1.7 como parche temporal del modal y es el paso previo para igualar el modelo de permisos de OpenCode.
- **Prueba en TUI prevista:** lanzar el reviewer/A2A `parallel` con una tool sin aprobar → el prompt aparece asociado al subagente (F1 muestra su `sessionID`); responder «y» → ejecuta solo esa llamada y la siguiente vuelve a preguntar; responder «a» → persiste y no pregunta tras reiniciar; responder «n» → se bloquean las peticiones pendientes de esa sesión y el subagente devuelve error; con background sin cliente → la tool queda pendiente o denegada, nunca ejecutada.
- **DoD:** ⛔ pendiente — se completa al pasar a `tasks/actual.md` y cerrar en `tasks/completadas.md`.

## P1 — Funcionales y estabilidad

### P1.1 Cerrar generadores de stream
- `app/tui/app.py` hace `break` sin `await stream_gen.aclose()`; el `finally` de `app/core/harness/loop.py` (Langfuse + contexto de hooks) no se ejecuta. Añadir `aclose()` en todas las rutas de salida/error.

### P1.2 Liberar clientes LLM y subprocess
- `app/core/llm/providers/openai_provider.py` nunca cierra `AsyncOpenAI`; `app/tools/shell.py` hace `kill()` sin `wait()`. Añadir `close()`/`aclose()` y `await process.wait()`.

### P1.3 Guardar la respuesta cuando un hook `Stop` bloquea
- `app/core/harness/loop.py` inyecta el feedback pero no llama a `ctx.add_assistant(...)`; el modelo critics lo que no ve. Igualar a la rama del crítico.

### P1.4 Aislar el contexto de hooks entre loops concurrentes
- `app/core/harness/hooks.py` usa un único `pending_context` global: dos loops A2A se roban el contexto. Sustituir por estado por sesión/`ContextVar`.

### P1.5 Robustecer el proveedor OpenAI-compatible
- `max_tokens` no se envía a la API pero sí se usa como ventana de contexto (`app/core/llm/providers/openai_provider.py`); `json.loads` sin guard; deltas sin `index` descartados y posible `IndexError`; IDs de tool call colisionantes.

### P1.6 Crítico: parseo estricto y fail-closed
- `app/tools/critic.py` acepta cualquier texto que contenga `APPROVED`, y un error del LLM cuenta como aprobación. Exigir respuesta exacta y tratar el error como "no aprobado" sin coste extra involuntario.

### P1.7 Modal de permisos: timeout y markup
- `app/tui/app.py` usa `wait_for` sobre `push_screen_wait` con `shield`: el modal queda huérfano. Interpolar argumentos sin escapar en `app/tui/app.py` y `app/tui/modals/permission.py` permite `MarkupError` y falsear el texto. Escapar markup, cerrar la pantalla al caducar y serializar los modales con un `lock`. Es un parche temporal: la solución de fondo para background/paralelo es **P0.9**.

### P1.8 Consistencia de comandos TUI
- `/provider` no actualiza pricing ni LLMs del crítico/A2A (`app/tui/commands.py`, `app/tui/app.py`); `/compact` no restaura la estrategia con `try/finally`; `/session load` no limpia el chat y `/session delete` resucita la sesión; F1 y `/debug` desincronizados.

### P1.9 MCP: sesión zombie y reintento no idempotente
- `app/mcp/client.py` marca `self.session` antes de `initialize()` y vuelve a ejecutar la tool tras cualquier error, duplicando efectos. Cerrar el `exit_stack` en error y no reintentar escrituras.

## P2 — Calidad, tests y tooling

### P2.1 Sanear la suite de tests
- 15 definiciones duplicadas (solo se ejecuta la última), tests sin `assert` y tests que comprueban números de línea concretos. Ver `tests/tui/test_app.py`, `tests/core/test_a2a.py` y `tests/core/test_context_compaction.py`.

### P2.2 Integración en CI
- `addopts` ignora `tests/integration` y CI usa keys falsas: la suite es verde pero ciega. Ejecutar integración en un job separado con mocks/servidores locales (`server/test_hook_types.py`, `scripts/local_mcp_server.py`).

### P2.3 Arreglar Docker y Compose
- `Dockerfile` usa `curl | bash` sin pin y un PATH de `uv` incorrecto, corre como root; `.dockerignore` excluye `mcp_config.json`; `docker-compose.yml` monta el repo sin usuario no-root.

### P2.4 Logs y observabilidad seguros
- `app/core/logger.py` y `app/core/harness/hooks.py` guardan payloads completos sin redactar claves; el collector no usa lock; el flujo A2A no llega al fichero. Redactar, sincronizar y limitar el tamaño de logs.

### P2.5 Deuda técnica diversa
- Código muerto y duplicado (`app/core/llm/providers/openai_provider.py`, `app/core/logger.py`, `app/core/harness/context.py`, `app/core/harness/a2a/base.py`); coste repartido 50/50 (`app/core/harness/loop.py`); búsqueda FTS5 como frase exacta (`app/core/harness/memory/backends/sqlite.py`); backend vectorial sin umbral de distancia (`app/core/harness/memory/backends/vector.py`); `InMemoryRingStore` con `limit=0` devuelve todo; matchers de hooks con `*` tratados como regex (`app/core/harness/hooks.py`).
