# Seguridad en A2A

## Permisos en Subagentes
Los subagentes **no heredan la instancia** del `PermissionGate` del padre: cada estrategia (`supervisor`, `sequential`, `parallel`, `swarm`) crea uno nuevo con el mismo `ask_user` y una copia de las `policies`. `supervisor`, `sequential` y `swarm` leen además los patrones persistidos en `.harness/permissions.json` (lo que permite no repetir confirmaciones aprobadas con `a`); `parallel` no los lee. El `DelegateTool` legacy crea su propio gate con sus tools en `Decision.ALLOW`, sin preguntar.

## Riesgos de los Subagentes
- **Prompt Injection**: Un agente malicioso podría intentar engañar al supervisor para que delegue una tarea peligrosa. Mitigación: el `PermissionGate` bloquea las tools sensibles.
- **Bucles Infinitos**: El `SwarmStrategy` tiene un límite de 5 saltos (`max_hops`). El `AgentLoop` tiene `max_iterations=10`.
- **Escalada de Privilegios**: Los subagentes solo tienen acceso a las tools que se les asignan en su `AgentCard`. No tienen acceso al registry completo.