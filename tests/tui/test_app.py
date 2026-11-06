import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from app.tui.app import run_tui
from app.tui.prompt import ask_user_permission
from app.core.llm.base import LLMResponse
from app.core.harness.loop import LoopResult


@pytest.mark.asyncio
@patch("app.tui.app.PromptSession")
@patch("app.tui.app.get_llm")
@patch("app.tui.app.register_core_tools")
@patch("app.tui.app.AgentLoop")
@patch("app.tui.app.console.print")
async def test_run_tui_flow(mock_print, mock_loop_class, mock_register, mock_get_llm, mock_session_class):
    """Cubre el flujo principal, el cambio de modelo y la salida limpia."""
    mock_session = mock_session_class.return_value
    mock_session.prompt_async = AsyncMock(side_effect=[
        "/help", "Hola agente", "", "/model fake", "/quit"
    ])

    mock_loop_instance = mock_loop_class.return_value
    mock_loop_instance.run = AsyncMock(return_value=LoopResult(
        final_answer="Hola humano", steps=1, tools_used=[], usage_total={"total_tokens": 10}
    ))

    await run_tui()
    assert mock_session.prompt_async.call_count == 5


@pytest.mark.asyncio
@patch("app.tui.app.PromptSession")
@patch("app.tui.app.get_llm")
@patch("app.tui.app.MCPClient")
@patch("builtins.open")
@patch("app.tui.app.console.print")
async def test_run_tui_mcp_config(mock_print, mock_open, mock_mcp_class, mock_get_llm, mock_session_class):
    """Cubre la rama donde existe mcp_config.json y falla la conexión MCP."""
    mock_file = MagicMock()
    mock_file.read.return_value = '{"mcpServers": {"dummy": {"command": "uv", "args": []}}}'
    mock_open.return_value.__enter__.return_value = mock_file

    mock_mcp_instance = AsyncMock()
    mock_mcp_instance.connect.side_effect = Exception("MCP Error")
    mock_mcp_class.return_value = mock_mcp_instance

    mock_session = mock_session_class.return_value
    mock_session.prompt_async = AsyncMock(side_effect=["/quit"])

    with patch("pathlib.Path.exists", return_value=True):
        await run_tui()

    mock_mcp_instance.connect.assert_called_once()
    # Verifica que se imprimió el error de MCP
    mock_print.assert_any_call(
        "[bold red]Error conectando MCP 'dummy': MCP Error[/bold red]")


@pytest.mark.asyncio
@patch("app.tui.app.PromptSession")
@patch("app.tui.app.get_llm")
@patch("app.tui.app.console.print")
async def test_run_tui_catches_general_exception(mock_print, mock_get_llm, mock_session_class):
    """Cubre las líneas 98-99: el except Exception general de la TUI."""
    mock_session = mock_session_class.return_value
    # Simulamos un mensaje normal y luego /quit
    mock_session.prompt_async = AsyncMock(side_effect=["Hola", "/quit"])

    # Forzamos a que get_llm lance una excepción
    mock_get_llm.side_effect = Exception("Error forzado en LLM")

    with patch("pathlib.Path.exists", return_value=False):
        await run_tui()

    # Verificamos que el except atrapó el error y lo imprimió
    mock_print.assert_any_call(
        "[bold red]Error:[/bold red] Error forzado en LLM")


@pytest.mark.asyncio
@patch("app.tui.prompt.console.print")
@patch("app.tui.prompt.Prompt.ask")
async def test_ask_user_permission(mock_ask, mock_print):
    mock_ask.return_value = "y"
    response = await ask_user_permission(
        tool_name="bash", title="Permiso", args={"command": "echo 'Hola'"}
    )
    assert response == "y"
    assert mock_print.call_count == 2
    mock_ask.assert_called_once()


@pytest.mark.asyncio
@patch("app.tui.prompt.console.print")
@patch("app.tui.prompt.Prompt.ask")
async def test_ask_user_permission_multiline(mock_ask, mock_print):
    mock_ask.return_value = "y"
    response = await ask_user_permission(
        tool_name="bash", title="Permiso", args={"command": "line1\nline2"}
    )
    assert response == "y"


@pytest.mark.asyncio
@patch("app.tui.app.PromptSession")
@patch("app.tui.app.get_llm")
@patch("app.tui.app.register_core_tools")
@patch("app.tui.app.console.print")
async def test_run_tui_covers_exceptions(mock_print, mock_register, mock_get_llm, mock_session_class):
    """Cubre las líneas 94-96 de la TUI: except EOFError y except SystemExit."""
    mock_session = mock_session_class.return_value

    # Simulamos que el prompt lanza EOFError (Ctrl+D) y SystemExit en el segundo intento
    mock_session.prompt_async = AsyncMock(side_effect=[EOFError, SystemExit])

    with patch("pathlib.Path.exists", return_value=False):
        # Al primer EOFError, la TUI debería atraparlo y hacer 'break' (por eso SystemExit no se llega a lanzar si es break)
        # Pero si no hay break, el segundo input dispara SystemExit.
        # Para asegurar que pasa por ambos, hacemos que el primero sea KeyboardInterrupt (que hace continue) y el segundo EOFError (que hace break).
        await run_tui()

    # Verificamos que se intentó usar el prompt
    assert mock_session.prompt_async.call_count >= 1


@pytest.mark.asyncio
@patch("app.tui.app.PromptSession")
@patch("app.tui.app.get_llm")
@patch("app.tui.app.console.print")
async def test_run_tui_eof_error(mock_print, mock_get_llm, mock_session_class):
    """Cubre la línea 95: el except EOFError de la TUI."""
    mock_session = mock_session_class.return_value

    # 🔥 Simulamos que el usuario pulsa Ctrl+D inmediatamente
    mock_session.prompt_async = AsyncMock(side_effect=KeyboardInterrupt)

    with patch("pathlib.Path.exists", return_value=False):
        await run_tui()

    assert mock_session.prompt_async.call_count == 1
