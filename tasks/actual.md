# Tarea Actual

- **Objetivo:** Refactorizar el proyecto para usar la estructura de contexto en texto plano (AGENTS.md, docs/, tasks/, checks/).
- **Estado:** Completada. `app.py` ya carga `AGENTS.md` y `tasks/actual.md` al inicializar el `ContextManager` y usa `Path.exists()`.
- **Notas:** Este archivo es contexto informativo; no representa una tarea pendiente salvo indicación explícita del usuario.