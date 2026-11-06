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
async def test_cmd_compact(capsys):
    from app.core.harness.context import ContextManager
    from unittest.mock import AsyncMock
    ctx = ContextManager(system_prompt="System")
    ctx.add_user("Mensaje")
    mock_llm = AsyncMock()

    await handle_command("/compact", ctx, {}, mock_llm)
    captured = capsys.readouterr()
    assert "Contexto compactado" in captured.out
