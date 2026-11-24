# Tareas Pendientes

> Inventario de funcionalidad pendiente. Las tareas en ejecución están en `tasks/actual.md`; las completadas, en `tasks/completadas.md`.
> La auditoría de los commits del 16–24 de noviembre de 2026 quedó cerrada; no quedan tareas sueltas de esa revisión.

## Hooks del Harness (estilo Claude Code)

> **Decisiones de diseño ya aprobadas por el usuario:**
> - Se implementa por fases; la fase 1 es la tarea actual (`tasks/actual.md`).
> - La activación es automática: los hooks se leen de la configuración al arrancar y se disparan solos cuando ocurre el evento. `/hooks` no es necesario para que funcionen; es solo un visor opcional de la fase 3.
> - Configuración en `.harness/hooks.json` (nueva property `settings.hooks_file`), con esquema parecido al de Claude Code (`hooks` → evento → `matcher` → `hooks[]`), para poder copiar ejemplos. No se usa `.claude/settings.json`.
> - Fase 1: solo `type: command` y solo observación (sin bloquear ni inyectar contexto). Fase 2: decisiones. Fase 3: tipos avanzados e interfaz.
> - Sin dependencias nuevas: `asyncio`, `subprocess` y `json` de la stdlib. Si hiciera falta alguna, preguntar antes de tocar `pyproject.toml`.
> - Seguridad: timeout con `settings.TOOL_TIMEOUT`, JSON por stdin sin interpolar en la shell, interruptor `disableAllHooks`, errores logueados con `logger` (nunca `print()`) y fail-open (un hook roto no rompe el loop).
> - Los subagentes A2A llevan `agent_name`/profundidad en el payload del evento para poder filtrar y evitar doble disparo.
> - Commits solo con aprobación explícita del usuario. No tocar `.agents/`.

- [ ] **Fase 2 — Control de decisión de los hooks.** `PreToolUse` podrá devolver `deny` (JSON con `hookSpecificOutput.permissionDecision: deny` o exit 2 con el motivo en stderr) y `Stop`/`PostToolUse` podrán devolver `decision: block` con feedback para el agente. Integrarlo con `PermissionGate.check()` y `AgentLoop._execute_tool()` con prioridad deny > ask > allow (el deny gana, como en Claude Code). `UserPromptSubmit`, `PreToolUse` y `PostToolUse` podrán aportar `additionalContext` como mensaje temporal de un solo uso: se inyecta antes de la llamada al LLM y se retira al terminar, reutilizando el patrón de los códigos de respuesta (`_begin_pending_mode()`/`_end_pending_mode()`); nunca se escribe en el system prompt ni se persiste en la sesión. Tests de todas las ramas de decisión, del fail-open y de que el contexto temporal no queda en el historial; actualizar `PRODUCT_BLUEPRINT/02_COMPONENTS/11_hooks.md`, `docs/herramientas.md` y `README.md`.

- [ ] **Fase 3 — Tipos avanzados, matchers completos e interfaz `/hooks`.** Añadir `type: http` (POST del JSON del evento), `type: prompt` (una llamada LLM que devuelve `{"ok": true|false, "reason": ...}`) y `type: agent` (subagente con herramientas y timeout de 60 s). Ampliar los matchers a nombre de herramienta, regex (`mcp__.*`) y filtro `if` con sintaxis de reglas de permisos; combinar resultados de varios hooks con deny preferente y `additionalContext` concatenado. Añadir el comando `/hooks` a `AVAILABLE_COMMANDS` para listar, recargar la configuración sin reiniciar y mostrar errores, y hot-reload del archivo. **Consultar antes de tocar el diseño de la TUI** (regla de `AGENTS.md`). Tests con cobertura 100 % y documentación en `PRODUCT_BLUEPRINT`, `docs/herramientas.md` y `README.md`.
