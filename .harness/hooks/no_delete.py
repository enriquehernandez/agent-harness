#!/usr/bin/env python3
"""Hook PreToolUse: bloquea comandos `bash` que eliminan archivos del proyecto.

Recibe el HookEvent como JSON por stdin. Si detecta una orden destructiva,
devuelve por stdout la decisión ``deny`` de Claude Code con el motivo; si no,
no escribe nada y la herramienta sigue su curso.
"""

import json
import re
import sys

# Detecta borrados directos, borrados con git/find y borrados desde Python.
# Se aplica solo a `bash`; el análisis es conservador: ante la duda, bloquea.
DELETE_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE | re.MULTILINE)
    for pattern in (
        r"(?:^|[;&|]\s*)(?:/usr/bin/)?rm\b",
        r"(?:^|[;&|]\s*)(?:/usr/bin/)?rmdir\b",
        r"(?:^|[;&|]\s*)(?:/usr/bin/)?unlink\b",
        r"(?:^|[;&|]\s*)(?:/usr/bin/)?shred\b",
        r"(?:^|[;&|]\s*)git\s+rm\b",
        r"\bfind\b[^\n]*\s-delete\b",
        r"\bos\.remove\s*\(",
        r"\bos\.unlink\s*\(",
        r"\bPath\([^)]*\)\.unlink\s*\(",
        r"\bshutil\.rmtree\s*\(",
    )
)


def deny_decision(command: str) -> dict:
    return {
        "hookSpecificOutput": {
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                f"🚫 Este hook prohíbe eliminar archivos del proyecto. "
                f"Comando bloqueado: {command}"
            ),
        }
    }


def main() -> None:
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return

    if not isinstance(event, dict) or event.get("tool_name") != "bash":
        return

    tool_input = event.get("tool_input") or {}
    command = tool_input.get("command", "")
    if not isinstance(command, str):
        return

    if any(pattern.search(command) for pattern in DELETE_PATTERNS):
        sys.stdout.write(json.dumps(deny_decision(command), ensure_ascii=False))


if __name__ == "__main__":
    main()
