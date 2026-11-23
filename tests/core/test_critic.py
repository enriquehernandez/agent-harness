import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.tools.critic import CriticTool
from app.core.llm.base import LLMResponse


@pytest.mark.asyncio
async def test_critic_approves():
    """Verifica que el crítico aprueba una respuesta válida."""
    mock_llm = MagicMock()
    mock_llm.chat = AsyncMock(return_value=LLMResponse(content="APPROVED"))

    tool = CriticTool(llm=mock_llm)
    result = await tool.run("print('hola')", "No uses print")

    assert result.success is True
    assert result.content == "APPROVED"


@pytest.mark.asyncio
async def test_critic_rejects():
    """Verifica que el crítico rechaza una respuesta inválida."""
    mock_llm = MagicMock()
    mock_llm.chat = AsyncMock(return_value=LLMResponse(
        content="REJECTED\nUsa logger en lugar de print."))

    tool = CriticTool(llm=mock_llm)
    result = await tool.run("print('hola')", "No uses print")

    assert result.success is True
    assert result.content.startswith("REJECTED")
    assert "Usa logger" in result.content


@pytest.mark.asyncio
async def test_critic_llm_error():
    """Verifica que el crítico maneja errores del LLM."""
    mock_llm = MagicMock()
    mock_llm.chat = AsyncMock(side_effect=Exception("Error de API"))

    tool = CriticTool(llm=mock_llm)
    result = await tool.run("print('hola')", "No uses print")

    assert result.success is False
    assert "Error en el crítico" in result.error
