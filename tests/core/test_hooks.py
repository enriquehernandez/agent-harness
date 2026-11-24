import asyncio
import json
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.harness import hooks as hooks_module
from app.core.harness.hooks import HookEvent, HookManager, HookRegistry, emit_hook


def _fake_process(returncode=0, stderr=b"", communicate=None):
    process = MagicMock()
    process.returncode = returncode
    process.communicate = AsyncMock(
        return_value=(b"", stderr)) if communicate is None else communicate
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


def test_settings_exposes_hooks_file():
    from app.core.config import settings
    from app.core.harness.hooks import HookManager

    assert HookManager().config_file == settings.hooks_file
