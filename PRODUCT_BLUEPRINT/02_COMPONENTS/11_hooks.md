# Hooks del ciclo de vida

Los hooks permiten ejecutar comandos definidos por el usuario **automáticamente** en puntos concretos del ciclo de vida del harness, sin que el agente tenga que elegirlos y sin que el usuario escriba ningún comando. Son el equivalente, en versión reducida, de los hooks de Claude Code.

La configuración vive en `.harness/hooks.json` (`settings.hooks_file`) y se carga al arrancar:

```json
{
  "disableAllHooks": false,
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "bash",
        "hooks": [
          { "type": "command", "command": "python3 .harness/hooks/no_delete.py" }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "edit_file|write_file",
        "hooks": [
          { "type": "command", "command": "python3 .harness/hooks/audit.py" }
        ]
      }
    ]
  }
}
```

- `matcher` admite alternativas separadas por `|`, nombres exactos y regex estilo `mcp__.*`; solo filtra `PreToolUse`/`PostToolUse` por nombre de herramienta. Vacío significa «todas». En el resto de eventos se ignora.
- Se aceptan cuatro tipos de handler: `command` (por defecto), `http`, `prompt` y `agent`.
- Cada handler puede llevar `if`: una firma `herramienta:detalle` con comodines `fnmatch` (`bash:rm *`, `edit_file:src/*.py`). Solo se aplica en eventos de herramienta. Ojo: los **permisos** no usan comodines: una aprobación guardada se compara como texto literal.
- `disableAllHooks: true` desactiva todos los hooks sin borrar la configuración.
- Los scripts de hooks van en `.harness/hooks/` y se versionan; el log que generan (`audit.log`) queda ignorado.

## Arquitectura

`app/core/harness/hooks.py` contiene cuatro piezas:

- `HookEvent`: payload con `hook_event_name`, `session_id`, `cwd`, `prompt`, `tool_name`, `tool_input`, `success`, `trigger`, `agent_name` y `agent_depth`. Los campos vacíos se omiten al serializar.
- `HookOutcome`: resultado del evento (`denied`, `reason`, `additional_context`). `from_process()` parsea la salida del comando (incluido exit 2) y `from_text()` la de HTTP/prompt/agent; acepta `permissionDecision`, `decision: block`, `ok: false` y `additionalContext`.
- `HookRegistry`: carga y filtra los handlers por evento, nombre de herramienta y firma `if`, siguiendo el Registry Pattern.
- `HookManager`: lee el JSON, lanza cada handler y aplica la primera decisión de bloqueo. En `command` usa `asyncio.create_subprocess_shell()` y pasa el evento por **stdin** como JSON; el comando sale de la configuración (archivo de confianza) y los datos del evento nunca se interpolan en la cadena. Controla `settings.TOOL_TIMEOUT` (mata el proceso si expira), guarda el `additionalContext` pendiente hasta `drain_context()`, registra errores por handler para `/hooks` y recarga la config automáticamente si cambia su mtime (`reload_if_changed()`).

`emit_hook(event)` es la única fachada pública; el módulo mantiene un `hook_manager` compartido.

## Puntos de disparo

| Evento | Dónde se dispara |
| :--- | :--- |
| `UserPromptSubmit` | Envío de prompts de la TUI (`_stream_user_message()` y rama de imágenes de `on_input_submitted()`) y en `AgentLoop.run()` para el modo headless |
| `PreToolUse` / `PostToolUse` | `AgentLoop._execute_tool()`, antes de permisos y al terminar (éxito, denegación, bloqueo por hook, tool no encontrada o fallo) |
| `PreCompact` / `PostCompact` | `ContextManager.maybe_compact()` (`trigger: auto`) y `force_compact()` (`trigger: manual`) |
| `Stop` | Final de `AgentLoop.run()` y de `AgentLoop.stream()` (respuesta final o máximo de iteraciones) |
| `StopFailure` | Ramas de timeout y excepción de `AgentLoop.stream()` |

Los eventos de subagentes A2A incluyen `agent_name`/`agent_depth` para poder filtrarlos.

## Decisiones: bloqueo de herramientas

Un handler `command` puede impedir la ejecución de la herramienta en dos formatos compatibles con Claude Code:

1. Terminar con **código 2** y escribir el motivo en `stderr` (si stderr está vacío se usa un motivo genérico).
2. Escribir en `stdout` un JSON con `hookSpecificOutput.permissionDecision: "deny"` y `hookSpecificOutput.permissionDecisionReason`. También se reconoce el formato genérico `decision: "block"` con `reason`, que se usa como feedback en `Stop`/`PostToolUse` (ver más abajo).

`HookManager.emit()` ejecuta los hooks en orden (salvo que se pida `parallel=True`) y devuelve el **primer deny** en orden de configuración; en modo serie ese deny corta la cadena. `AgentLoop._execute_tool()` consulta el resultado **antes de `PermissionGate.check()`**, de modo que el deny prevalece sobre `allow`: no llama a la herramienta, escribe el motivo en el resultado de la tool y marca `last_hook_denial`. En `stream()`, ese estado produce el evento `AgentEvent(type="hook_denied", data={"tool": ..., "message": ...})`; `stream_to_chat()` lo muestra como `🚫 **Bloqueado por un hook:** ...` sin interrumpir el turno.

### Guardia `no_delete.py`

`.harness/hooks/no_delete.py` es un hook `PreToolUse` con matcher `bash`. Lee el evento por stdin y, si `tool_input.command` contiene `rm`, `rmdir`, `unlink`, `shred`, `git rm`, `find ... -delete`, `os.remove`, `os.unlink`, `Path(...).unlink()` o `shutil.rmtree()`, devuelve el JSON `deny` con el comando bloqueado en el motivo. El análisis es conservador: ante la duda, bloquea. Las órdenes sin borrado no escriben nada y la herramienta continúa.

### Registro compartido `audit.py`

`.harness/hooks/audit.py` es tanto el hook `PostToolUse` que registra `edit_file`/`write_file` como el módulo de registro compartido: expone `log_event(event)` y escribe siempre en `<cwd>/.harness/hooks/audit.log` con el formato:

```text
2026-11-24T23:28:12+00:00 tool=bash success=False command=rm -f archivo.txt
2026-11-24T23:29:01+00:00 tool=edit_file success=True path=app/tui/app.py
```

`no_delete.py` importa `log_event()` y registra el bloqueo **en el momento de decidirlo**, antes de devolver el `deny`. Por eso no hace falta un segundo hook `PostToolUse` con matcher `bash` y no hay entradas duplicadas. Para `bash` se guarda el comando; para el resto de herramientas, la ruta. Los saltos de línea del comando se escapan para mantener una entrada por línea.

## Fail-open y límites

- Un JSON de configuración inválido, un comando que no existe, un código de salida distinto de cero (salvo el 2 con motivo), un stdout vacío o no parseable y un timeout solo generan `logger.warning` y permiten la acción.
- La compactación y el Permission Gate siguen funcionando igual: los hooks son aditivos.

### Feedback de `Stop` y `PostToolUse`

Un hook `Stop` o `PostToolUse` que devuelve `decision: "block"` (o cualquier `deny`) ya no se ignora: `AgentLoop._apply_hook_feedback()` convierte el motivo en un mensaje `[SISTEMA - FEEDBACK DE HOOK]: ...` añadido al contexto antes de la siguiente llamada al LLM.

- En `PostToolUse`, la herramienta ya se ejecutó: el mensaje se añade después del resultado de la tool para que el agente pueda corregirlo en el siguiente paso.
- En `Stop`, el bloqueo impide cerrar el turno: el loop añade el feedback y vuelve a iterar (respetando `max_iterations`). Si ya se agotaron las iteraciones, el feedback queda registrado y se devuelve el resultado habitual.
- Si el hook no aporta motivo, se usa un texto genérico. El mensaje se conserva en el historial: es feedback, no un contexto temporal.

### Contexto adicional temporal (`additionalContext`)

Un hook puede entregar información extra al LLM sin tocar el system prompt ni persistirla en la sesión. Se lee de `hookSpecificOutput.additionalContext` (o de `additionalContext` en la raíz) al parsear la salida:

```json
{ "hookSpecificOutput": { "additionalContext": "usa python en vez de bash" } }
```

Solo se guarda en los eventos `UserPromptSubmit`, `PreToolUse` y `PostToolUse`. `HookManager.emit()` concatena en orden (con `\n`) los aportes de todos los hooks ejecutados y los deja en `pending_context`; un `deny` no descarta el contexto recogido hasta ese momento. `drain_context()` lo entrega una sola vez y lo limpia.

`AgentLoop._inject_hook_context()` lo vierte en `ctx.append_hook_context()` justo antes de cada llamada al LLM: se crea un único mensaje `user` con el prefijo `[SISTEMA - CONTEXTO ADICIONAL DE HOOK]: ...` y las entregas posteriores se suman a ese mismo mensaje. Al terminar el turno, `_finish_hook_context()` lo retira por identidad —el mismo patrón que `_begin_pending_mode()`/`_end_pending_mode()` de la TUI— y descarta lo que no llegó a usarse. Así, el historial guardado no contiene el mensaje temporal.

A diferencia del feedback, este contexto **no se conserva**: es de un solo uso por turno y nunca entra en el system prompt ni en la sesión.

### Tipos avanzados de handler

| Tipo | Configuración | Comportamiento |
| :--- | :--- | :--- |
| `command` | `command` | Shell con el evento por stdin; `settings.TOOL_TIMEOUT` |
| `http` | `url`, `timeout` opcional | `POST` JSON con `httpx.AsyncClient`; la ruta no tiene semántica, solo el JSON de respuesta (ver abajo); un `>= 400` se registra como error y se ignora |
| `prompt` | `prompt`, `provider`/`model` opcionales | Una llamada LLM con el evento; JSON con `ok: false` bloquea y la respuesta en texto pasa a `additionalContext` |
| `agent` | `prompt`, `tools`, `timeout` opcionales | `DelegateTool` con permisos hijos y timeout de 60 s por defecto; `tools` **no concede permisos** (no se pasa como `allow` al gate) y la respuesta se parsea igual que `prompt` |

Los tipos `prompt` y `agent` reutilizan el LLM inyectado en `HookManager` (tests) o construyen uno desde `provider`/`model` y `settings.LLM_PROVIDER`. El contexto variable `_hook_depth` impide que los eventos del subagente vuelvan a disparar hooks ni a drenar el `additionalContext` del turno padre.

### Contrato de respuesta del hook `http`

El harness envía el `HookEvent` completo como JSON en el cuerpo del `POST`. **La ruta es solo una etiqueta del servidor**: `/context`, `/deny` o cualquier otra no activan comportamientos especiales en el harness. Lo que decide el efecto es el JSON devuelto con `status < 400`:

| Respuesta | Efecto |
| :--- | :--- |
| `{"additionalContext": "..."}` | Se concatena con los demás aportes y se inyecta como contexto temporal (ver más arriba). |
| `{"decision": "block", "reason": "..."}` | `denied=True` con ese motivo. |
| `{"hookSpecificOutput": {"permissionDecision": "deny", "permissionDecisionReason": "..."}}` o `{"ok": false, "reason": "..."}` | También `denied=True` (formatos Claude Code y hooks `prompt`/`agent`). |
| Texto plano o JSON no parseable | Se ignora: `_launch_http()` llama a `from_text()` sin `plain_is_context=True`, a diferencia de `prompt`/`agent`. |
| `status >= 400` | `logger.warning`, error registrado por handler y `HookOutcome()` vacío (fail-open): **no** es un deny. |

El deny es decisivo en `PreToolUse`/`PostToolUse`: gana sobre los permisos y la tool no se ejecuta. En `UserPromptSubmit` la TUI ignora el `denied` del outcome; ahí solo tiene efecto el `additionalContext`. En `Stop`/`PostToolUse`, un deny se convierte en feedback para el modelo (ver más arriba).

### Timeouts del tipo `agent`

`agent` lanza un `DelegateTool` real con un `AgentLoop` sobre el LLM configurado; si el handler no lleva `provider`, hereda `settings.LLM_PROVIDER` (en el entorno actual, `OPENROUTER`). El timeout por defecto es `AGENT_HOOK_TIMEOUT = 60` y se puede fijar con `timeout` en el handler. Una llamada remota no es instantánea: en una ejecución real del 25 de noviembre de 2026 el mismo hook que fallaba con `timeout: 1` y con `timeout: 10` terminó correctamente en **17,51 s** con `timeout: 60`. Por eso un timeout corto agota siempre y no indica un problema de configuración. El error se registra con tipo y límite (`TimeoutError: superó 1s`), tanto en el warning como en el campo `error` del JSON del panel. Si no interesa esperar al subagente, conviene subir el timeout a 30–60 s o mover el hook a `Stop`.

### Interfaz y recarga

`/hooks` muestra en el chat los eventos, tipos, comandos/URLs/prompts, matchers, filtros `if` y los errores registrados por handler. `/hooks reload` fuerza la lectura de `.harness/hooks.json` y vuelve a mostrar el estado. Además, `HookManager.emit()` comprueba el mtime del archivo antes de cada evento (`hot-reload`), así que basta con editar la configuración: no hace falta reiniciar la TUI. Los cambios de la TUI se limitaron a registrarlo en `AVAILABLE_COMMANDS` y en `/help`.

### Latencia percibida al enviar un prompt

`_stream_user_message()` pinta el mensaje y activa el indicador «Pensando…» **antes** de esperar `emit_hook(UserPromptSubmit, parallel=True)`. Con `parallel=True` los handlers arrancan a la vez y se reducen en el orden original: se concatenan los `additionalContext` en orden y sigue ganando el primer deny, aunque los demás ya se hayan ejecutado. Los eventos de herramientas mantienen el modo serie para no alterar los efectos colaterales (por ejemplo, el registro de `audit.py`). Así, un hook `prompt`/`agent` lento ya no retrasa la respuesta visual; el LLM principal sigue recibiendo el contexto antes de la primera llamada.

### Observabilidad en el panel de debug

Cada handler publica en `logger.info` un JSON con `hook: "handler"`: `event`, `type`, `status` (`ok`/`denied`/`error`), `duration_ms`, `matcher`, `if`, `target`, `provider`, `input` (el `HookEvent` completo) y `output` (`denied`, `reason`, `additionalContext`), más el `error` registrado si falló. Al terminar, `emit()` publica otro JSON con `hook: "emit"`: `event`, `parallel`, número de handlers, duración total, `input` y `output` agregado. `DebugEventCollector` los resume en el panel como `🪝 <evento> · <tipo> · <estado> · <ms> · [matcher]` y como `🪝 emit · <evento> · <n> handlers · <ms> · parallel`; al seleccionarlos se abre el JSON completo con `Syntax`. Como el panel guarda los últimos 50 eventos, cada turno deja una traza legible del ciclo de vida sin tocar la TUI: basta con `logger` (F1 muestra el panel). Los errores se normalizan con `HookManager._format_hook_error()`: un `TimeoutError` sin texto se registra como `TimeoutError: superó 10s` (con el límite del handler), de modo que ni el warning ni el campo `error` del JSON quedan vacíos. `_record_error()` usa `error sin motivo` como última línea de defensa, así que el panel siempre marca `status: error` cuando un handler falla.
