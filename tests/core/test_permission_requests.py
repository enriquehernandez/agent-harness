import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.harness.a2a.base import AgentCard
from app.core.harness.a2a.strategies.parallel import ParallelStrategy
from app.core.harness.permissions import (
    Decision,
    PermissionBroker,
    PermissionGate,
    PermissionReply,
    normalize_reply,
)
from app.core.harness.subagents import DelegateTool
from app.core.harness.tool import ToolRegistry


@pytest.fixture(autouse=True)
def isolated_permissions_file(tmp_path, monkeypatch):
    """Cada test usa un `.harness/permissions.json` propio."""
    monkeypatch.chdir(tmp_path)


async def _start_check(gate: PermissionGate, command: str = "ls") -> asyncio.Task:
    task = asyncio.create_task(gate.check("bash", {"command": command}))
    await asyncio.sleep(0)
    return task


def _queued_broker() -> PermissionBroker:
    """Broker con un suscriptor: simula a la TUI escuchando la cola."""
    broker = PermissionBroker()
    broker.add_listener(lambda request: None)
    return broker


def test_broker_rejects_unknown_unattended_policy():
    with pytest.raises(ValueError, match="unattended"):
        PermissionBroker(unattended="allow")


@pytest.mark.parametrize(
    "value,expected",
    [
        ("y", PermissionReply.ONCE),
        ("yes", PermissionReply.ONCE),
        ("once", PermissionReply.ONCE),
        ("a", PermissionReply.ALWAYS),
        ("always", PermissionReply.ALWAYS),
        ("siempre", PermissionReply.ALWAYS),
        ("n", PermissionReply.REJECT),
        ("no", PermissionReply.REJECT),
        ("reject", PermissionReply.REJECT),
        (PermissionReply.ONCE, PermissionReply.ONCE),
    ],
)
def test_normalize_reply_aliases(value, expected):
    assert normalize_reply(value) == expected


def test_normalize_reply_rejects_unknown_value():
    with pytest.raises(ValueError, match="once"):
        normalize_reply("quizá")


@pytest.mark.asyncio
async def test_once_approves_only_the_current_request(tmp_path):
    broker = _queued_broker()
    gate = PermissionGate(broker=broker, persist_file=tmp_path / "permissions.json")

    first = await _start_check(gate)
    request = broker.list_pending()[0]
    assert request.request_id.startswith("req-")
    assert request.session_id == "main"
    assert request.tool_name == "bash"
    assert request.signature == "bash:ls"
    assert request.resources == ("bash:ls",)
    assert request.patterns == ("bash:ls",)

    assert broker.reply(request.request_id, "y") is True
    assert await asyncio.wait_for(first, 1) == Decision.ALLOW
    assert gate.session_allowed == set()
    assert broker.list_pending() == []

    second = await _start_check(gate)
    second_request = broker.list_pending()[0]
    assert second_request.request_id != request.request_id
    assert broker.reply(second_request.request_id, "once") is True
    assert await asyncio.wait_for(second, 1) == Decision.ALLOW
    assert gate.session_allowed == set()


@pytest.mark.asyncio
async def test_always_persists_literal_signature_and_survives_restart(tmp_path):
    persist_file = tmp_path / "permissions.json"
    broker = _queued_broker()
    gate = PermissionGate(broker=broker, persist_file=persist_file)

    task = await _start_check(gate, "grep *.log")
    request = broker.list_pending()[0]
    assert broker.reply(request.request_id, "a") is True
    assert await asyncio.wait_for(task, 1) == Decision.ALLOW

    assert gate.session_allowed == {"bash:grep *.log"}
    assert json.loads(persist_file.read_text(encoding="utf-8"))["session_allowed"] == [
        "bash:grep *.log"
    ]

    restarted = PermissionGate(
        broker=PermissionBroker(), persist_file=persist_file)
    assert await restarted.check("bash", {"command": "grep *.log"}) == Decision.ALLOW
    assert await restarted.check("bash", {"command": "grep secret.log"}) == Decision.DENY
    assert restarted.broker.list_pending() == []


@pytest.mark.asyncio
async def test_configured_deny_wins_over_approved_signature():
    gate = PermissionGate(broker=PermissionBroker())
    gate.policies["bash"] = Decision.DENY
    gate.session_allowed.add("bash:ls")

    assert await gate.check("bash", {"command": "ls"}) == Decision.DENY
    assert gate.broker.list_pending() == []


@pytest.mark.asyncio
async def test_deny_set_while_request_is_pending_wins_over_always():
    broker = _queued_broker()
    gate = PermissionGate(broker=broker)

    task = await _start_check(gate)
    request = broker.list_pending()[0]
    gate.policies["bash"] = Decision.DENY
    assert broker.reply(request.request_id, "always") is True

    assert await asyncio.wait_for(task, 1) == Decision.DENY
    assert gate.session_allowed == set()


@pytest.mark.asyncio
async def test_reject_closes_pending_requests_of_the_same_session():
    broker = _queued_broker()
    parent = PermissionGate(broker=broker, session_id="main")
    reviewer_a = parent.child(session_id="a2a:reviewer")
    reviewer_b = parent.child(session_id="a2a:reviewer")

    first = await _start_check(reviewer_a, "pwd")
    second = await _start_check(reviewer_b, "ls")
    requests = broker.list_pending()
    assert {request.session_id for request in requests} == {"a2a:reviewer"}
    assert len(requests) == 2

    target = next(request for request in requests if request.signature == "bash:pwd")
    assert broker.reply(target.request_id, "n") is True

    assert await asyncio.wait_for(first, 1) == Decision.DENY
    assert await asyncio.wait_for(second, 1) == Decision.DENY
    assert broker.list_pending() == []
    assert broker.is_rejected("a2a:reviewer") is True

    blocked = await _start_check(reviewer_a)
    assert await asyncio.wait_for(blocked, 1) == Decision.DENY
    assert broker.list_pending() == []


@pytest.mark.asyncio
async def test_reject_does_not_block_other_sessions():
    broker = _queued_broker()
    parent = PermissionGate(broker=broker, session_id="main")
    reviewer = parent.child(session_id="a2a:reviewer")
    writer = parent.child(session_id="a2a:writer")

    first = await _start_check(reviewer)
    other = await _start_check(writer, "pwd")
    requests = broker.list_pending()
    target = next(request for request in requests if request.session_id == "a2a:reviewer")

    assert broker.reply(target.request_id, PermissionReply.REJECT) is True
    assert await asyncio.wait_for(first, 1) == Decision.DENY
    assert broker.list_pending("a2a:writer")[0].signature == "bash:pwd"
    assert broker.is_rejected("a2a:writer") is False

    request = broker.list_pending("a2a:writer")[0]
    assert broker.reply(request.request_id, "y") is True
    assert await asyncio.wait_for(other, 1) == Decision.ALLOW


def test_reply_to_missing_request_returns_false():
    broker = PermissionBroker()
    assert broker.reply("req-inexistente", "once") is False


@pytest.mark.asyncio
async def test_headless_broker_denies_without_auto_approval():
    gate = PermissionGate(broker=PermissionBroker())

    assert await gate.check("bash", {"command": "rm -rf /"}) == Decision.DENY
    assert gate.session_allowed == set()


@pytest.mark.asyncio
async def test_headless_pending_policy_waits_without_approving():
    broker = PermissionBroker(unattended="pending")
    gate = PermissionGate(broker=broker)

    task = asyncio.create_task(gate.check("bash", {"command": "ls"}))
    await asyncio.sleep(0)
    assert len(broker.list_pending()) == 1

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(asyncio.shield(task), 0.01)

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert broker.list_pending() == []
    assert gate.session_allowed == set()


@pytest.mark.asyncio
async def test_broker_notifies_sync_and_async_listeners():
    broker = PermissionBroker()
    seen = []

    def sync_listener(request):
        seen.append(("sync", request.request_id))

    async def async_listener(request):
        seen.append(("async", request.request_id))

    broker.add_listener(sync_listener)
    broker.add_listener(async_listener)
    gate = PermissionGate(broker=broker)

    task = await _start_check(gate)
    request = broker.list_pending()[0]
    assert seen == [("sync", request.request_id), ("async", request.request_id)]

    assert broker.reply(request.request_id, "once") is True
    assert await asyncio.wait_for(task, 1) == Decision.ALLOW


def test_child_gate_shares_broker_and_accepts_session_override():
    broker = PermissionBroker()
    parent = PermissionGate(broker=broker, session_id="main")

    child = parent.child(allow=["read_file"], session_id="a2a:analyst")
    default_child = parent.child()

    assert child.broker is broker
    assert child.session_id == "a2a:analyst"
    assert child.policies["read_file"] == Decision.ALLOW
    assert child.session_allowed is parent.session_allowed
    assert default_child.session_id == "main"


@pytest.mark.asyncio
async def test_parallel_subagents_get_distinct_sessions_and_share_broker():
    broker = _queued_broker()
    parent = PermissionGate(broker=broker)
    registry = {
        name: AgentCard(
            name=name,
            description="",
            system_prompt="",
            tools=ToolRegistry(),
        )
        for name in ("analyst", "writer")
    }
    strategy = ParallelStrategy(
        MagicMock(), registry, parent, agents_to_run=["analyst", "writer"])

    with patch("app.core.harness.a2a.strategies.parallel.AgentLoop") as mock_loop:
        mock_loop.return_value.run = AsyncMock(
            return_value=MagicMock(final_answer="Hecho"))
        await strategy.execute("Tarea")

    gates = [call.kwargs["permissions"] for call in mock_loop.call_args_list]
    assert [gate.session_id for gate in gates] == ["a2a:analyst", "a2a:writer"]
    assert all(gate.broker is broker for gate in gates)

    tasks = [asyncio.create_task(gate.check("bash", {"command": "ls"})) for gate in gates]
    await asyncio.sleep(0)
    requests = broker.list_pending()
    assert {request.session_id for request in requests} == {
        "a2a:analyst", "a2a:writer"}

    for request in requests:
        assert broker.reply(request.request_id, "once") is True
    assert await asyncio.wait_for(asyncio.gather(*tasks), 1) == [
        Decision.ALLOW, Decision.ALLOW
    ]


@pytest.mark.asyncio
async def test_delegate_tool_uses_its_own_session_id():
    broker = PermissionBroker()
    parent = PermissionGate(broker=broker)
    tool = DelegateTool(
        name="reviewer",
        description="",
        llm=MagicMock(),
        tools=ToolRegistry(),
        system_prompt="",
        permissions=parent,
    )

    with patch("app.core.harness.subagents.AgentLoop") as mock_loop:
        mock_loop.return_value.run = AsyncMock(
            return_value=MagicMock(final_answer="Hecho"))
        await tool.run("Revisa")

    gate = mock_loop.call_args.kwargs["permissions"]
    assert gate.session_id == "delegate:reviewer"
    assert gate.broker is broker
