# Seguridad en A2A

## Permisos en Subagentes
Los subagentes usan un gate hijo del `PermissionGate` del padre (`PermissionGate.child()`): comparten `ask_user`, `persist_file` y `session_allowed` por referencia, pero copian las `policies` para poder añadir excepciones locales. Las cuatro estrategias (`supervisor`, `sequential`, `parallel` y `swarm`) lo construyen con `A2AStrategy._child_gate()`, que además carga los patrones persistidos en `.harness/permissions.json`, de modo que una confirmación aprobada con `a` no se repite en ninguna de ellas. El `DelegateTool` legacy recibe el gate de la TUI y ya no marca sus propias tools como `Decision.ALLOW` en la copia del hijo: comparte aprobaciones, pero `bash`/`write_file` requieren una decisión explícita.

## Riesgos de los Subagentes
- **Prompt Injection**: Un agente malicioso podría intentar engañar al supervisor para que delegue una tarea peligrosa. Mitigación: el `PermissionGate` bloquea las tools sensibles. En modo `fork`, `A2AStrategy._fork_context()` no copia el mensaje `system` del padre, de modo que las reglas del orquestador no se inyectan como instrucciones del subagente.
- **Bucles Infinitos**: El `SwarmStrategy` tiene un límite de 5 saltos (`max_hops`). El `AgentLoop` tiene `max_iterations=10`.
- **Escalada de Privilegios**: Los subagentes solo tienen acceso a las tools que se les asignan en su `AgentCard`. No tienen acceso al registry completo.