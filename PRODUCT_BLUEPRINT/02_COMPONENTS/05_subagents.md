# Subagentes Delegados (Subagents-as-Tools)

## El Problema del Contexto Compartido
Cuando un agente usa herramientas muy pesadas (como leer 10 archivos para revisar código), el contexto de la conversación principal se llena de información irrelevante para el usuario. Esto aumenta los costes, la latencia y las probabilidades de alucinación.

## La Solución: Subagentes Aislados
Implementamos el patrón **Subagents-as-Tools**. El agente principal (Orquestador) tiene acceso a una herramienta llamada `delegate_to_reviewer`. 

Cuando el Orquestador la invoca:
1.  Se instancia un **nuevo AgentLoop** con su propio `ContextManager` y un `ToolRegistry` restringido. En la TUI se intentan copiar `read_text_file`, `list_directory` y `bash` (`app/tui/app.py`), pero `read_text_file` y `list_directory` no están registrados (`register_core_tools()` registra `read_file`, `write_file`, `bash`, etc.), así que en la práctica solo queda `bash`. Además, `DelegateTool.run()` crea su propio `PermissionGate` y marca esas tools como `Decision.ALLOW` (`app/core/harness/subagents.py`): no usa el gate interactivo del padre.
2.  El Subagente ejecuta la tarea de forma aislada.
3.  Al terminar, devuelve **solo un resumen** al agente principal.

## Ventajas
- **Ahorro de Tokens:** El agente principal no ve todo el proceso de lectura del subagente, solo el resultado final.
- **Seguridad:** El subagente tiene un conjunto de herramientas limitado (Principio de Menor Privilegio).
- **Modularidad:** Puedes crear diferentes subagentes (Reviewer, Documentador, Tester) y registrarlos como herramientas.