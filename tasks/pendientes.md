# Tareas Pendientes

> Inventario de funcionalidad pendiente. Las tareas en ejecución están en `tasks/actual.md`; las completadas, en `tasks/completadas.md`.
> La auditoría de los commits del 16–24 de noviembre de 2026 quedó cerrada; no quedan tareas sueltas de esa revisión.

## Hooks del Harness (estilo Claude Code)

> **Decisiones de diseño ya aprobadas por el usuario:**
> - Se implementó por fases; las cuatro fases están completadas (`tasks/completadas.md`).
> - La activación es automática: los hooks se leen de la configuración al arrancar y se disparan solos cuando ocurre el evento. `/hooks` no es necesario para que funcionen; es solo un visor opcional de la fase 3.
> - Configuración en `.harness/hooks.json` (nueva property `settings.hooks_file`), con esquema parecido al de Claude Code (`hooks` → evento → `matcher` → `hooks[]`), para poder copiar ejemplos. No se usa `.claude/settings.json`.
> - Fase 1: `type: command` y observación. Fase 2: decisiones (`deny` de `PreToolUse`, `block` de `Stop`/`PostToolUse` y `additionalContext` temporal). Fase 3: tipos avanzados, matchers completos e interfaz `/hooks`.
> - Sin dependencias nuevas: `asyncio`, `subprocess` y `json` de la stdlib. Si hiciera falta alguna, preguntar antes de tocar `pyproject.toml`.
> - Seguridad: timeout con `settings.TOOL_TIMEOUT`, JSON por stdin sin interpolar en la shell, interruptor `disableAllHooks`, errores logueados con `logger` (nunca `print()`) y fail-open (un hook roto no rompe el loop).
> - Los subagentes A2A llevan `agent_name`/profundidad en el payload del evento para poder filtrar y evitar doble disparo.
> - Commits solo con aprobación explícita del usuario. No tocar `.agents/`.

No quedan tareas pendientes de hooks: las cuatro fases están en `tasks/completadas.md`.
