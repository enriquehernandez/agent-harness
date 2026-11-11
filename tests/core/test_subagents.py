import pytest
from unittest.mock import AsyncMock, patch
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
