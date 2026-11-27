# Permission Gate (Seguridad)

Darle acceso a `bash` a un LLM es peligroso. El `PermissionGate` es la capa de seguridad entre la "mente" del LLM y el "sistema operativo".

## Mecánica de Funcionamiento

1. **Evaluación de Política**: Cada herramienta tiene un nivel por defecto (`ALLOW`, `ASK`, `DENY`).
2. **Intercepción**: Cuando el LLM pide usar `bash`, el `AgentLoop` pausa la ejecución y consulta al `PermissionGate`.
3. **Cola de peticiones**: Si la política es `ASK`, `PermissionBroker.request()` encola una petición con `requestID`, `sessionID`, firma, argumentos y diff, y la tool call espera en un `asyncio.Event`. La TUI avisa por chat, lista las peticiones con F1 y responde con `/permissions reply <requestID> once|always|reject`; `/permissions pending` muestra la cola. No se abre ningún modal: delegar o responder no cancela al agente padre. El modal directo sigue disponible solo para llamadores antiguos que inyectan `ask_user`.

```text
🔐 Permiso pendiente `req-8af2b66a` · sesión `a2a:analyst` · `bash` → `bash:ls`.
   Responde con `/permissions reply req-8af2b66a once|always|reject`.
```

4. **Persistencia (no solo memoria de sesión)**: Si el usuario responde `always` (`a`), `check()` añade la firma a `session_allowed` y la guarda en `.harness/permissions.json`. Al crear un `PermissionGate` en futuras sesiones, `_load_persisted_permissions()` lee ese archivo y autoriza **solo las firmas textuales guardadas**, por lo que no se vuelve a preguntar para esa misma firma. La comparación es exacta (`signature in session_allowed`): `*`, `?` y `[...]` son caracteres literales, así que aprobar `bash:grep *.log` no autoriza `bash:grep secrets.log` ni `bash:grep .env`. `once` solo autoriza esa llamada: no persiste. Un `deny` configurado se evalúa antes que las aprobaciones y también gana si se activa mientras la petición está esperando. `/reload permissions` recarga el archivo descartando aprobaciones solo en memoria.
5. **Gates para subagentes**: `child(allow=..., session_id=...)` crea un gate que comparte el broker, `session_allowed` y `persist_file` con el padre, copia las `policies` y admite marcar tools concretas como `Decision.ALLOW`. **Ningún subagente usa ese argumento**: `DelegateTool`, los hooks `agent` y las estrategias A2A derivan gates con su propia sesión (`delegate:<nombre>`, `hook:agent`, `a2a:<agente>`), de modo que `bash`/`write_file` siguen en `ASK` salvo aprobación explícita. Una aprobación en cualquier subagente vale también para el padre y sus hermanos; un `reject` cierra solo las peticiones pendientes de esa sesión.
6. **Inyección de Errores**: Si el usuario deniega (`reject`/`n`), el Harness inyecta un mensaje `ToolMessage` diciendo: "`ERROR: El usuario denegó el permiso`". Así el LLM sabe que no debe insistir y busca otra alternativa.
7. **Sin cliente**: En background o headless el broker no tiene suscriptores: con la política por defecto la petición se deniega; con `unattended="pending"` queda en cola esperando una respuesta externa. Nunca se aprueba sola.
