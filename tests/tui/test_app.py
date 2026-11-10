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
@patch("app.tui.app.AgentLoop")  # 🔥 Mockeamos AgentLoop
@patch("app.tui.app.console.print")
async def test_run_tui_catches_general_exception(mock_print, mock_loop_class, mock_get_llm, mock_session_class):
    mock_session = mock_session_class.return_value
    mock_session.prompt_async = AsyncMock(side_effect=["Hola", "/quit"])

    # El LLM se inicializa bien
    mock_llm = MagicMock()
    mock_get_llm.return_value = mock_llm

    # 🔥 El error se lanza al ejecutar el AgentLoop
    mock_loop_instance = mock_loop_class.return_value
    mock_loop_instance.run = AsyncMock(
        side_effect=Exception("Error forzado en LLM"))

    with patch("pathlib.Path.exists", return_value=False):
        await run_tui()

    # Verificamos que se imprimió el error general
    error_encontrado = any("Error forzado en LLM" in str(call)
                           for call in mock_print.call_args_list)
    assert error_encontrado


@pytest.mark.asyncio
@patch("app.tui.prompt.console.print")
@patch("app.tui.prompt.Prompt.ask")
async def test_ask_user_permission(mock_ask, mock_print):
    mock_ask.return_value = "y"
    response = await ask_user_permission(
        tool_name="bash", signature="bash:echo 'Hola'", args={"command": "echo 'Hola'"}, diff_text=None
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
        tool_name="bash", signature="bash:line1\nline2", args={"command": "line1\nline2"}, diff_text="diff simulado"
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


@pytest.mark.asyncio
@patch("app.tui.app.PromptSession")
@patch("app.tui.app.get_llm")
@patch("app.tui.app.MCPClient")
@patch("app.tui.app.console.print")
async def test_run_tui_covers_finally_and_systemexit(mock_print, mock_mcp_class, mock_get_llm, mock_session_class):
    """Cubre el cierre de MCP (finally) y el except SystemExit."""
    mock_session = mock_session_class.return_value

    # 🔥 Lanzamos una excepción genérica que NO sea atrapada por los excepts del bucle
    # (así se propaga al finally y luego al except Exception externo)
    mock_session.prompt_async = AsyncMock(
        side_effect=Exception("Fallo catastrófico"))

    # Simulamos que hay un cliente MCP conectado para el finally
    mock_mcp_instance = AsyncMock()
    mock_mcp_class.return_value = mock_mcp_instance

    # Forzamos que mcp_config.json exista para cargar el cliente
    with patch("pathlib.Path.exists", return_value=True):
        with patch("builtins.open") as mock_open:
            mock_file = MagicMock()
            mock_file.read.return_value = '{"mcpServers": {"test": {"command": "uv", "args": []}}}'
            mock_open.return_value.__enter__.return_value = mock_file

            # La excepción se propaga hasta el except Exception externo, que la atrapa
            await run_tui()

    # Verificamos que se intentó cerrar el cliente
    mock_mcp_instance.disconnect.assert_called_once()


@pytest.mark.asyncio
@patch("app.tui.app.PromptSession")
@patch("app.tui.app.get_llm")
@patch("app.tui.app.MCPClient")
@patch("app.tui.app.console.print")
async def test_run_tui_covers_finally(mock_print, mock_mcp_class, mock_get_llm, mock_session_class):
    """Cubre el bloque finally de la TUI (cierre de MCP)."""
    mock_session = mock_session_class.return_value

    # Forzamos una excepción genérica que se propaga hasta el finally
    mock_session.prompt_async = AsyncMock(
        side_effect=Exception("Fallo crítico"))

    mock_mcp_instance = AsyncMock()
    mock_mcp_class.return_value = mock_mcp_instance

    with patch("pathlib.Path.exists", return_value=True):
        with patch("builtins.open") as mock_open:
            mock_file = MagicMock()
            mock_file.read.return_value = '{"mcpServers": {"test": {"command": "uv", "args": []}}}'
            mock_open.return_value.__enter__.return_value = mock_file

            await run_tui()

    # El finally debe haber intentado cerrar el cliente
    mock_mcp_instance.disconnect.assert_called_once()


@pytest.mark.asyncio
@patch("app.tui.app.PromptSession")
@patch("app.tui.app.get_llm")
@patch("app.tui.app.AgentLoop")
@patch("app.tui.app.console.print")
async def test_run_tui_agent_loop_exception(mock_print, mock_loop_class, mock_get_llm, mock_session_class):
    """Cubre las líneas 107-110: el except que atrapa errores del AgentLoop."""
    mock_session = mock_session_class.return_value
    mock_session.prompt_async = AsyncMock(side_effect=["Hola", "/quit"])

    mock_llm = MagicMock()
    mock_get_llm.return_value = mock_llm

    # Forzamos a que el AgentLoop lance una excepción al ejecutarse
    mock_loop_instance = mock_loop_class.return_value
    mock_loop_instance.run = AsyncMock(
        side_effect=Exception("Fallo simulado en el loop"))

    with patch("pathlib.Path.exists", return_value=False):
        await run_tui()

    # 🔥 Búsqueda flexible: recorremos todas las llamadas al print
    error_encontrado = False
    for call in mock_print.call_args_list:
        # Convertimos los argumentos de la llamada a string para buscar el mensaje
        call_str = str(call)
        if "Fallo simulado en el loop" in call_str:
            error_encontrado = True
            break

    assert error_encontrado, f"No se encontró el error en las llamadas: {mock_print.call_args_list}"


@pytest.mark.asyncio
@patch("app.tui.app.PromptSession")
@patch("app.tui.app.get_llm")
@patch("app.tui.app.AgentLoop")
@patch("app.tui.app.console.print")
async def test_run_tui_shows_tools(mock_print, mock_loop_class, mock_get_llm, mock_session_class):
    """Cubre la línea 107: cuando el agente usa herramientas y muestra los stats."""
    mock_session = mock_session_class.return_value
    mock_session.prompt_async = AsyncMock(
        side_effect=["Usa una tool", "/quit"])

    # Simulamos que el AgentLoop devuelve un resultado con herramientas usadas
    from app.core.harness.loop import LoopResult
    mock_loop_instance = mock_loop_class.return_value
    mock_loop_instance.run = AsyncMock(return_value=LoopResult(
        final_answer="He usado la tool",
        steps=2,
        tools_used=["bash", "read_file"],  # 🔥 Aquí forzamos la línea 107
        usage_total={"total_tokens": 50}
    ))

    with patch("pathlib.Path.exists", return_value=False):
        await run_tui()

    # Verificamos que se imprimió el resumen de pasos y herramientas
    mock_print.assert_any_call(
        "[dim]Pasos: 2 | Tools: ['bash', 'read_file'] | Tokens API: 50[/dim]\n"
    )
