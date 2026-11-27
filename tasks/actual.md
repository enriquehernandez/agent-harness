# Tarea Actual

No hay tareas en ejecución. El inventario priorizado está en `tasks/pendientes.md` y las tareas cerradas, en `tasks/completadas.md`.

## Plantilla para una tarea en curso

Al empezar una tarea de `tasks/pendientes.md`, copiar su ID y su objetivo aquí y mantener el registro al día. Es la parte "en curso" del ciclo descrito en `tasks/DEFINITION_OF_DONE.md`:

```markdown
## P0.N <Título>
- **Objetivo:** copiado de `tasks/pendientes.md`.
- **Estado:** En curso. Qué se está haciendo.
- **Avance:** [x] test de regresión escrito · [ ] código · [ ] verificación TUI.
- **Pruebas ejecutadas:** comandos y resultado real (`uv run tom test`, integración).
- **Prueba en TUI:** pasos ya ejecutados y resultado observado (o «pendiente»).
- **Bloqueos:** qué impide avanzar, si hay.
- **Siguiente paso:** acción concreta.
```

Al terminar: completar el DoD, mover la entrada a `tasks/completadas.md` con su `Prueba en TUI` ejecutada, quitarla de `tasks/pendientes.md` y dejar esta sección sin tareas activas. No se propone commit sin aprobación explícita.

## Notas

- Cómo cerrar una tarea: `tasks/DEFINITION_OF_DONE.md`.
- Tareas completadas: `tasks/completadas.md`.
- Inventario priorizado: `tasks/pendientes.md`.
