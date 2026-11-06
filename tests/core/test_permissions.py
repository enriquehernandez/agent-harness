import pytest
from app.core.harness.permissions import PermissionGate, Decision


@pytest.mark.asyncio
async def test_permission_gate_allow():
    gate = PermissionGate()
    gate.policies = {"safe_tool": Decision.ALLOW}

    decision = await gate.check("safe_tool", {})
    assert decision == Decision.ALLOW


@pytest.mark.asyncio
async def test_permission_gate_deny():
    gate = PermissionGate()
    gate.policies = {"bad_tool": Decision.DENY}

    decision = await gate.check("bad_tool", {})
    assert decision == Decision.DENY


@pytest.mark.asyncio
async def test_permission_gate_ask_deny_no_ui():
    """Si pide ASK pero no hay UI (ask_user), debe denegar por seguridad."""
    gate = PermissionGate()
    gate.policies = {"danger_tool": Decision.ASK}

    decision = await gate.check("danger_tool", {})
    assert decision == Decision.DENY


@pytest.mark.asyncio
async def test_permission_gate_ask_user_yes():
    """Simula que el usuario responde 'y'."""
    async def mock_ask_user(tool, title, args):
        return "y"

    gate = PermissionGate(ask_user=mock_ask_user)
    gate.policies = {"danger_tool": Decision.ASK}

    decision = await gate.check("danger_tool", {})
    assert decision == Decision.ALLOW


@pytest.mark.asyncio
async def test_permission_gate_ask_user_always():
    """Simula que el usuario responde 'a' (always)."""
    async def mock_ask_user(tool, title, args):
        return "a"

    gate = PermissionGate(ask_user=mock_ask_user)
    gate.policies = {"danger_tool": Decision.ASK}

    # Primera vez: Pregunta
    decision1 = await gate.check("danger_tool", {})
    assert decision1 == Decision.ALLOW

    # Segunda vez: Ya no pregunta, recuerda el "always"
    decision2 = await gate.check("danger_tool", {})
    assert decision2 == Decision.ALLOW
    assert "danger_tool" in gate.session_allowed


@pytest.mark.asyncio
async def test_permission_gate_ask_user_no():
    """Simula que el usuario responde 'n'."""
    async def mock_ask_user(tool, title, args):
        return "n"

    gate = PermissionGate(ask_user=mock_ask_user)
    gate.policies = {"danger_tool": Decision.ASK}

    decision = await gate.check("danger_tool", {})
    assert decision == Decision.DENY
