# Tareas Completadas

## Refactorización de contexto en texto plano

- **Objetivo:** Refactorizar el proyecto para usar la estructura de contexto en texto plano (`AGENTS.md`, `docs/`, `tasks/`, `checks/`).
- **Estado:** Completada en el arranque del contexto: `app/tui/app.py` lee `AGENTS.md` y `tasks/actual.md` y añade el `preamble()` de la memoria al System Prompt (`[Long-term memory]`). `docs/` y `checks/` **no** se leen ni se inyectan: el texto del prompt solo los menciona como «everything else below … is BACKGROUND CONTEXT»; el agente debe consultarlos con herramientas cuando los necesita.

## Ctrl+L limpia también el `ContextManager`

- **Objetivo:** Igualar `Ctrl+L` a `/clear`: vaciar el historial conservando el system prompt.
- **Estado:** Completada. `action_clear_chat()` (`app/tui/app.py`) llama a `self.ctx.clear()` cuando hay contexto, además de limpiar los widgets. Cubierto por `tests/tui/test_app.py::test_app_clear_chat_clears_context`.
