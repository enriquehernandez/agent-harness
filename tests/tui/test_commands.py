from unittest.mock import patch

import pytest
from app.tui.commands import handle_command
from app.core.harness.context import ContextManager


@pytest.mark.asyncio
async def test_cmd_help(capsys):
    ctx = ContextManager()
    state = {"provider": "fake"}

    handled = await handle_command("/help", ctx, state, None)
    assert handled is True
    captured = capsys.readouterr()
    assert "Comandos disponibles" in captured.out


@pytest.mark.asyncio
async def test_cmd_clear():
    ctx = ContextManager(system_prompt="sys")
    ctx.add_user("Hola")
    state = {"provider": "fake"}

    await handle_command("/clear", ctx, state, None)
    assert len(ctx.messages) == 1
    assert ctx.messages[0]["content"] == "sys"


@pytest.mark.asyncio
async def test_cmd_model_change():
    ctx = ContextManager()
    state = {"provider": "fake"}

    await handle_command("/model openrouter", ctx, state, None)
    assert state["provider"] == "openrouter"


@pytest.mark.asyncio
async def test_cmd_quit():
    with pytest.raises(SystemExit):
        await handle_command("/quit", None, {}, None)


@pytest.mark.asyncio
async def test_cmd_exit():
    with pytest.raises(SystemExit):
        await handle_command("/exit", None, {}, None)


@pytest.mark.asyncio
async def test_cmd_unknown():
    handled = await handle_command("/inventado", None, {}, None)
    assert handled is True


@pytest.mark.asyncio
async def test_cmd_tokens(capsys):
    from app.core.harness.context import ContextManager
    ctx = ContextManager()
    ctx.add_user("1234")
    # Mock llm para max_context_window

    class MockLLM:
        max_context_window = 100
    await handle_command("/tokens", ctx, {}, MockLLM())
    captured = capsys.readouterr()
    assert "Tokens estimados" in captured.out


@pytest.mark.asyncio
async def test_cmd_model_display(capsys):
    await handle_command("/model", None, {"provider": "fake"}, None)
    captured = capsys.readouterr()
    assert "Proveedor actual:" in captured.out


@pytest.mark.asyncio
@patch("app.tui.commands.console.print")
async def test_cmd_compact(mock_print):
    from app.core.harness.context import ContextManager
    from unittest.mock import AsyncMock
    from app.core.llm.base import LLMResponse

    ctx = ContextManager(system_prompt="System")
    # Añadimos 10 mensajes para asegurar que la compactación se dispare
    for i in range(10):
        ctx.add_user(f"Mensaje {i}")

    mock_llm = AsyncMock()
    mock_llm.chat.return_value = LLMResponse(content="[Resumen simulado]")

    await handle_command("/compact", ctx, {}, mock_llm)

    # Verificamos que se intentó compactar
    mock_llm.chat.assert_called_once()
    mock_print.assert_any_call(
        "[bold yellow]Compactando contexto...[/bold yellow]")


@pytest.mark.asyncio
@patch("app.tui.commands.console.print")
async def test_cmd_compact(mock_print):
    from app.core.harness.context import ContextManager
    from unittest.mock import AsyncMock
    from app.core.llm.base import LLMResponse

    ctx = ContextManager(system_prompt="System")
    # 🔥 Añadimos 6 mensajes para superar el límite de la compactación (keep_last_n=4)
    for i in range(6):
        ctx.add_user(f"Mensaje {i}")

    mock_llm = AsyncMock()
    # El LLM debe devolver un LLMResponse válido para que la compactación no falle
    mock_llm.chat.return_value = LLMResponse(content="[Resumen simulado]")

    await handle_command("/compact", ctx, {}, mock_llm)

    # Verificamos que se llamó al LLM para resumir
    mock_llm.chat.assert_called_once()
    mock_print.assert_any_call(
        "[bold yellow]Compactando contexto...[/bold yellow]")


@pytest.mark.asyncio
@patch("app.tui.commands.console.print")
async def test_cmd_debug(mock_print):
    from app.core.logger import logger
    import logging
    # 1. Estado inicial (DEBUG)
    logger.setLevel(logging.DEBUG)
    await handle_command("/debug", None, {}, None)
    assert logger.level == logging.INFO
    mock_print.assert_any_call("[bold yellow]Debug DESACTIVADO.[/bold yellow]")

    # 2. Cambiamos a INFO para cubrir la rama else
    logger.setLevel(logging.INFO)
    await handle_command("/debug", None, {}, None)
    assert logger.level == logging.DEBUG
    mock_print.assert_any_call(
        "[bold green]Debug ACTIVADO.[/bold green] (Verás los logs detallados de las peticiones)")
