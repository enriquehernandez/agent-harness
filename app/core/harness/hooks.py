"""Hooks de ciclo de vida estilo Claude Code.

Los hooks se leen de ``.harness/hooks.json`` al arrancar y se disparan
automáticamente desde los puntos de extensión del harness. Solo se aceptan
handlers ``command``: reciben el evento como JSON por stdin y su salida se
ignora (fase observadora). Un hook roto nunca interrumpe al agente.
"""

import asyncio
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

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


class HookRegistry:
    """Registro de handlers por evento, con filtro por nombre de herramienta."""

    def __init__(self, config: dict | None = None):
        self.handlers: dict[str, list[dict[str, str]]] = {}
        self.disabled_all = False
        if config is not None:
            self.load(config)

    def load(self, config: dict) -> None:
        self.disabled_all = bool(config.get("disableAllHooks", False))
        self.handlers = {}
        events = config.get("hooks", {})
        if not isinstance(events, dict):
            return

        for event_name, groups in events.items():
            if event_name not in SUPPORTED_EVENTS or not isinstance(groups, list):
                continue
            entries: list[dict[str, str]] = []
            for group in groups:
                if not isinstance(group, dict):
                    continue
                matcher = group.get("matcher", "")
                for handler in group.get("hooks", []):
                    if not isinstance(handler, dict):
                        continue
                    if handler.get("type", "command") != "command":
                        continue
                    command = handler.get("command", "")
                    if command:
                        entries.append({"matcher": matcher, "command": command})
            if entries:
                self.handlers[event_name] = entries

    def for_event(
        self, event_name: str, tool_name: str | None = None
    ) -> list[dict[str, str]]:
        if self.disabled_all:
            return []
        entries = self.handlers.get(event_name, [])
        if event_name not in TOOL_EVENTS:
            return list(entries)
        return [
            entry for entry in entries
            if not entry["matcher"]
            or tool_name in {
                name.strip() for name in entry["matcher"].split("|")
            }
        ]


class HookManager:
    """Carga la configuración y ejecuta los hooks de forma asíncrona."""

    def __init__(
        self,
        config_file: Path | None = None,
        registry: HookRegistry | None = None,
        timeout: float | None = None,
    ):
        self.config_file = (
            Path(config_file) if config_file is not None else settings.hooks_file
        )
        self.registry = registry or HookRegistry()
        self.timeout = settings.TOOL_TIMEOUT if timeout is None else timeout
        self.reload()

    def reload(self) -> None:
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

    async def emit(self, event: HookEvent) -> None:
        for handler in self.registry.for_event(
            event.hook_event_name, event.tool_name
        ):
            await self._launch(handler["command"], event)

    async def _launch(self, command: str, event: HookEvent) -> None:
        payload = json.dumps(event.to_dict(), ensure_ascii=False).encode("utf-8")
        process = None
        stderr_output = b""
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=event.cwd or os.getcwd(),
            )
            _, stderr_output = await asyncio.wait_for(
                process.communicate(payload), self.timeout)
        except (OSError, asyncio.TimeoutError, TimeoutError) as exc:
            if process is not None and process.returncode is None:
                process.kill()
                await process.wait()
            logger.warning(f"Hook '{command}' falló: {exc}")
            return

        if process.returncode != 0:
            stderr = stderr_output.decode("utf-8", errors="replace")
            logger.warning(
                f"Hook '{command}' terminó con código {process.returncode}: {stderr}"
            )
        # La salida se ignora en la fase observadora.


hook_manager = HookManager()


async def emit_hook(event: HookEvent) -> None:
    """Dispara un evento; reutilizable desde el loop, el contexto y la TUI."""
    await hook_manager.emit(event)
