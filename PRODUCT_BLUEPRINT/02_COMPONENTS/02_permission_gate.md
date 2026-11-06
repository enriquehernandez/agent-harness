# Permission Gate (Seguridad)

Darle acceso a `bash` a un LLM es peligroso. El `PermissionGate` es la capa de seguridad entre la "mente" del LLM y el "sistema operativo".

## Mecánica de Funcionamiento

1. **Evaluación de Política**: Cada herramienta tiene un nivel por defecto (`ALLOW`, `ASK`, `DENY`).
2. **Intercepción**: Cuando el LLM pide usar `bash`, el `AgentLoop` pausa la ejecución y consulta al `PermissionGate`.
3. **Interacción Humana**: Si la política es `ASK`, el gate usa `prompt_toolkit` y `rich` para mostrar un panel en la terminal:

```text
🛠️  El agente quiere usar: bash
╭───────────────────────────────────────────────╮
│ command: rm -rf ./venv                        │
╰───────────────────────────────────────────────╯
¿Permitir ejecución? [y/n/a] (n): 
```

4. **Memoria de Sesión**: Si el usuario responde `a` (always), el gate guarda la herramienta en un `set()` llamado `session_allowed`. Durante esa ejecución, no se volverá a preguntar.
5. **Inyección de Errores**: Si el usuario deniega (`n`), el Harness inyecta un mensaje `ToolMessage` diciendo: "`ERROR: El usuario denegó el permiso`". Así el LLM sabe que no debe insistir y busca otra alternativa.