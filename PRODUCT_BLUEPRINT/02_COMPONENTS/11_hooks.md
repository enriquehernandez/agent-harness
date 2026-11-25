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

- `matcher` admite alternativas separadas por `|` y solo filtra `PreToolUse`/`PostToolUse` por nombre de herramienta; vacío significa «todas». En el resto de eventos se ignora.
- Solo se aceptan handlers `type: command` (fase 1). Los tipos `http`, `prompt` y `agent` quedan para la fase 3.
- `disableAllHooks: true` desactiva todos los hooks sin borrar la configuración.
- Los scripts de hooks van en `.harness/hooks/` y se versionan; el log que generan (`audit.log`) queda ignorado.

## Arquitectura

`app/core/harness/hooks.py` contiene cuatro piezas:

- `HookEvent`: payload con `hook_event_name`, `session_id`, `cwd`, `prompt`, `tool_name`, `tool_input`, `success`, `trigger`, `agent_name` y `agent_depth`. Los campos vacíos se omiten al serializar.
- `HookOutcome`: resultado del evento (`denied`, `reason`). Lo produce `from_process()` a partir de la salida del comando.
- `HookRegistry`: carga y filtra los handlers por evento y herramienta, siguiendo el Registry Pattern.
- `HookManager`: lee el JSON, lanza cada comando con `asyncio.create_subprocess_shell()` y pasa el evento por **stdin** como JSON. El comando sale de la configuración (archivo de confianza); los datos del evento nunca se interpolan en la cadena. Se aplica `settings.TOOL_TIMEOUT` y, si expira, se mata el proceso.

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
2. Escribir en `stdout` un JSON con `hookSpecificOutput.permissionDecision: "deny"` y `hookSpecificOutput.permissionDecisionReason`. También se reconoce el formato genérico `decision: "block"` con `reason`.

`HookManager.emit()` ejecuta los hooks en orden y devuelve el **primer deny**, sin lanzar los restantes. `AgentLoop._execute_tool()` consulta el resultado **antes de `PermissionGate.check()`**, de modo que el deny prevalece sobre `allow`: no llama a la herramienta, escribe el motivo en el resultado de la tool y marca `last_hook_denial`. En `stream()`, ese estado produce el evento `AgentEvent(type="hook_denied", data={"tool": ..., "message": ...})`; `stream_to_chat()` lo muestra como `🚫 **Bloqueado por un hook:** ...` sin interrumpir el turno.

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
- Resto de la fase 2 (feed-back de `Stop`/`PostToolUse` e `additionalContext`) y fase 3 (tipos avanzados, matchers completos y `/hooks`) siguen pendientes en `tasks/pendientes.md`.
