# Seguridad en A2A

## Permisos en Subagentes
Los subagentes heredan el `PermissionGate` del padre. Si el usuario aprobó una tool con `a` (always), se guarda en `.harness/permissions.json`. Los subagentes leen ese archivo para no pedir confirmación dos veces.

## Riesgos de los Subagentes
- **Prompt Injection**: Un agente malicioso podría intentar engañar al supervisor para que delegue una tarea peligrosa. Mitigación: el `PermissionGate` bloquea las tools sensibles.
- **Bucles Infinitos**: El `SwarmStrategy` tiene un límite de 5 saltos (`max_hops`). El `AgentLoop` tiene `max_iterations=10`.
- **Escalada de Privilegios**: Los subagentes solo tienen acceso a las tools que se les asignan en su `AgentCard`. No tienen acceso al registry completo.