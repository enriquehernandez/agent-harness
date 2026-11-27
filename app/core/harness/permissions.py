import asyncio
import difflib
import inspect
import json
import uuid
from pathlib import Path
from app.core.config import settings
from app.core.logger import logger
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Awaitable, Iterable, Literal


class Decision(str, Enum):
    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"


class PermissionReply(str, Enum):
    """Respuestas permitidas a una petición de permiso encolada."""

    ONCE = "once"
    ALWAYS = "always"
    REJECT = "reject"


_REPLY_ALIASES = {
    "y": PermissionReply.ONCE,
    "yes": PermissionReply.ONCE,
    "s": PermissionReply.ONCE,
    "si": PermissionReply.ONCE,
    "sí": PermissionReply.ONCE,
    "once": PermissionReply.ONCE,
    "a": PermissionReply.ALWAYS,
    "always": PermissionReply.ALWAYS,
    "siempre": PermissionReply.ALWAYS,
    "n": PermissionReply.REJECT,
    "no": PermissionReply.REJECT,
    "reject": PermissionReply.REJECT,
}


def normalize_reply(value: str | PermissionReply) -> PermissionReply:
    """Acepta las respuestas de la TUI y del CLI; las desconocidas son errores."""
    if isinstance(value, PermissionReply):
        return value
    try:
        return _REPLY_ALIASES[value.strip().lower()]
    except (AttributeError, KeyError) as exc:
        raise ValueError(
            f"Respuesta no válida: {value!r}. Usa once|always|reject."
        ) from exc


@dataclass
class PermissionRequest:
    """Una petición `ask` esperando una respuesta externa.

    `sessionID` identifica al agente que pide permiso (padre o subagente) y
    `requestID` identifica la llamada concreta. `resources` y `patterns` viajan
    con la petición para que la TUI pueda mostrarlos sin reconstruir los args.
    """

    request_id: str
    session_id: str
    tool_name: str
    signature: str
    resources: tuple[str, ...]
    patterns: tuple[str, ...]
    args: dict
    diff_text: str | None
    reply: PermissionReply | None = None
    event: asyncio.Event = field(
        default_factory=asyncio.Event, repr=False, compare=False)


class PermissionBroker:
    """Cola compartida de peticiones de permiso, una por tool call en espera.

    La TUI se suscribe con `add_listener` para mostrar las peticiones, pero el
    tool call no depende de un modal: espera en `event` hasta que alguien llama
    a `reply`. Sin suscriptores, `unattended` decide entre denegar o dejar la
    petición pendiente; nunca se aprueba automáticamente.
    """

    def __init__(self, *, unattended: Literal["deny", "pending"] = "deny"):
        if unattended not in ("deny", "pending"):
            raise ValueError("unattended debe ser 'deny' o 'pending'")
        self.unattended = unattended
        self.pending: dict[str, PermissionRequest] = {}
        self._listeners: list[Callable[[PermissionRequest],
                                       Awaitable[None] | None]] = []
        self._rejected_sessions: set[str] = set()

    def add_listener(self, listener: Callable[[PermissionRequest],
                                              Awaitable[None] | None]) -> None:
        self._listeners.append(listener)

    def is_rejected(self, session_id: str) -> bool:
        return session_id in self._rejected_sessions

    def list_pending(self, session_id: str | None = None) -> list[PermissionRequest]:
        return [
            request for request in self.pending.values()
            if session_id is None or request.session_id == session_id
        ]

    async def request(
        self,
        *,
        session_id: str,
        tool_name: str,
        signature: str,
        args: dict,
        diff_text: str | None = None,
        patterns: Iterable[str] | None = None,
    ) -> PermissionReply:
        if session_id in self._rejected_sessions:
            return PermissionReply.REJECT

        request = PermissionRequest(
            request_id=f"req-{uuid.uuid4().hex[:8]}",
            session_id=session_id,
            tool_name=tool_name,
            signature=signature,
            resources=(signature,),
            patterns=tuple(patterns or (signature,)),
            args=args,
            diff_text=diff_text,
        )
        self.pending[request.request_id] = request
        try:
            for listener in tuple(self._listeners):
                result = listener(request)
                if inspect.isawaitable(result):
                    await result

            if not self._listeners and self.unattended == "deny":
                self.reply(request.request_id, PermissionReply.REJECT)

            await request.event.wait()
            return request.reply or PermissionReply.REJECT
        finally:
            self.pending.pop(request.request_id, None)

    def reply(self, request_id: str, answer: str | PermissionReply) -> bool:
        reply = normalize_reply(answer)
        request = self.pending.get(request_id)
        if request is None:
            return False

        if reply == PermissionReply.REJECT:
            self._rejected_sessions.add(request.session_id)
            for pending in tuple(self.pending.values()):
                if pending.session_id == request.session_id:
                    pending.reply = reply
                    pending.event.set()
        else:
            request.reply = reply
            request.event.set()
        return True


@dataclass
class PermissionGate:
    """Manages tool permissions."""

    policies: dict[str, Decision] = field(default_factory=dict)
    session_allowed: set[str] = field(default_factory=set)
    ask_user: Callable[[str, str, dict, str | None],
                       Awaitable[str]] | None = None
    persist_file: Path = field(
        default_factory=lambda: settings.permissions_file)
    broker: PermissionBroker | None = None
    session_id: str = "main"

    def __post_init__(self):
        if not self.policies:
            self.policies = {
                "read_file": Decision.ASK,
                "read_text_file": Decision.ASK,
                "list_dir": Decision.ASK,
                "list_directory": Decision.ASK,
                "write_file": Decision.ASK,
                "edit_file": Decision.ASK,
                "bash": Decision.ASK,
            }
        self._load_persisted_permissions()

    def _load_persisted_permissions(self):
        if self.persist_file.exists():
            try:
                with open(self.persist_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for pattern in data.get("session_allowed", []):
                        self.session_allowed.add(pattern)
            except Exception:
                pass

    def reload_persisted(self) -> None:
        """Vuelve a leer `.harness/permissions.json`, descartando aprobaciones en memoria."""
        self.session_allowed.clear()
        self._load_persisted_permissions()

    def child(self, allow: Iterable[str] = (), *,
              session_id: str | None = None) -> "PermissionGate":
        """Crea un gate de subagente que comparte aprobaciones, broker y persistencia.

        Las `policies` se copian para que el hijo pueda añadir excepciones propias
        (p. ej. las tools del reviewer) sin alterar la política del padre.
        `session_allowed` se comparte por referencia: una aprobación con `a` en
        cualquier subagente vale también para el padre y para sus hermanos. Cada
        hijo tiene su propio `session_id` para que `reject` solo cierre sus
        peticiones, aunque comparta la cola con el padre.
        """
        child = PermissionGate(
            policies=self.policies.copy(),
            session_allowed=self.session_allowed,
            ask_user=self.ask_user,
            persist_file=self.persist_file,
            broker=self.broker,
            session_id=session_id or self.session_id,
        )
        for tool in allow:
            child.policies[tool] = Decision.ALLOW
        return child

    def _save_persisted_permissions(self):
        data = {"session_allowed": list(self.session_allowed)}
        try:
            self.persist_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.persist_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving permissions: {e}")

    def _get_signature(self, tool_name: str, arguments: dict) -> str:
        if tool_name == "bash":
            return f"bash:{arguments.get('command', '').strip()}"
        elif tool_name in ("write_file", "edit_file"):
            return f"{tool_name}:{arguments.get('path', '')}"
        return tool_name

    def _is_allowed(self, signature: str) -> bool:
        """Una aprobación autoriza exactamente la firma guardada, nunca un glob.

        `y` aprueba una sola llamada; `a` persiste esa firma textual. Si el usuario
        aprueba `bash:grep *.log`, solo `grep *.log` queda autorizado: `*`, `?` y
        `[...]` se comparan como caracteres literales, no como patrones.
        """
        return signature in self.session_allowed

    def _generate_diff(self, args: dict) -> str | None:
        if "path" in args and "content" in args:
            path = Path(args["path"])
            old_content = ""
            if path.exists():
                try:
                    old_content = path.read_text(encoding="utf-8")
                except Exception:
                    pass
            new_content = args["content"]
            return "".join(
                difflib.unified_diff(
                    old_content.splitlines(keepends=True),
                    new_content.splitlines(keepends=True),
                    fromfile=f"a/{args['path']}",
                    tofile=f"b/{args['path']}",
                    lineterm="",
                )
            )

        if "path" in args and "edits" in args:
            path = Path(args["path"])
            if not path.exists():
                return f"File {args['path']} does not exist, cannot generate diff."
            try:
                old_content = path.read_text(encoding="utf-8")
            except Exception as e:
                return f"Could not read file: {e}"

            new_content = old_content
            for edit in args["edits"]:
                old_text = edit.get("oldText", "")
                new_text = edit.get("newText", "")
                if not old_text:
                    return "⚠️ edit con 'oldText' vacío: no se puede generar el diff."
                if old_text in new_content:
                    new_content = new_content.replace(old_text, new_text)
                else:
                    return f"⚠️ Text to replace not found: {old_text[:20]}..."

            return "".join(
                difflib.unified_diff(
                    old_content.splitlines(keepends=True),
                    new_content.splitlines(keepends=True),
                    fromfile=f"a/{args['path']}",
                    tofile=f"b/{args['path']}",
                    lineterm="",
                )
            )

        return None

    async def _ask_broker(
        self, tool_name: str, signature: str, arguments: dict
    ) -> PermissionReply:
        """Encola el `ask` y espera a que la TUI/CLI responda por su `requestID`."""
        return await self.broker.request(
            session_id=self.session_id,
            tool_name=tool_name,
            signature=signature,
            patterns=(signature,),
            args=arguments,
            diff_text=self._generate_diff(arguments),
        )

    async def check(self, tool_name: str, arguments: dict) -> Decision:
        signature = self._get_signature(tool_name, arguments)
        policy = self.policies.get(tool_name, Decision.ASK)

        # Un `deny` configurado gana siempre, incluso a una firma guardada con
        # `always` en una sesión anterior.
        if policy == Decision.DENY:
            return Decision.DENY
        if policy == Decision.ALLOW or self._is_allowed(signature):
            return Decision.ALLOW

        if self.broker is not None:
            reply = await self._ask_broker(tool_name, signature, arguments)
            if reply == PermissionReply.ALWAYS:
                if self.policies.get(tool_name, Decision.ASK) == Decision.DENY:
                    return Decision.DENY
                self.session_allowed.add(signature)
                self._save_persisted_permissions()
            if reply in (PermissionReply.ONCE, PermissionReply.ALWAYS):
                return Decision.ALLOW
            return Decision.DENY

        # Compatibilidad con llamadores que todavía pasan `ask_user` directo.
        # La TUI ya no usa esta vía: sus peticiones pasan por el broker.
        if not self.ask_user:
            return Decision.DENY

        diff_text = self._generate_diff(arguments)
        response = await self.ask_user(tool_name, signature, arguments, diff_text)

        if response.lower() in ("y", "yes", "s", "si", "sí"):
            return Decision.ALLOW
        elif response.lower() in ("a", "always", "siempre"):
            self.session_allowed.add(signature)
            self._save_persisted_permissions()
            return Decision.ALLOW

        return Decision.DENY
