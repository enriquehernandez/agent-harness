# Tarea Actual

- **Objetivo:** Refactorizar el proyecto para usar la estructura de contexto en texto plano (`AGENTS.md`, `docs/`, `tasks/`, `checks/`).
- **Estado:** Completada en el arranque del contexto: `app/tui/app.py` lee `AGENTS.md` y `tasks/actual.md` y añade el `preamble()` de la memoria al System Prompt (`[Long-term memory]`). `docs/` y `checks/` **no** se leen ni se inyectan: el texto del prompt solo los menciona como «everything else below … is BACKGROUND CONTEXT»; el agente debe consultarlos con herramientas cuando los necesita.
- **Notas:** Este archivo es contexto informativo; no representa una tarea pendiente salvo indicación explícita del usuario. El inventario de funcionalidad documentada como ausente está en `tasks/pendientes.md`.
