"""Hooks de ciclo de vida estilo Claude Code.

Los hooks se leen de ``.harness/hooks.json`` al arrancar y se disparan
automáticamente desde los puntos de extensión del harness. Hay cuatro tipos:
``command``, ``http``, ``prompt`` y ``agent``. Un hook roto nunca interrumpe
al agente (fail-open), pero sus decisiones de bloqueo se respetan.
"""

import asyncio
import fnmatch
import json
import os
import re
import time
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from app.core.config import settings
from app.core.logger import logger


SUPPORTED_EVENTS = frozenset({
    "UserPromptSubmit",
    "PreToolUse",
    "PostToolUse",
    "PreCompact",
    "PostCompact",
    "Stop",
    "StopFailure",
})
TOOL_EVENTS = frozenset({"PreToolUse", "PostToolUse"})
CONTEXT_EVENTS = frozenset({"UserPromptSubmit", "PreToolUse", "PostToolUse"})
HOOK_TYPES = frozenset({"command", "http", "prompt", "agent"})
LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
SAFE_COMMAND_CHARS = re.compile(r"^[A-Za-z0-9_./:=@, -]+$")
URL_REJECTION = "URL no permitida: solo HTTP(S) en loopback"
COMMAND_REJECTION = "comando con caracteres de shell no permitido"
AGENT_HOOK_TIMEOUT = 60.0


def _is_loopback_url(value: object) -> bool:
    """Acepta solo HTTP(S) de loopback, sin usuario/contraseña en la URL."""
    if not isinstance(value, str):
        return False
    try:
        parsed = urlparse(value)
    except ValueError:
        return False
    return (
        parsed.scheme in {"http", "https"}
        and parsed.hostname in LOOPBACK_HOSTS
        and not parsed.username
        and not parsed.password
    )


def _is_safe_command(value: object) -> bool:
    """Sin operadores de shell: ni encadenamiento, expansión ni sustitución."""
    return isinstance(value, str) and bool(SAFE_COMMAND_CHARS.fullmatch(value))
PROMPT_HOOK_SYSTEM = (
    "Decide si la acción del agente debe continuar. Responde solo un JSON con "
    '{"ok": true|false, "reason": "...", "additionalContext": "..."}. '
    '`ok: false` bloquea la acción; `additionalContext` se entrega al modelo.'
)

# Los hooks `agent` ejecutan un AgentLoop. Este guardián evita que sus propios
# eventos vuelvan a disparar los hooks (doble disparo / recursión).
_hook_depth: ContextVar[int] = ContextVar("hook_depth", default=0)


def hook_context_active() -> bool:
    """Falso dentro de un hook `agent`: su loop anidado no debe drenar contexto."""
    return _hook_depth.get() == 0


@dataclass
class HookEvent:
    """Datos que se entregan al hook como JSON por stdin."""

    hook_event_name: str
    session_id: str = ""
    cwd: str = ""
    prompt: str = ""
    tool_name: str | None = None
    tool_input: dict[str, Any] = field(default_factory=dict)
    success: bool | None = None
    trigger: str | None = None
    agent_name: str | None = None
    agent_depth: int = 0

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "hook_event_name": self.hook_event_name,
            "session_id": self.session_id,
            "cwd": self.cwd or os.getcwd(),
        }
        if self.prompt:
            payload["prompt"] = self.prompt
        if self.tool_name:
            payload["tool_name"] = self.tool_name
        if self.tool_input:
            payload["tool_input"] = self.tool_input
        if self.success is not None:
            payload["success"] = self.success
        if self.trigger:
            payload["trigger"] = self.trigger
        if self.agent_name:
            payload["agent_name"] = self.agent_name
        if self.agent_depth:
            payload["agent_depth"] = self.agent_depth
        return payload


@dataclass
class HookOutcome:
    """Resultado de un evento: ``denied`` bloquea la herramienta en curso.

    ``additional_context`` es información temporal para el LLM: se inyecta
    antes de la siguiente llamada y se retira al terminar el turno.
    """

    denied: bool = False
    reason: str = ""
    additional_context: str = ""

    @staticmethod
    def _extract_context(payload: dict) -> str:
        """Lee `additionalContext` del bloque específico o de la raíz."""
        specific = payload.get("hookSpecificOutput")
        value = payload.get("additionalContext")
        if isinstance(specific, dict):
            value = specific.get("additionalContext") or value
        return str(value).strip() if value else ""

    @classmethod
    def from_text(
        cls, text: str | None, plain_is_context: bool = False
    ) -> "HookOutcome":
        """Parsea la salida de un hook (JSON o texto plano).

        Acepta los formatos de Claude Code (``permissionDecision`` y
        ``decision: block``), la clave ``ok: false`` de los hooks `prompt` y
        ``additionalContext``. Si se espera JSON y llega texto plano, este se
        conserva como contexto cuando ``plain_is_context`` es verdadero.
        """
        text = (text or "").strip()
        if not text:
            return cls()
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return cls(additional_context=text) if plain_is_context else cls()
        if not isinstance(payload, dict):
            return cls(additional_context=text) if plain_is_context else cls()

        context = cls._extract_context(payload)
        denied = False
        reason = ""
        if payload.get("ok") is False:
            denied = True
            reason = str(payload.get("reason") or "El hook no aprobó la acción.")
        specific = payload.get("hookSpecificOutput")
        if isinstance(specific, dict) and specific.get("permissionDecision") == "deny":
            denied = True
            reason = str(
                specific.get("permissionDecisionReason")
                or "El hook bloqueó la acción."
            )
        if payload.get("decision") == "block":
            denied = True
            reason = str(payload.get("reason") or "El hook bloqueó la acción.")
        return cls(denied=denied, reason=reason, additional_context=context)

    @classmethod
    def from_process(
        cls, returncode: int, stdout: bytes, stderr: bytes
    ) -> "HookOutcome":
        # Convención Claude Code: exit 2 + motivo en stderr = bloqueo.
        if returncode == 2:
            reason = stderr.decode("utf-8", errors="replace").strip()
            return cls(
                denied=True,
                reason=reason or "El hook bloqueó la acción (código 2).",
            )
        if not stdout:
            return cls()
        return cls.from_text(stdout.decode("utf-8", errors="replace"))


class HookRegistry:
    """Registro de handlers por evento, con filtro por herramienta y regla `if`."""

    def __init__(self, config: dict | None = None):
        self.handlers: dict[str, list[dict[str, Any]]] = {}
        self.rejected: dict[str, str] = {}
        self.disabled_all = False
        if config is not None:
            self.load(config)

    @staticmethod
    def _rejection_key(event_name: str, kind: str, target: Any) -> str:
        return f"{event_name}|{kind}|{target}"

    def load(self, config: dict) -> None:
        self.disabled_all = bool(config.get("disableAllHooks", False))
        self.handlers = {}
        self.rejected = {}
        events = config.get("hooks", {})
        if not isinstance(events, dict):
            return

        for event_name, groups in events.items():
            if event_name not in SUPPORTED_EVENTS or not isinstance(groups, list):
                continue
            entries: list[dict[str, Any]] = []
            for group in groups:
                if not isinstance(group, dict):
                    continue
                matcher = group.get("matcher", "")
                for handler in group.get("hooks", []):
                    if not isinstance(handler, dict):
                        continue
                    kind = handler.get("type", "command")
                    if kind not in HOOK_TYPES:
                        continue
                    main_key = {"command": "command", "http": "url"}.get(
                        kind, "prompt")
                    value = handler.get(main_key, "")
                    if not value:
                        continue
                    if kind == "http" and not _is_loopback_url(value):
                        self.rejected[self._rejection_key(
                            event_name, kind, value)] = URL_REJECTION
                        continue
                    if kind == "command" and not _is_safe_command(value):
                        self.rejected[self._rejection_key(
                            event_name, kind, value)] = COMMAND_REJECTION
                        continue
                    entry: dict[str, Any] = {"matcher": matcher}
                    if kind != "command":
                        entry["type"] = kind
                    entry[main_key] = value
                    for key in ("if", "model", "provider", "tools", "timeout"):
                        if key in handler:
                            entry[key] = handler[key]
                    entries.append(entry)
            if entries:
                self.handlers[event_name] = entries

    @staticmethod
    def _matches(matcher: str, tool_name: str | None) -> bool:
        """Acepta nombres exactos, alternativas `|` y regex (`mcp__.*`)."""
        if not matcher:
            return True
        for alternative in matcher.split("|"):
            candidate = alternative.strip()
            if not candidate:
                continue
            if any(char in candidate for char in "*^$[]()\\"):
                try:
                    if re.fullmatch(candidate, tool_name or ""):
                        return True
                except re.error as exc:
                    logger.warning(f"Matcher de hook inválido '{candidate}': {exc}")
            elif candidate == tool_name:
                return True
        return False

    @staticmethod
    def _signature(tool_name: str | None, tool_input: dict) -> str:
        """Firma `herramienta:detalle`, igual que las reglas de permisos."""
        if tool_name == "bash":
            return f"bash:{tool_input.get('command', '').strip()}"
        if tool_name in ("write_file", "edit_file"):
            return f"{tool_name}:{tool_input.get('path', '')}"
        return tool_name or ""

    @classmethod
    def _passes_if(
        cls, entry: dict, tool_name: str | None, tool_input: dict | None
    ) -> bool:
        rule = entry.get("if")
        if not rule:
            return True
        patterns = [rule] if isinstance(rule, str) else rule
        if not isinstance(patterns, list):
            return True
        signature = cls._signature(tool_name, tool_input or {})
        return any(
            fnmatch.fnmatch(signature, str(pattern)) for pattern in patterns
        )

    def for_event(
        self,
        event_name: str,
        tool_name: str | None = None,
        tool_input: dict | None = None,
    ) -> list[dict[str, Any]]:
        if self.disabled_all:
            return []
        entries = self.handlers.get(event_name, [])
        if event_name not in TOOL_EVENTS:
            return list(entries)
        return [
            entry for entry in entries
            if self._matches(entry["matcher"], tool_name)
            and self._passes_if(entry, tool_name, tool_input)
        ]


class HookManager:
    """Carga la configuración y ejecuta los hooks de forma asíncrona."""

    def __init__(
        self,
        config_file: Path | None = None,
        registry: HookRegistry | None = None,
        timeout: float | None = None,
        llm=None,
        tools=None,
        permissions=None,
    ):
        self.config_file = (
            Path(config_file) if config_file is not None else settings.hooks_file
        )
        self.registry = registry or HookRegistry()
        self.timeout = settings.TOOL_TIMEOUT if timeout is None else timeout
        self.llm = llm
        self.tools = tools
        self.permissions = permissions
        self.pending_context = ""
        self.errors: dict[str, str] = {}
        self._mtime: float | None = None
        self.reload()

    @staticmethod
    def _handler_key(event_name: str, entry: dict) -> str:
        target = (
            entry.get("command") or entry.get("url") or entry.get("prompt") or "?"
        )
        return f"{event_name}|{entry.get('type', 'command')}|{target}"

    def _record_error(self, event_name: str, entry: dict, message: Any) -> None:
        text = str(message or "").strip()
        self.errors[self._handler_key(event_name, entry)] = (
            text or "error sin motivo")[:300]

    @staticmethod
    def _format_hook_error(
        exc: BaseException, timeout: float | None = None
    ) -> str:
        """Describe la excepción; los timeouts suelen tener `str()` vacío."""
        detail = str(exc).strip()
        if isinstance(
            exc, (asyncio.TimeoutError, TimeoutError, httpx.TimeoutException)
        ):
            detail = (
                f"superó {timeout:g}s" if timeout is not None
                else (detail or "timeout")
            )
        return f"{type(exc).__name__}: {detail}" if detail else type(exc).__name__

    @staticmethod
    def _log_hook(payload: dict) -> None:
        """Publica el ciclo de vida del hook como JSON en el panel de debug."""
        logger.info(json.dumps(payload, ensure_ascii=False))

    def _stat_mtime(self) -> float | None:
        try:
            return self.config_file.stat().st_mtime
        except OSError:
            return None

    def reload(self) -> None:
        self._mtime = self._stat_mtime()
        self.errors.clear()
        if not self.config_file.exists():
            self.registry.load({})
            return
        try:
            config = json.loads(
                self.config_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning(
                f"No se pudo leer la configuración de hooks: {exc}")
            self.registry.load({})
            return
        self.registry.load(config if isinstance(config, dict) else {})
        self.errors.update(self.registry.rejected)

    def reload_if_changed(self) -> bool:
        """Hot-reload: vuelve a leer el archivo si cambió su mtime."""
        mtime = self._stat_mtime()
        if mtime == self._mtime:
            return False
        self.reload()
        return True

    async def emit(
        self, event: HookEvent, parallel: bool = False
    ) -> HookOutcome:
        """Ejecuta los hooks; el primer deny en orden de configuración gana.

        Por defecto se ejecutan en serie y el primer deny corta la cadena. Con
        ``parallel=True`` todos arrancan a la vez (útil en ``UserPromptSubmit``
        para no sumar latencias), pero los resultados se reducen en el orden
        original: el contexto se concatena igual y el primer deny sigue
        ganando, aunque los demás handlers ya se hayan ejecutado.
        """
        self.reload_if_changed()
        started = time.perf_counter()
        entries = self.registry.for_event(
            event.hook_event_name, event.tool_name, event.tool_input
        )
        if parallel and len(entries) > 1:
            outcomes = list(await asyncio.gather(
                *(self._run_handler(entry, event) for entry in entries)
            ))
        else:
            outcomes = []
            for entry in entries:
                outcome = await self._run_handler(entry, event)
                outcomes.append(outcome)
                if outcome.denied:
                    break

        contexts = [
            outcome.additional_context
            for outcome in outcomes if outcome.additional_context
        ]
        denial = next(
            (outcome for outcome in outcomes if outcome.denied), None)
        aggregated = "\n".join(contexts)
        if aggregated and event.hook_event_name in CONTEXT_EVENTS:
            self.pending_context = "\n".join(
                part for part in (self.pending_context, aggregated) if part)
        result = HookOutcome(
            denied=denial is not None,
            reason=denial.reason if denial else "",
            additional_context=aggregated,
        )
        self._log_hook({
            "hook": "emit",
            "event": event.hook_event_name,
            "parallel": parallel,
            "handlers": len(entries),
            "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            "input": event.to_dict(),
            "output": {
                "denied": result.denied,
                "reason": result.reason,
                "additionalContext": result.additional_context,
            },
        })
        return result

    async def _run_handler(self, entry: dict, event: HookEvent) -> HookOutcome:
        kind = entry.get("type", "command")
        started = time.perf_counter()
        outcome = HookOutcome()
        try:
            if kind == "command":
                outcome = await self._launch(entry, event)
            elif kind == "http":
                outcome = await self._launch_http(entry, event)
            elif kind == "prompt":
                outcome = await self._launch_prompt(entry, event)
            else:
                outcome = await self._launch_agent(entry, event)
            return outcome
        finally:
            error = self.errors.get(
                self._handler_key(event.hook_event_name, entry), "")
            status = "error" if error else (
                "denied" if outcome.denied else "ok")
            provider = entry.get("provider")
            if not provider and kind in ("prompt", "agent"):
                provider = settings.LLM_PROVIDER
            self._log_hook({
                "hook": "handler",
                "event": event.hook_event_name,
                "type": kind,
                "status": status,
                "duration_ms": round(
                    (time.perf_counter() - started) * 1000, 2),
                "matcher": entry.get("matcher", ""),
                "if": entry.get("if", ""),
                "target": (
                    entry.get("command") or entry.get("url")
                    or entry.get("prompt") or ""
                ),
                "provider": provider or "",
                "input": event.to_dict(),
                "output": {
                    "denied": outcome.denied,
                    "reason": outcome.reason,
                    "additionalContext": outcome.additional_context,
                },
                "error": error or None,
            })

    async def _launch(self, entry: dict, event: HookEvent) -> HookOutcome:
        command = entry["command"]
        if not _is_safe_command(command):
            logger.warning(f"Hook '{command}' rechazado: {COMMAND_REJECTION}")
            self._record_error(
                event.hook_event_name, entry, COMMAND_REJECTION)
            return HookOutcome()
        payload = json.dumps(event.to_dict(), ensure_ascii=False).encode("utf-8")
        process = None
        stdout_output, stderr_output = b"", b""
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=event.cwd or os.getcwd(),
            )
            stdout_output, stderr_output = await asyncio.wait_for(
                process.communicate(payload), self.timeout)
        except (OSError, asyncio.TimeoutError, TimeoutError) as exc:
            if process is not None and process.returncode is None:
                process.kill()
                await process.wait()
            message = self._format_hook_error(exc, self.timeout)
            logger.warning(f"Hook '{command}' falló: {message}")
            self._record_error(event.hook_event_name, entry, message)
            return HookOutcome()

        if process.returncode != 0:
            stderr = stderr_output.decode("utf-8", errors="replace")
            logger.warning(
                f"Hook '{command}' terminó con código {process.returncode}: {stderr}"
            )
            if process.returncode != 2:
                self._record_error(
                    event.hook_event_name, entry, stderr or f"código {process.returncode}")
        return HookOutcome.from_process(
            process.returncode, stdout_output, stderr_output)

    async def _launch_http(self, entry: dict, event: HookEvent) -> HookOutcome:
        url = entry["url"]
        if not _is_loopback_url(url):
            logger.warning(f"Hook http '{url}' rechazado: {URL_REJECTION}")
            self._record_error(event.hook_event_name, entry, URL_REJECTION)
            return HookOutcome()
        timeout = entry.get("timeout", self.timeout)
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, json=event.to_dict())
        except Exception as exc:
            message = self._format_hook_error(exc, timeout)
            logger.warning(f"Hook http '{url}' falló: {message}")
            self._record_error(event.hook_event_name, entry, message)
            return HookOutcome()
        if response.status_code >= 400:
            logger.warning(
                f"Hook http '{url}' respondió HTTP {response.status_code}")
            self._record_error(
                event.hook_event_name, entry, f"HTTP {response.status_code}")
            return HookOutcome()
        return HookOutcome.from_text(response.text)

    def _llm_for(self, entry: dict):
        """LLM inyectado o construido desde la configuración del hook."""
        if self.llm is not None:
            return self.llm
        from app.core.llm import get_llm

        provider = entry.get("provider") or settings.LLM_PROVIDER
        kwargs = {}
        if entry.get("model"):
            kwargs["model"] = entry["model"]
        return get_llm(provider, **kwargs)

    async def _launch_prompt(self, entry: dict, event: HookEvent) -> HookOutcome:
        try:
            llm = self._llm_for(entry)
            messages = [
                {"role": "system", "content": PROMPT_HOOK_SYSTEM},
                {"role": "user", "content": (
                    f"{entry['prompt']}\n\nEvento: "
                    f"{json.dumps(event.to_dict(), ensure_ascii=False)}")},
            ]
            response = await asyncio.wait_for(llm.chat(messages), self.timeout)
        except Exception as exc:
            message = self._format_hook_error(exc, self.timeout)
            logger.warning(f"Hook prompt falló: {message}")
            self._record_error(event.hook_event_name, entry, message)
            return HookOutcome()
        return HookOutcome.from_text(
            response.content or "", plain_is_context=True)

    async def _launch_agent(self, entry: dict, event: HookEvent) -> HookOutcome:
        timeout = entry.get("timeout", AGENT_HOOK_TIMEOUT)
        token = _hook_depth.set(_hook_depth.get() + 1)
        try:
            from .permissions import PermissionGate
            from .subagents import DelegateTool
            from .tool import ToolRegistry

            llm = self._llm_for(entry)
            tools = self.tools or ToolRegistry()
            # `tools` de la config no concede permisos: el subagente hereda
            # aprobaciones y policies, y las tools sensibles siguen pidiendo.
            gate = (self.permissions or PermissionGate()).child()
            delegate = DelegateTool(
                name="hook_agent",
                description="Subagente invocado por un hook",
                llm=llm,
                tools=tools,
                system_prompt=entry["prompt"],
                permissions=gate,
            )
            task = (
                f"{entry['prompt']}\n\nEvento: "
                f"{json.dumps(event.to_dict(), ensure_ascii=False)}"
            )
            result = await asyncio.wait_for(delegate.run(task), timeout)
        except Exception as exc:
            message = self._format_hook_error(exc, timeout)
            logger.warning(f"Hook agent falló: {message}")
            self._record_error(event.hook_event_name, entry, message)
            return HookOutcome()
        finally:
            _hook_depth.reset(token)

        if not result.success:
            reason = result.error or "sin motivo"
            logger.warning(f"Hook agent devolvió error: {reason}")
            self._record_error(event.hook_event_name, entry, reason)
            return HookOutcome()
        text = (result.content or "").split("Response:\n", 1)[-1]
        return HookOutcome.from_text(text, plain_is_context=True)

    def drain_context(self) -> str:
        """Devuelve y limpia el contexto pendiente (un solo uso por turno)."""
        context = self.pending_context
        self.pending_context = ""
        return context

    def describe(self) -> str:
        """Resumen legible de los hooks activos, los descartados y sus errores."""
        if not self.registry.handlers and not self.registry.rejected:
            return "No hay hooks configurados. Revisa `.harness/hooks.json`."
        lines = []
        if self.registry.handlers:
            lines += ["### 🪝 Hooks activos", ""]
        for event_name, entries in self.registry.handlers.items():
            lines.append(f"**{event_name}**")
            for entry in entries:
                kind = entry.get("type", "command")
                target = (
                    entry.get("command") or entry.get("url") or entry.get("prompt") or "?"
                )
                if len(target) > 50:
                    target = target[:47] + "..."
                details = [f"`{kind}`", f"`{target}`"]
                if entry.get("matcher"):
                    details.append(f"matcher `{entry['matcher']}`")
                if entry.get("if"):
                    details.append(f"if `{entry['if']}`")
                line = "- " + " · ".join(details)
                error = self.errors.get(self._handler_key(event_name, entry))
                if error:
                    line += f" ⚠️ {error}"
                lines.append(line)
            lines.append("")
        if self.registry.rejected:
            lines += ["### 🚫 Hooks descartados", ""]
            for key, reason in self.registry.rejected.items():
                lines.append(f"- `{key}` · {reason}")
            lines.append("")
        lines.append(f"Config: `{self.config_file}`")
        return "\n".join(lines)


hook_manager = HookManager()


async def emit_hook(
    event: HookEvent, parallel: bool = False
) -> HookOutcome:
    """Dispara un evento; reutilizable desde el loop, el contexto y la TUI."""
    if _hook_depth.get() > 0:
        return HookOutcome()
    return await hook_manager.emit(event, parallel=parallel)
