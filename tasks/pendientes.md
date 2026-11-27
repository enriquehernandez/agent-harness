# Tareas Pendientes

> Inventario de funcionalidad pendiente. Las tareas en ejecución están en `tasks/actual.md`; las completadas, en `tasks/completadas.md`.
> La auditoría de los commits del 16–24 de noviembre de 2026 quedó cerrada. El inventario siguiente sale de la revisión completa del 27 de noviembre de 2026 y está ordenado por prioridad: **P0** (bloqueantes), **P1** (funcionales/estabilidad), **P2** (calidad y tooling).
> La Definition of Done (tests, cobertura, pasos en TUI y puerta de commit) está en `tasks/DEFINITION_OF_DONE.md`, con plantillas para pendiente, en curso y completada. Las tareas P0 ya traen `Prueba en TUI prevista`; el resto la añade al pasar a `tasks/actual.md`.

## P0 — Bloqueantes (seguridad e integridad de datos)

### P0.2 Aprobar exactamente el comando que se ejecuta
- **Problema:** `BashTool.run()` reescribe `command` *después* de la aprobación (`app/tools/shell.py:40-59`) e invoca `export_observations` sin permiso. La firma aprobada no coincide con lo ejecutado.
- **Criterio:** la tool no muta el comando aprobado; cualquier escritura derivada pasa por `PermissionGate`. Actualizar `tests/core/test_tools.py:238-260`, que hoy consagra el comportamiento.
- **Prueba en TUI prevista:** Pedir un comando con `capture_snapshot.py`, aprobarlo con «y» → el comando mostrado en F1 debe ser exactamente el aprobado; sin escritura de `observations.json` sin permiso.
- **DoD:** ⛔ pendiente — se completa al pasar a `tasks/actual.md` y cerrar en `tasks/completadas.md`.

### P0.3 Tratar las aprobaciones persistentes como texto literal
- **Problema:** `fnmatch(signature, allowed)` (`app/core/harness/permissions.py:84-95`) convierte comandos aprobados con `*`, `?` o `[...]` en patrones glob que autorizan otros comandos.
- **Criterio:** comparación exacta (o escape del patrón con `re.escape`). Test: aprobar `bash:grep *.log` no autoriza `bash:grep .env`.
- **Prueba en TUI prevista:** Aprobar `bash:grep *.log` con «a», reiniciar la TUI y pedir `grep .env` → debe volver a preguntar (hoy queda autorizado por el glob).
- **DoD:** ⛔ pendiente — se completa al pasar a `tasks/actual.md` y cerrar en `tasks/completadas.md`.

### P0.4 Sanear IDs de sesión y validar el historial cargado
- **Problema:** `session.py:11-13,92-97` construye rutas con el ID del usuario sin validar; `app/tui/app.py:108-119` inyecta como `system` mensajes de un JSON manipulado.
- **Criterio:** IDs rechazados si contienen `/`, `..` o son absolutos; `load()` filtra/desarma mensajes `system`; JSON corrupto no revienta `on_mount`. Tests para `/session load ../../mcp_config` y para un session file con `role: system`.
- **Prueba en TUI prevista:** `/session load ../../mcp_config` → rechazado sin tocar otros JSON; meter un mensaje `role: system` en una sesión, reiniciar la TUI → el system prompt no se sustituye.
- **DoD:** ⛔ pendiente — se completa al pasar a `tasks/actual.md` y cerrar en `tasks/completadas.md`.

### P0.5 No filtrar secretos a servidores MCP y fijar versiones
- **Problema:** `app/mcp/client.py:17-28` copia `os.environ` completo (API keys, Langfuse) en cada servidor; `mcp_config.json` usa `uvx`/`npx` sin versión fija.
- **Criterio:** allowlist explícita de variables por servidor, sin secretos por defecto; versiones pinnadas; test que compruebe que las claves no aparecen en `client.env`.
- **Prueba en TUI prevista:** Con MCP activo, `/tools` → las tools siguen funcionando; inspeccionar el proceso del servidor → sin API keys en su entorno; `/doctor` sin errores.
- **DoD:** ⛔ pendiente — se completa al pasar a `tasks/actual.md` y cerrar en `tasks/completadas.md`.

### P0.6 Restringir hooks `command`/`http` y aplicar sus denegaciones en la TUI
- **Problema:** `hooks.py:466-518` ejecuta shell y URLs arbitrarias de `.harness/hooks.json`; `app.py:491-494,622-625` descarta el `denied` de `UserPromptSubmit`.
- **Criterio:** validación/allowlist de URLs (mínimo: solo loopback) y comandos; un `denied` en `UserPromptSubmit` bloquea el prompt realmente. Usar `server/test_hook_types.py` como prueba manual (los cuatro tipos: `command`, `http`, `prompt`, `agent`).
- **Prueba en TUI prevista:** Ejecutar `uv run python server/test_hook_types.py`, `/hooks` → los cuatro tipos listados; el hook `http /deny` bloquea `bash:ls`; un `UserPromptSubmit` con deny impide enviar el prompt; F1 muestra el ciclo.
- **DoD:** ⛔ pendiente — se completa al pasar a `tasks/actual.md` y cerrar en `tasks/completadas.md`.

### P0.7 Evitar que los scripts destructivos toquen datos reales
- **Problema:** `scripts/verify_memory_backends.py:92-95,158-159` borra `.harness` y siempre termina con éxito; `scripts/check_pricing.py:61-65,135-138` elimina la caché si falla la descarga; `checks/tests.md:8` obliga a ejecutarlo.
- **Criterio:** los scripts usan directorios temporales, restauran backups en `finally` y devuelven código de salida no cero si fallan; quitar la instrucción obligatoria del checklist.
- **Prueba en TUI prevista:** N/A en TUI (scripts de diagnóstico): ejecutarlos contra un repo temporal → la memoria y la caché reales siguen intactas; `/doctor` y `/cost` sin errores.
- **DoD:** ⛔ pendiente — se completa al pasar a `tasks/actual.md` y cerrar en `tasks/completadas.md`.

### P0.8 Dejar de inflar la cobertura
- **Problema:** `pyproject.toml:67-79` excluye `except`, `continue`, `return` y `on_*/watch_*/compose`; `:57-59` silencia `RuntimeWarning`; `tests/integration` se ignora en `addopts`.
- **Criterio:** medir el manejo de errores y los handlers de TUI; aceptar que el porcentaje baje temporalmente y cubrirlo con tests de comportamiento; no silenciar `RuntimeWarning`.
- **Prueba en TUI prevista:** N/A en TUI (proceso): `uv run tom test` con las exclusiones reducidas → cobertura real sin `RuntimeWarning`; arrancar la TUI y `/doctor` sin errores.
- **DoD:** ⛔ pendiente — se completa al pasar a `tasks/actual.md` y cerrar en `tasks/completadas.md`.

### P0.9 Desacoplar la aprobación del modal: petición pendiente por sesión
- **Problema:** `PermissionGate.check()` hace `await self.ask_user(...)` en el mismo proceso (`permissions.py:161-165`). En background (`ask_user=None`) deniega sin poder preguntar y en A2A `parallel` (`parallel.py:63-64`) se apilan modales. OpenCode resuelve el `ask` como una `PermissionRequest(sessionID, requestID, resources, save)` y espera un `reply` externo `once|always|reject`.
- **Criterio:** las decisiones `ALLOW`/`DENY` se resuelven localmente sin modal; un `ASK` encola una petición con `sessionID` del subagente, `requestID`, firma/recursos y patrones propuestos, y el tool call espera la respuesta. La TUI puede listar y responder peticiones del hijo aunque el padre siga trabajando: `once` vale solo para esa petición, `always` guarda patrones literales (depende de P0.3) y nunca vence a un `deny` configurado, `reject` cierra esa y todas las pendientes de la misma sesión. Sin cliente (background/headless) la petición queda pendiente o se rechaza según política, nunca se auto-aprueba.
- **Dependencias:** P0.1 y P0.3; deja P1.7 como parche temporal del modal y es el paso previo para igualar el modelo de permisos de OpenCode.
- **Prueba en TUI prevista:** lanzar el reviewer/A2A `parallel` con una tool sin aprobar → el prompt aparece asociado al subagente (F1 muestra su `sessionID`); responder «y» → ejecuta solo esa llamada y la siguiente vuelve a preguntar; responder «a» → persiste y no pregunta tras reiniciar; responder «n» → se bloquean las peticiones pendientes de esa sesión y el subagente devuelve error; con background sin cliente → la tool queda pendiente o denegada, nunca ejecutada.
- **DoD:** ⛔ pendiente — se completa al pasar a `tasks/actual.md` y cerrar en `tasks/completadas.md`.

## P1 — Funcionales y estabilidad

### P1.1 Cerrar generadores de stream
- `app/tui/app.py:562-591` hace `break` sin `await stream_gen.aclose()`; el `finally` de `loop.py:344-350` (Langfuse + contexto de hooks) no se ejecuta. Añadir `aclose()` en todas las rutas de salida/error.

### P1.2 Liberar clientes LLM y subprocess
- `openai_provider.py:18-35` nunca cierra `AsyncOpenAI`; `shell.py:73-75` hace `kill()` sin `wait()`. Añadir `close()`/`aclose()` y `await process.wait()`.

### P1.3 Guardar la respuesta cuando un hook `Stop` bloquea
- `loop.py:152-153,283-284` inyecta el feedback pero no llama a `ctx.add_assistant(...)`; el modelo critics lo que no ve. Igualar a la rama del crítico (`:147-149`, `:276-278`).

### P1.4 Aislar el contexto de hooks entre loops concurrentes
- `hooks.py:296,399-400,591-595` usa un único `pending_context` global: dos loops A2A se roban el contexto. Sustituir por estado por sesión/`ContextVar`.

### P1.5 Robustecer el proveedor OpenAI-compatible
- `max_tokens` no se envía a la API pero sí se usa como ventana de contexto (`openai_provider.py:26,80-85,216-217`); `json.loads` sin guard (`:104,201`); deltas sin `index` descartados y posible `IndexError` (`:179-192`); IDs de tool call colisionantes (`:199`).

### P1.6 Crítico: parseo estricto y fail-closed
- `critic.py:39-44` acepta cualquier texto que contenga `APPROVED`, y un error del LLM cuenta como aprobación. Exigir respuesta exacta y tratar el error como "no aprobado" sin coste extra involuntario.

### P1.7 Modal de permisos: timeout y markup
- `app.py:354-361` usa `wait_for` sobre `push_screen_wait` con `shield`: el modal queda huérfano. Interpolar argumentos sin escapar en `app.py:339-346` / `modals/permission.py:49-58` permite `MarkupError` y falsear el texto. Escapar markup, cerrar la pantalla al caducar y serializar los modales con un `lock`. Es un parche temporal: la solución de fondo para background/paralelo es **P0.9**.

### P1.8 Consistencia de comandos TUI
- `/provider` no actualiza pricing ni LLMs del crítico/A2A (`commands.py:485-514`, `app.py:194-245`); `/compact` no restaura la estrategia con `try/finally` (`commands.py:552-572`); `/session load` no limpia el chat y `/session delete` resucita la sesión (`commands.py:755-792`); F1 y `/debug` desincronizados (`app.py:373-382`).

### P1.9 MCP: sesión zombie y reintento no idempotente
- `client.py:40-55` marca `self.session` antes de `initialize()`; `client.py:161-172` vuelve a ejecutar la tool tras cualquier error, duplicando efectos. Cerrar el `exit_stack` en error y no reintentar escrituras.

## P2 — Calidad, tests y tooling

### P2.1 Sanear la suite de tests
- 15 definiciones duplicadas (solo se ejecuta la última), tests sin `assert` y tests que fuerzan números de línea. Ver `tests/tui/test_app.py`, `tests/core/test_a2a.py` y `tests/core/test_context_compaction.py`.

### P2.2 Integración en CI
- `addopts` ignora `tests/integration` y CI usa keys falsas: la suite es verde pero ciega. Ejecutar integración en un job separado con mocks/servidores locales (`server/test_hook_types.py`, `scripts/local_mcp_server.py`).

### P2.3 Arreglar Docker y Compose
- `Dockerfile:8,14` usa `curl | bash` sin pin, `:15` pone un PATH de `uv` incorrecto, corre como root; `.dockerignore` excluye `mcp_config.json`; `docker-compose.yml` monta el repo sin usuario no-root.

### P2.4 Logs y observabilidad seguros
- `logger.py:68-125` y `hooks.py:406-418` guardan payloads completos sin redactar claves; el collector no usa lock; el flujo A2A no llega al fichero. Redactar, sincronizar y limitar el tamaño de logs.

### P2.5 Deuda técnica diversa
- Código muerto y duplicado (`openai_provider.py:65-77`, `logger.py:40`, `context.py:76-79`, `a2a/base.py:74-77`); coste repartido 50/50 (`loop.py:367-370`); búsqueda FTS5 como frase exacta (`memory/backends/sqlite.py:32-36`); backend vectorial sin umbral de distancia (`vector.py:89-106`); `InMemoryRingStore` con `limit=0` devuelve todo; matchers de hooks con `*` tratados como regex (`hooks.py:224-232`).
