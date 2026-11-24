# Permission Gate (Seguridad)

Darle acceso a `bash` a un LLM es peligroso. El `PermissionGate` es la capa de seguridad entre la "mente" del LLM y el "sistema operativo".

## Mecánica de Funcionamiento

1. **Evaluación de Política**: Cada herramienta tiene un nivel por defecto (`ALLOW`, `ASK`, `DENY`).
2. **Intercepción**: Cuando el LLM pide usar `bash`, el `AgentLoop` pausa la ejecución y consulta al `PermissionGate`.
3. **Interacción Humana**: Si la política es `ASK`, el gate usa un `ModalScreen` de **Textual** (no `prompt_toolkit`) para mostrar un panel con los argumentos y el diff. El usuario responde con `y`/`n`/`a` desde la TUI.

```text
🛠️  El agente quiere usar: bash
╭───────────────────────────────────────────────╮
│ command: rm -rf ./venv                        │
╰───────────────────────────────────────────────╯
¿Permitir ejecución? [y/n/a] (n): 
```

4. **Persistencia (no solo memoria de sesión)**: Si el usuario responde `a` (always), `check()` añade la firma a `session_allowed` y la guarda en `.harness/permissions.json`. Al crear un `PermissionGate` en futuras sesiones, `_load_persisted_permissions()` lee ese archivo y aplica los patrones guardados, por lo que no se vuelve a preguntar. `y` solo autoriza esa llamada: no persiste. `/reload permissions` recarga el archivo descartando aprobaciones solo en memoria.
5. **Gates para subagentes**: `child(allow=...)` crea un gate que comparte `session_allowed`, `ask_user` y `persist_file` con el padre, copia las `policies` y puede marcar tools concretas como `Decision.ALLOW`. Una aprobación en cualquier subagente vale también para el padre y sus hermanos.
6. **Inyección de Errores**: Si el usuario deniega (`n`), el Harness inyecta un mensaje `ToolMessage` diciendo: "`ERROR: El usuario denegó el permiso`". Así el LLM sabe que no debe insistir y busca otra alternativa.