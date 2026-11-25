# Tareas Pendientes

> Inventario de funcionalidad pendiente. Las tareas en ejecución están en `tasks/actual.md`; las completadas, en `tasks/completadas.md`.
> La auditoría de los commits del 16–24 de noviembre de 2026 quedó cerrada; no quedan tareas sueltas de esa revisión.

## Hooks del Harness (estilo Claude Code)

> **Decisiones de diseño ya aprobadas por el usuario:**
> - Se implementa por fases; la fase 1 es la tarea actual (`tasks/actual.md`).
> - La activación es automática: los hooks se leen de la configuración al arrancar y se disparan solos cuando ocurre el evento. `/hooks` no es necesario para que funcionen; es solo un visor opcional de la fase 3.
> - Configuración en `.harness/hooks.json` (nueva property `settings.hooks_file`), con esquema parecido al de Claude Code (`hooks` → evento → `matcher` → `hooks[]`), para poder copiar ejemplos. No se usa `.claude/settings.json`.
> - Fase 1: solo `type: command` y observación. Fase 2: decisiones (ya están el `deny` de `PreToolUse` que bloquea borrados y el `block` de `Stop`/`PostToolUse` como feedback). Fase 3: tipos avanzados e interfaz.
> - Sin dependencias nuevas: `asyncio`, `subprocess` y `json` de la stdlib. Si hiciera falta alguna, preguntar antes de tocar `pyproject.toml`.
> - Seguridad: timeout con `settings.TOOL_TIMEOUT`, JSON por stdin sin interpolar en la shell, interruptor `disableAllHooks`, errores logueados con `logger` (nunca `print()`) y fail-open (un hook roto no rompe el loop).
> - Los subagentes A2A llevan `agent_name`/profundidad en el payload del evento para poder filtrar y evitar doble disparo.
> - Commits solo con aprobación explícita del usuario. No tocar `.agents/`.

- [ ] **Fase 2 (resto) — `additionalContext` temporal.** Ya implementado: `HookOutcome` entiende `deny` por JSON o exit 2 con motivo en stderr y gana sobre los permisos en `AgentLoop._execute_tool()` (aviso `hook_denied` en la TUI; `.harness/hooks/no_delete.py` bloquea borrados por `bash`); el `block` de `Stop`/`PostToolUse` se convierte en feedback persistente en el contexto y, en `Stop`, fuerza otra iteración. Pendiente: añadir `additionalContext` como mensaje temporal de un solo uso en `UserPromptSubmit`, `PreToolUse` y `PostToolUse` (inyectar antes de la llamada al LLM y retirar al terminar, reutilizando `_begin_pending_mode()`/`_end_pending_mode()`; nunca en el system prompt ni en la sesión), con concatenación entre hooks. Tests de que el contexto temporal no queda en el historial.

- [ ] **Fase 3 — Tipos avanzados, matchers completos e interfaz `/hooks`.** Añadir `type: http` (POST del JSON del evento), `type: prompt` (una llamada LLM que devuelve `{"ok": true|false, "reason": ...}`) y `type: agent` (subagente con herramientas y timeout de 60 s). Ampliar los matchers a nombre de herramienta, regex (`mcp__.*`) y filtro `if` con sintaxis de reglas de permisos; combinar resultados de varios hooks con deny preferente y `additionalContext` concatenado. Añadir el comando `/hooks` a `AVAILABLE_COMMANDS` para listar, recargar la configuración sin reiniciar y mostrar errores, y hot-reload del archivo. **Consultar antes de tocar el diseño de la TUI** (regla de `AGENTS.md`). Tests con cobertura 100 % y documentación en `PRODUCT_BLUEPRINT`, `docs/herramientas.md` y `README.md`.
