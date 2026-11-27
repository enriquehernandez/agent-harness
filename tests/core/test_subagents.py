import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.core.harness.subagents import DelegateTool
from app.core.llm.base import LLMResponse


@pytest.mark.asyncio
async def test_delegate_tool_success(fake_llm, basic_registry):
    """Cubre el flujo exitoso del subagente."""
    tool = DelegateTool(
        name="delegate_test", description="Test", llm=fake_llm,
        tools=basic_registry, system_prompt="Test prompt"
    )
    fake_llm._responses = [LLMResponse(content="Subagent done")]
    result = await tool.run(task="Do something")
    assert result.success is True
    assert "Subagent done" in result.content


@pytest.mark.asyncio
async def test_delegate_tool_uses_parent_gate_state(
        fake_llm, basic_registry, tmp_path, monkeypatch):
    """El subagente comparte aprobaciones y políticas, sin auto-allow de tools."""
    from app.core.harness.permissions import Decision, PermissionGate

    monkeypatch.chdir(tmp_path)
    parent_gate = PermissionGate(ask_user=AsyncMock(return_value="n"))
    parent_gate.session_allowed.add("bash:ls")

    tool = DelegateTool(
        name="delegate_test", description="Test", llm=fake_llm,
        tools=basic_registry, system_prompt="Test prompt",
        permissions=parent_gate,
    )
    fake_llm._responses = [LLMResponse(content="Subagent done")]

    with patch("app.core.harness.subagents.AgentLoop") as MockLoop:
        MockLoop.return_value.run = AsyncMock(
            return_value=MagicMock(final_answer="Hecho"))
        await tool.run(task="Do something")

    gate = MockLoop.call_args.kwargs["permissions"]
    assert gate.session_allowed is parent_gate.session_allowed
    assert gate.ask_user is parent_gate.ask_user
    assert gate.policies == parent_gate.policies
    assert gate.policies["bash"] == Decision.ASK
    assert gate.policies["write_file"] == Decision.ASK
    assert "add" not in gate.policies
    assert await gate.check("bash", {"command": "ls"}) == Decision.ALLOW
    assert await gate.check("bash", {"command": "pwd"}) != Decision.ALLOW


@pytest.mark.asyncio
async def test_delegate_tool_denies_tools_without_ask_user(
        fake_llm, basic_registry, tmp_path, monkeypatch):
    """Sin usuario que responda, el gate hijo deniega en vez de auto-aprobar."""
    from app.core.harness.permissions import Decision, PermissionGate

    from app.core.harness.tool import FunctionTool

    monkeypatch.chdir(tmp_path)
    for name in ("bash", "write_file"):
        basic_registry.register(FunctionTool(
            name=name, description="", parameters_schema={},
            func=lambda **kwargs: "",
        ))
    parent_gate = PermissionGate(ask_user=None)

    tool = DelegateTool(
        name="delegate_test", description="Test", llm=fake_llm,
        tools=basic_registry, system_prompt="Test prompt",
        permissions=parent_gate,
    )
    fake_llm._responses = [LLMResponse(content="Subagent done")]

    with patch("app.core.harness.subagents.AgentLoop") as MockLoop:
        MockLoop.return_value.run = AsyncMock(
            return_value=MagicMock(final_answer="Hecho"))
        await tool.run(task="Do something")

    gate = MockLoop.call_args.kwargs["permissions"]
    assert await gate.check("bash", {"command": "ls"}) == Decision.DENY
    assert await gate.check("write_file", {"path": "app.py"}) == Decision.DENY


@pytest.mark.asyncio
async def test_delegate_tool_error(fake_llm, basic_registry):
    """Cubre el manejo de errores del subagente."""
    tool = DelegateTool(
        name="delegate_test", description="Test", llm=fake_llm,
        tools=basic_registry, system_prompt="Test prompt"
    )

    # Forzamos un error en el chat del LLM
    with patch.object(fake_llm, "chat", new_callable=AsyncMock) as mock_chat:
        mock_chat.side_effect = Exception("Simulated error")
        result = await tool.run(task="Fail")
        assert result.success is False
        assert "Simulated error" in result.error
