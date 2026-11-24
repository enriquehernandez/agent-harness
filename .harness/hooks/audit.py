#!/usr/bin/env python3
"""Hook PostToolUse: registra las ediciones de archivos en audit.log."""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

AUDITED_TOOLS = {"edit_file", "write_file"}


def main() -> None:
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        return

    tool = event.get("tool_name", "")
    if tool not in AUDITED_TOOLS:
        return

    root = Path(event.get("cwd") or Path.cwd())
    log_file = root / ".harness" / "hooks" / "audit.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)

    tool_input = event.get("tool_input") or {}
    path = tool_input.get("path", "")
    success = event.get("success")
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")

    with log_file.open("a", encoding="utf-8") as handle:
        handle.write(
            f"{timestamp} tool={tool} success={success} path={path}\n"
        )


if __name__ == "__main__":
    main()
