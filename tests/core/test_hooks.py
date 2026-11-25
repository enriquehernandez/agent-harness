import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.harness import hooks as hooks_module
from app.core.harness.hooks import (
    HookEvent, HookManager, HookOutcome, HookRegistry, emit_hook,
)


def _fake_process(returncode=0, stderr=b"", stdout=b"", communicate=None):
    process = MagicMock()
    process.returncode = returncode
    process.communicate = AsyncMock(
        return_value=(stdout, stderr)) if communicate is None else communicate
    process.kill = MagicMock()
    process.wait = AsyncMock()
    return process


def _write_config(path: Path, config: dict) -> Path:
    path.write_text(json.dumps(config), encoding="utf-8")
    return path


def test_hook_event_payload_with_all_fields():
    event = HookEvent(
        hook_event_name="PreToolUse",
        session_id="sesion-1",
        cwd="/tmp/proyecto",
        tool_name="edit_file",
        tool_input={"path": "app.py"},
        success=False,
        trigger="auto",
        agent_name="reviewer",
        agent_depth=2,
        prompt="Revisa esto",
    )

    assert event.to_dict() == {
        "hook_event_name": "PreToolUse",
        "session_id": "sesion-1",
        "cwd": "/tmp/proyecto",
        "prompt": "Revisa esto",
        "tool_name": "edit_file",
        "tool_input": {"path": "app.py"},
        "success": False,
        "trigger": "auto",
        "agent_name": "reviewer",
        "agent_depth": 2,
    }


def test_hook_event_payload_minimal():
    assert HookEvent("Stop").to_dict() == {
        "hook_event_name": "Stop",
        "session_id": "",
        "cwd": os.getcwd(),
    }


def test_registry_load_filters_invalid_entries():
    config = {
        "hooks": {
            "PreToolUse": [
                "grupo no dict",
                {
                    "matcher": "edit_file",
                    "hooks": [
                        "handler no dict",
                        {"type": "http", "command": "ignorado"},
                        {"type": "command", "command": ""},
                        {"type": "command", "command": "echo pre"},
                    ],
                },
            ],
            "UnknownEvent": [
                {"hooks": [{"type": "command", "command": "echo no"}]}
            ],
            "Stop": "no es una lista",
        }
    }

    registry = HookRegistry()
    registry.load(config)

    assert registry.for_event("PreToolUse", "edit_file") == [
        {"matcher": "edit_file", "command": "echo pre"}
    ]
    assert registry.for_event("UnknownEvent") == []
    assert registry.for_event("Stop") == []


def test_registry_ignores_non_dict_hooks_block():
    registry = HookRegistry({"hooks": "mal"})

    assert registry.handlers == {}


def test_registry_non_tool_events_ignore_matcher():
    registry = HookRegistry({"hooks": {
        "Stop": [{"matcher": "irrelevante", "hooks": [
            {"command": "echo stop"}]}]
    }})

    assert registry.for_event("Stop") == [
        {"matcher": "irrelevante", "command": "echo stop"}
    ]


def test_registry_matcher_for_tool_events():
    registry = HookRegistry({"hooks": {
        "PreToolUse": [
            {"matcher": "", "hooks": [{"command": "todas"}]},
            {"matcher": " Edit | Write ", "hooks": [{"command": "ediciones"}]},
        ]
    }})

    assert [h["command"] for h in registry.for_event("PreToolUse", "Edit")] == [
        "todas", "ediciones"]
    assert [h["command"] for h in registry.for_event("PreToolUse", "Bash")] == [
        "todas"]
    assert [h["command"] for h in registry.for_event("PreToolUse")] == ["todas"]


def test_registry_disable_all_hooks():
    registry = HookRegistry({"disableAllHooks": True, "hooks": {
        "Stop": [{"hooks": [{"command": "echo stop"}]}]
    }})

    assert registry.for_event("Stop") == []


def test_manager_reload_missing_config(tmp_path):
    manager = HookManager(config_file=tmp_path / "hooks.json")

    assert manager.registry.for_event("Stop") == []


def test_manager_reload_invalid_json(tmp_path):
    config_file = tmp_path / "hooks.json"
    config_file.write_text("{invalid", encoding="utf-8")

    with patch.object(hooks_module.logger, "warning") as warn:
        manager = HookManager(config_file=config_file)

    assert manager.registry.for_event("Stop") == []
    warn.assert_called_once()


def test_manager_reload_non_dict_config(tmp_path):
    config_file = tmp_path / "hooks.json"
    config_file.write_text("[]", encoding="utf-8")

    manager = HookManager(config_file=config_file)

    assert manager.registry.for_event("Stop") == []


def test_manager_reload_valid_config_and_explicit_registry(tmp_path):
    config_file = _write_config(tmp_path / "hooks.json", {"hooks": {
        "Stop": [{"hooks": [{"command": "echo stop"}]}]
    }})
    registry = HookRegistry()

    manager = HookManager(config_file=config_file, registry=registry, timeout=5)

    assert manager.registry is registry
    assert manager.timeout == 5
    assert registry.for_event("Stop")[0]["command"] == "echo stop"


@pytest.mark.asyncio
async def test_manager_emits_event_as_json_on_stdin(tmp_path):
    config_file = _write_config(tmp_path / "hooks.json", {"hooks": {
        "PreToolUse": [{"matcher": "edit_file", "hooks": [
            {"command": "hook-cmd"}]}]
    }})
    manager = HookManager(config_file=config_file)
    process = _fake_process()
    event = HookEvent("PreToolUse", tool_name="edit_file",
                      tool_input={"path": "app.py"}, cwd=str(tmp_path))

    with patch("app.core.harness.hooks.asyncio.create_subprocess_shell",
               new=AsyncMock(return_value=process)) as spawn:
        await manager.emit(event)

    spawn.assert_awaited_once()
    assert spawn.await_args.args[0] == "hook-cmd"
    assert spawn.await_args.kwargs["cwd"] == str(tmp_path)
    payload = json.loads(process.communicate.await_args.args[0].decode("utf-8"))
    assert payload["hook_event_name"] == "PreToolUse"
    assert payload["tool_input"] == {"path": "app.py"}
    assert payload["cwd"] == str(tmp_path)


@pytest.mark.asyncio
async def test_manager_logs_nonzero_exit(tmp_path):
    config_file = _write_config(tmp_path / "hooks.json", {"hooks": {
        "Stop": [{"hooks": [{"command": "falla"}]}]
    }})
    manager = HookManager(config_file=config_file)

    with patch("app.core.harness.hooks.asyncio.create_subprocess_shell",
               new=AsyncMock(return_value=_fake_process(2, b"motivo"))):
        with patch.object(hooks_module.logger, "warning") as warn:
            await manager.emit(HookEvent("Stop"))

    assert "falla" in warn.call_args[0][0]


@pytest.mark.asyncio
async def test_manager_survives_spawn_error(tmp_path):
    config_file = _write_config(tmp_path / "hooks.json", {"hooks": {
        "Stop": [{"hooks": [{"command": "no-existe"}]}]
    }})
    manager = HookManager(config_file=config_file)

    with patch("app.core.harness.hooks.asyncio.create_subprocess_shell",
               new=AsyncMock(side_effect=OSError("sin shell"))):
        with patch.object(hooks_module.logger, "warning") as warn:
            await manager.emit(HookEvent("Stop"))

    assert "no-existe" in warn.call_args[0][0]


@pytest.mark.asyncio
async def test_manager_kills_process_on_timeout(tmp_path):
    config_file = _write_config(tmp_path / "hooks.json", {"hooks": {
        "Stop": [{"hooks": [{"command": "lento"}]}]
    }})
    manager = HookManager(config_file=config_file)
    process = _fake_process(
        returncode=None,
        communicate=AsyncMock(side_effect=asyncio.TimeoutError),
    )

    with patch("app.core.harness.hooks.asyncio.create_subprocess_shell",
               new=AsyncMock(return_value=process)):
        with patch.object(hooks_module.logger, "warning") as warn:
            await manager.emit(HookEvent("Stop"))

    process.kill.assert_called_once()
    process.wait.assert_awaited_once()
    assert "lento" in warn.call_args[0][0]


@pytest.mark.asyncio
async def test_manager_timeout_does_not_kill_finished_process(tmp_path):
    config_file = _write_config(tmp_path / "hooks.json", {"hooks": {
        "Stop": [{"hooks": [{"command": "casi"}]}]
    }})
    manager = HookManager(config_file=config_file)
    process = _fake_process(
        communicate=AsyncMock(side_effect=asyncio.TimeoutError),
    )

    with patch("app.core.harness.hooks.asyncio.create_subprocess_shell",
               new=AsyncMock(return_value=process)):
        with patch.object(hooks_module.logger, "warning"):
            await manager.emit(HookEvent("Stop"))

    process.kill.assert_not_called()


@pytest.mark.asyncio
async def test_emit_hook_delegates_to_module_manager():
    event = HookEvent("Stop")

    with patch.object(hooks_module, "hook_manager", new_callable=AsyncMock) as manager:
        await emit_hook(event)

    manager.emit.assert_awaited_once_with(event)


def test_hook_outcome_defaults_to_allow():
    outcome = HookOutcome()

    assert outcome.denied is False
    assert outcome.reason == ""


@pytest.mark.asyncio
@pytest.mark.parametrize("stderr,expected", [
    (b"No se pueden borrar archivos", "No se pueden borrar archivos"),
    (b"", "El hook bloqueó la acción (código 2)."),
])
async def test_manager_denies_on_exit_code_two(tmp_path, stderr, expected):
    config_file = _write_config(tmp_path / "hooks.json", {"hooks": {
        "PreToolUse": [{"matcher": "bash", "hooks": [
            {"command": "guardia"}]}]
    }})
    manager = HookManager(config_file=config_file)

    with patch("app.core.harness.hooks.asyncio.create_subprocess_shell",
               new=AsyncMock(return_value=_fake_process(2, stderr))):
        with patch.object(hooks_module.logger, "warning"):
            outcome = await manager.emit(HookEvent(
                "PreToolUse", tool_name="bash",
                tool_input={"command": "rm archivo.txt"}))

    assert outcome.denied is True
    assert outcome.reason == expected


@pytest.mark.asyncio
async def test_manager_denies_on_json_permission_decision(tmp_path):
    payload = json.dumps({
        "hookSpecificOutput": {
            "permissionDecision": "deny",
            "permissionDecisionReason": "Borrado prohibido",
        }
    }).encode("utf-8")
    config_file = _write_config(tmp_path / "hooks.json", {"hooks": {
        "PreToolUse": [{"hooks": [{"command": "guardia"}]}]
    }})
    manager = HookManager(config_file=config_file)

    with patch("app.core.harness.hooks.asyncio.create_subprocess_shell",
               new=AsyncMock(return_value=_fake_process(stdout=payload))):
        outcome = await manager.emit(HookEvent("PreToolUse", tool_name="bash"))

    assert outcome.denied is True
    assert outcome.reason == "Borrado prohibido"


@pytest.mark.asyncio
async def test_manager_denies_on_generic_block_decision(tmp_path):
    payload = json.dumps({
        "decision": "block", "reason": "Bloqueado por política"}).encode("utf-8")
    config_file = _write_config(tmp_path / "hooks.json", {"hooks": {
        "Stop": [{"hooks": [{"command": "guardia"}]}]
    }})
    manager = HookManager(config_file=config_file)

    with patch("app.core.harness.hooks.asyncio.create_subprocess_shell",
               new=AsyncMock(return_value=_fake_process(stdout=payload))):
        outcome = await manager.emit(HookEvent("Stop"))

    assert outcome.denied is True
    assert outcome.reason == "Bloqueado por política"


@pytest.mark.asyncio
@pytest.mark.parametrize("stdout", [
    b"",
    b"no es json",
    b"\xff",
    b"{}",
    json.dumps({"hookSpecificOutput": {
        "permissionDecision": "allow"}}).encode("utf-8"),
])
async def test_manager_allows_when_there_is_no_deny(tmp_path, stdout):
    config_file = _write_config(tmp_path / "hooks.json", {"hooks": {
        "PreToolUse": [{"hooks": [{"command": "observador"}]}]
    }})
    manager = HookManager(config_file=config_file)

    with patch("app.core.harness.hooks.asyncio.create_subprocess_shell",
               new=AsyncMock(return_value=_fake_process(stdout=stdout))):
        outcome = await manager.emit(HookEvent("PreToolUse", tool_name="bash"))

    assert outcome.denied is False


@pytest.mark.asyncio
async def test_manager_prefers_deny_among_hooks(tmp_path):
    deny_payload = json.dumps({
        "hookSpecificOutput": {
            "permissionDecision": "deny",
            "permissionDecisionReason": "El segundo_hook dice no",
        }
    }).encode("utf-8")
    config_file = _write_config(tmp_path / "hooks.json", {"hooks": {
        "PreToolUse": [{"hooks": [
            {"command": "permite"},
            {"command": "niega"},
        ]}]
    }})
    manager = HookManager(config_file=config_file)
    processes = [
        _fake_process(stdout=b""),
        _fake_process(stdout=deny_payload),
    ]

    with patch("app.core.harness.hooks.asyncio.create_subprocess_shell",
               new=AsyncMock(side_effect=processes)) as spawn:
        with patch.object(hooks_module.logger, "warning"):
            outcome = await manager.emit(HookEvent(
                "PreToolUse", tool_name="bash"))

    assert spawn.await_count == 2
    assert outcome.denied is True
    assert outcome.reason == "El segundo_hook dice no"


@pytest.mark.asyncio
async def test_manager_stops_after_first_deny(tmp_path):
    config_file = _write_config(tmp_path / "hooks.json", {"hooks": {
        "Stop": [{"hooks": [
            {"command": "niega"},
            {"command": "no_deberia_ejecutarse"},
        ]}]
    }})
    manager = HookManager(config_file=config_file)

    with patch("app.core.harness.hooks.asyncio.create_subprocess_shell",
               new=AsyncMock(return_value=_fake_process(2, b"alto"))) as spawn:
        with patch.object(hooks_module.logger, "warning"):
            outcome = await manager.emit(HookEvent("Stop"))

    assert spawn.await_count == 1
    assert outcome.denied is True


REPO_ROOT = Path(__file__).resolve().parents[2]
NO_DELETE_SCRIPT = REPO_ROOT / ".harness" / "hooks" / "no_delete.py"


def _run_no_delete(command: str, tool_name: str = "bash", cwd: Path | None = None):
    cwd = cwd or REPO_ROOT
    payload = json.dumps({
        "hook_event_name": "PreToolUse",
        "cwd": str(cwd),
        "tool_name": tool_name,
        "tool_input": {"command": command},
    })
    return subprocess.run(
        [sys.executable, str(NO_DELETE_SCRIPT)],
        input=payload, capture_output=True, text=True, cwd=cwd,
        check=False,
    )


@pytest.mark.parametrize("command", [
    "rm archivo.txt",
    "rm -rf ./carpeta",
    "rmdir vieja",
    "unlink archivo.txt",
    "shred -u secreto.txt",
    "git rm -f archivo.txt",
    "find . -name '*.py' -delete",
    "python3 -c \"import os; os.remove('x.txt')\"",
    "python3 -c \"from pathlib import Path; Path('x').unlink()\"",
    "ls && rm -f temporal.txt",
])
def test_no_delete_script_denies_destructive_commands(tmp_path, command):
    result = _run_no_delete(command, cwd=tmp_path)

    assert result.returncode == 0
    decision = json.loads(result.stdout)["hookSpecificOutput"]
    assert decision["permissionDecision"] == "deny"
    assert "eliminar" in decision["permissionDecisionReason"].lower()


@pytest.mark.parametrize("command,tool_name", [
    ("ls -la", "bash"),
    ("git status", "bash"),
    ("echo rm no es borrado", "write_file"),
])
def test_no_delete_script_allows_safe_commands(command, tool_name):
    result = _run_no_delete(command, tool_name=tool_name)

    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_no_delete_script_survives_invalid_payload():
    result = subprocess.run(
        [sys.executable, str(NO_DELETE_SCRIPT)],
        input="no es json", capture_output=True, text=True,
        cwd=REPO_ROOT, check=False,
    )

    assert result.returncode == 0
    assert result.stdout.strip() == ""


AUDIT_SCRIPT = REPO_ROOT / ".harness" / "hooks" / "audit.py"


def _run_audit(event: dict, cwd: Path):
    return subprocess.run(
        [sys.executable, str(AUDIT_SCRIPT)],
        input=json.dumps(event), capture_output=True, text=True,
        cwd=cwd, check=False,
    )


@pytest.mark.parametrize("tool,tool_input,success,expected", [
    ("edit_file", {"path": "app.py"}, True,
     "tool=edit_file success=True path=app.py"),
    ("write_file", {"path": "nuevo.py"}, False,
     "tool=write_file success=False path=nuevo.py"),
])
def test_audit_script_records_edits(
        tmp_path, tool, tool_input, success, expected):
    result = _run_audit({
        "hook_event_name": "PostToolUse", "tool_name": tool,
        "tool_input": tool_input, "success": success,
    }, tmp_path)

    assert result.returncode == 0
    log = (tmp_path / ".harness" / "hooks" / "audit.log").read_text(
        encoding="utf-8")
    assert expected in log


def test_audit_script_ignores_bash(tmp_path):
    """Los bloqueos de bash los registra `no_delete.py` vía `log_event()`."""
    _run_audit({
        "hook_event_name": "PostToolUse", "tool_name": "bash",
        "tool_input": {"command": "rm temporal-hook.txt"}, "success": False,
    }, tmp_path)

    assert not (tmp_path / ".harness" / "hooks" / "audit.log").exists()


def test_audit_script_survives_invalid_payload(tmp_path):
    result = subprocess.run(
        [sys.executable, str(AUDIT_SCRIPT)],
        input="no es json", capture_output=True, text=True,
        cwd=tmp_path, check=False,
    )

    assert result.returncode == 0
    assert not (tmp_path / ".harness" / "hooks" / "audit.log").exists()


def test_no_delete_logs_denial_through_audit_module(tmp_path):
    """El guardia usa el registrador compartido y deja una sola línea."""
    result = _run_no_delete("rm temporal-hook.txt", cwd=tmp_path)

    assert json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"
    lines = (tmp_path / ".harness" / "hooks" / "audit.log").read_text(
        encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert "tool=bash success=False command=rm temporal-hook.txt" in lines[0]


def test_hooks_config_has_no_duplicate_bash_audit():
    config = json.loads(
        (REPO_ROOT / ".harness" / "hooks.json").read_text(encoding="utf-8"))

    matchers = [group.get("matcher", "") for group in config["hooks"]["PostToolUse"]]
    assert "bash" not in matchers


def test_settings_exposes_hooks_file():
    from app.core.config import settings
    from app.core.harness.hooks import HookManager

    assert HookManager().config_file == settings.hooks_file
