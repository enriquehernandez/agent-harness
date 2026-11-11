import difflib
import json
import fnmatch
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Awaitable


class Decision(str, Enum):
    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"


@dataclass
class PermissionGate:
    """Manages tool permissions."""

    policies: dict[str, Decision] = field(default_factory=dict)
    session_allowed: set[str] = field(default_factory=set)
    ask_user: Callable[[str, str, dict, str | None],
                       Awaitable[str]] | None = None
    persist_file: Path = field(
        default_factory=lambda: Path(".harness_permissions.json"))

    def __post_init__(self):
        if not self.policies:
            self.policies = {
                "read_file": Decision.ALLOW,
                "read_text_file": Decision.ALLOW,
                "list_dir": Decision.ALLOW,
                "list_directory": Decision.ALLOW,
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

    def _save_persisted_permissions(self):
        data = {"session_allowed": list(self.session_allowed)}
        try:
            with open(self.persist_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving permissions: {e}")

    def _get_signature(self, tool_name: str, arguments: dict) -> str:
        if tool_name == "bash":
            return f"bash:{arguments.get('command', '').strip()}"
        elif tool_name in ("write_file", "edit_file"):
            return f"{tool_name}:{arguments.get('path', '')}"
        return tool_name

    def _is_allowed(self, signature: str) -> bool:
        for allowed in self.session_allowed:
            if fnmatch.fnmatch(signature, allowed):
                return True
        return False

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
            return "".join(difflib.unified_diff(
                old_content.splitlines(keepends=True),
                new_content.splitlines(keepends=True),
                fromfile=f"a/{args['path']}",
                tofile=f"b/{args['path']}",
                lineterm=""
            ))

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
                if old_text in new_content:
                    new_content = new_content.replace(old_text, new_text)
                else:
                    return f"⚠️ Text to replace not found: {old_text[:20]}..."

            return "".join(difflib.unified_diff(
                old_content.splitlines(keepends=True),
                new_content.splitlines(keepends=True),
                fromfile=f"a/{args['path']}",
                tofile=f"b/{args['path']}",
                lineterm=""
            ))

        return None

    async def check(self, tool_name: str, arguments: dict) -> Decision:
        signature = self._get_signature(tool_name, arguments)

        if self._is_allowed(signature):
            return Decision.ALLOW

        policy = self.policies.get(tool_name, Decision.ASK)
        if policy == Decision.ALLOW:
            return Decision.ALLOW
        if policy == Decision.DENY:
            return Decision.DENY

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
