#!/usr/bin/env python3
"""Registro central de hooks.

Expone ``log_event()`` para que cualquier hook registre sus decisiones y,
además, actúa como hook ``PostToolUse`` que registra ``edit_file``/``write_file``.
Así hay un único formato de línea y un único archivo, ``audit.log``.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

AUDITED_TOOLS = {"edit_file", "write_file"}


def log_event(event: dict, root: Path | None = None) -> None:
    """Añade una línea a ``.harness/hooks/audit.log``.

    Acepta un ``HookEvent`` serializado o un dict con ``tool_name``,
    ``success`` y ``tool_input``. Para ``bash`` se registra el comando; para
    el resto de herramientas, la ruta del archivo.
    """
    tool = event.get("tool_name", "")
    success = event.get("success")
    tool_input = event.get("tool_input") or {}

    if tool == "bash":
        command = tool_input.get("command", "")
        if not isinstance(command, str):
            command = str(command)
        detail = "command=" + command.replace("\r", "\\r").replace("\n", "\\n")
    else:
        detail = "path=" + str(tool_input.get("path", ""))

    base = root or Path(event.get("cwd") or Path.cwd())
    log_file = base / ".harness" / "hooks" / "audit.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")

    with log_file.open("a", encoding="utf-8") as handle:
        handle.write(
            f"{timestamp} tool={tool} success={success} {detail}\n")


def main() -> None:
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return

    if not isinstance(event, dict):
        return
    if event.get("tool_name") not in AUDITED_TOOLS:
        return

    log_event(event)


if __name__ == "__main__":
    main()
