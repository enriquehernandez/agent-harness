# Hooks del ciclo de vida

Los hooks permiten ejecutar comandos definidos por el usuario **automáticamente** en puntos concretos del ciclo de vida del harness, sin que el agente tenga que elegirlos y sin que el usuario escriba ningún comando. Son el equivalente, en versión reducida, de los hooks de Claude Code.

La configuración vive en `.harness/hooks.json` (`settings.hooks_file`) y se carga al arrancar:

```json
{
  "disableAllHooks": false,
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          { "type": "command", "command": "python .claude/hooks/audit.py" }
        ]
      }
    ],
    "Stop": [
      { "hooks": [{ "type": "command", "command": "echo 'turno terminado' >> .harness/logs/hooks.log" }] }
    ]
  }
}
```

- `matcher` admite alternativas separadas por `|` y solo filtra `PreToolUse`/`PostToolUse` por nombre de herramienta; vacío significa «todas». En el resto de eventos se ignora.
- Solo se aceptan handlers `type: command` (fase 1). Los tipos `http`, `prompt` y `agent` quedan para fases posteriores.
- `disableAllHooks: true` desactiva todos los hooks sin borrar la configuración.

## Arquitectura

`app/core/harness/hooks.py` contiene tres piezas:

- `HookEvent`: payload con `hook_event_name`, `session_id`, `cwd`, `prompt`, `tool_name`, `tool_input`, `success`, `trigger`, `agent_name` y `agent_depth`. Los campos vacíos se omiten al serialize.
- `HookRegistry`: carga y filtra los handlers por evento y herramienta, siguiendo el Registry Pattern.
- `HookManager`: lee el JSON, lanza cada comando con `asyncio.create_subprocess_shell()` y pasa el evento por **stdin** como JSON. El comando sale de la configuración (archivo de confianza); los datos del evento nunca se interpolan en la cadena. Se aplica `settings.TOOL_TIMEOUT` y, si expira, se mata el proceso.

`emit_hook(event)` es la única fachada pública; el módulo mantiene un `hook_manager` compartido.

## Puntos de disparo (fase 1)

| Evento | Dónde se dispara |
| :--- | :--- |
| `UserPromptSubmit` | Envío de prompts de la TUI (`_stream_user_message()` y rama de imágenes de `on_input_submitted()`) y en `AgentLoop.run()` para el modo headless |
| `PreToolUse` / `PostToolUse` | `AgentLoop._execute_tool()`, antes de permisos y al terminar (éxito, denegación, tool no encontrada o fallo) |
| `PreCompact` / `PostCompact` | `ContextManager.maybe_compact()` (`trigger: auto`) y `force_compact()` (`trigger: manual`) |
| `Stop` | Final de `AgentLoop.run()` y de `AgentLoop.stream()` (respuesta final o máximo de iteraciones) |
| `StopFailure` | Ramas de timeout y excepción de `AgentLoop.stream()` |

Los eventos de subagentes A2A incluyen `agent_name`/`agent_depth` para poder filtrarlos.

## Contrato de la fase 1

- **Observación pura:** la salida del hook se ignora; no puede bloquear herramientas ni inyectar contexto. Esas decisiones se reservan para la fase 2.
- **Fail-open:** un JSON inválido, un comando que no existe, un código de salida distinto de cero o un timeout solo generan un aviso con `logger.warning` y no interrumpen al agente.
- La compactación y el Permission Gate siguen funcionando igual: los hooks son aditivos.
