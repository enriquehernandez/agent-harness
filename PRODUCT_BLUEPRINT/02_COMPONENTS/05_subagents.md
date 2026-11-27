# Subagentes Delegados (Subagents-as-Tools)

## El Problema del Contexto Compartido
Cuando un agente usa herramientas muy pesadas (como leer 10 archivos para revisar código), el contexto de la conversación principal se llena de información irrelevante para el usuario. Esto aumenta los costes, la latencia y las probabilidades de alucinación.

## La Solución: Subagentes Aislados
Implementamos el patrón **Subagents-as-Tools**. El agente principal (Orquestador) tiene acceso a una herramienta llamada `delegate_to_reviewer`. 

Cuando el Orquestador la invoca:
1.  Se instancia un **nuevo AgentLoop** con su propio `ContextManager` y un `ToolRegistry` restringido. La TUI copia `read_file` y `bash` (`app/tui/app.py`), que son nombres reales del registry (`register_core_tools()`); para listar directorios el subagente usa `bash`. Además, `DelegateTool.run()` deriva un gate hijo del gate interactivo del padre con `PermissionGate.child(session_id="delegate:<nombre>")` (`app/core/harness/subagents.py`): comparte la cola, las aprobaciones (`session_allowed`) y las `policies`, pero **no auto-aprueba ninguna tool**. `bash` y `write_file` siguen encolando una petición con ese `sessionID` salvo que ya estén aprobadas en `session_allowed`; las peticiones se responden desde el chat con `/permissions reply <requestID> ...`.
2.  El Subagente ejecuta la tarea de forma aislada.
3.  Al terminar, devuelve **solo un resumen** al agente principal.

## Ventajas
- **Ahorro de Tokens:** El agente principal no ve todo el proceso de lectura del subagente, solo el resultado final.
- **Seguridad:** El subagente tiene un conjunto de herramientas limitado (Principio de Menor Privilegio).
- **Modularidad:** Puedes crear diferentes subagentes (Reviewer, Documentador, Tester) y registrarlos como herramientas.