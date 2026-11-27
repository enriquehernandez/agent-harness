# Tareas Pendientes

> Inventario de funcionalidad pendiente. Las tareas en ejecución están en `tasks/actual.md`; las completadas, en `tasks/completadas.md`.
> La auditoría de los commits del 16–24 de noviembre de 2026 quedó cerrada. El inventario siguiente sale de la revisión completa del 27 de noviembre de 2026 y está ordenado por prioridad: **P0** (bloqueantes), **P1** (funcionales/estabilidad), **P2** (calidad y tooling).
> La Definition of Done (tests, cobertura, pasos en TUI y puerta de commit) está en `tasks/DEFINITION_OF_DONE.md`, con plantillas para pendiente, en curso y completada. Las tareas P0 ya traen `Prueba en TUI prevista`; el resto la añade al pasar a `tasks/actual.md`.
> Las referencias son a archivos y símbolos, nunca a números de línea: el código cambia y esas referencias se quedan obsoletas.

## P0 — Bloqueantes (seguridad e integridad de datos)

Sin tareas pendientes.

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
