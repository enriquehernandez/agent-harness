# Tareas Pendientes

> Inventario de funcionalidad pendiente. Las tareas en ejecución están en `tasks/actual.md`; las completadas, en `tasks/completadas.md`.
> La auditoría de los commits del 16–24 de noviembre de 2026 quedó cerrada; no quedan tareas sueltas de esa revisión.

## Hooks del Harness (estilo Claude Code)

> **Decisiones de diseño ya aprobadas por el usuario:**
> - Se implementa por fases; la fase 1 es la tarea actual (`tasks/actual.md`).
> - La activación es automática: los hooks se leen de la configuración al arrancar y se disparan solos cuando ocurre el evento. `/hooks` no es necesario para que funcionen; es solo un visor opcional de la fase 3.
> - Configuración en `.harness/hooks.json` (nueva property `settings.hooks_file`), con esquema parecido al de Claude Code (`hooks` → evento → `matcher` → `hooks[]`), para poder copiar ejemplos. No se usa `.claude/settings.json`.
> - Fase 1: solo `type: command` y observación. Fase 2: decisiones (ya están el `deny` de `PreToolUse` que bloquea borrados, el `block` de `Stop`/`PostToolUse` como feedback y el `additionalContext` temporal). Fase 3: tipos avanzados e interfaz.
> - Sin dependencias nuevas: `asyncio`, `subprocess` y `json` de la stdlib. Si hiciera falta alguna, preguntar antes de tocar `pyproject.toml`.
> - Seguridad: timeout con `settings.TOOL_TIMEOUT`, JSON por stdin sin interpolar en la shell, interruptor `disableAllHooks`, errores logueados con `logger` (nunca `print()`) y fail-open (un hook roto no rompe el loop).
> - Los subagentes A2A llevan `agent_name`/profundidad en el payload del evento para poder filtrar y evitar doble disparo.
> - Commits solo con aprobación explícita del usuario. No tocar `.agents/`.

- [ ] **Fase 3 — Tipos avanzados, matchers completos e interfaz `/hooks`.** Añadir `type: http` (POST del JSON del evento), `type: prompt` (una llamada LLM que devuelve `{"ok": true|false, "reason": ...}`) y `type: agent` (subagente con herramientas y timeout de 60 s). Ampliar los matchers a nombre de herramienta, regex (`mcp__.*`) y filtro `if` con sintaxis de reglas de permisos; combinar resultados de varios hooks con deny preferente y `additionalContext` concatenado. Añadir el comando `/hooks` a `AVAILABLE_COMMANDS` para listar, recargar la configuración sin reiniciar y mostrar errores, y hot-reload del archivo. **Consultar antes de tocar el diseño de la TUI** (regla de `AGENTS.md`). Tests con cobertura 100 % y documentación en `PRODUCT_BLUEPRINT`, `docs/herramientas.md` y `README.md`.
