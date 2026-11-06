from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Awaitable


class Decision(str, Enum):
    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"


@dataclass
class PermissionPolicy:
    """Define la política por defecto para cada herramienta."""
    tool_name: str
    default_decision: Decision


@dataclass
class PermissionGate:
    """Gestiona los permisos de las herramientas."""
    # Políticas por defecto (ej. bash pide permiso, read_file no)
    policies: dict[str, Decision] = field(default_factory=dict)
    # Memoria de sesión para herramientas aprobadas temporalmente
    session_allowed: set[str] = field(default_factory=set)
    # Función asíncrona para preguntar al usuario (inyectable para tests)
    ask_user: Callable[[str, str, dict], Awaitable[str]] | None = None

    def __post_init__(self):
        # Configuración por defecto segura
        if not self.policies:
            self.policies = {
                "read_file": Decision.ALLOW,
                "list_dir": Decision.ALLOW,
                "write_file": Decision.ASK,
                "bash": Decision.ASK,
            }

    async def check(self, tool_name: str, arguments: dict) -> Decision:
        # 1. ¿Ya se aprobó en esta sesión?
        if tool_name in self.session_allowed:
            return Decision.ALLOW

        # 2. ¿Qué dice la política por defecto?
        # Por defecto, preguntar si es desconocida
        policy = self.policies.get(tool_name, Decision.ASK)

        if policy == Decision.ALLOW:
            return Decision.ALLOW
        if policy == Decision.DENY:
            return Decision.DENY

        # 3. Si es ASK, dependemos de la función ask_user
        if not self.ask_user:
            return Decision.DENY  # Si no hay interfaz para preguntar, denegar por seguridad

        # Preguntar al usuario
        response = await self.ask_user(tool_name, "Permiso requerido", arguments)

        if response.lower() in ("y", "yes", "s", "si", "sí"):
            return Decision.ALLOW
        elif response.lower() in ("a", "always", "siempre"):
            self.session_allowed.add(tool_name)
            return Decision.ALLOW

        return Decision.DENY
