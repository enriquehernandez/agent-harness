import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.tui.commands import handle_command
from app.core.harness.context import ContextManager
from app.core.llm.base import LLMResponse


@pytest.fixture
def mock_app():
    app = MagicMock()
    app.write_to_chat = AsyncMock()
    app.update_dashboard = MagicMock()
    app.exit = MagicMock()
    app.toggle_debug_panel = AsyncMock()
    app.clear_debug_events = MagicMock()
    mock_scroll = MagicMock()
    mock_scroll.remove_children = AsyncMock()
    app.query_one.return_value = mock_scroll
    app.registry = MagicMock()
    app.registry.names.return_value = [
        "bash", "read_file", "delegate_to_reviewer"]
    mock_tool = MagicMock()
    mock_tool.description = "[MCP] Read a file"
    app.registry.get.return_value = mock_tool
    app.verbose_mode = False
    app.debug_mode = False
    return app


@pytest.fixture
def ctx():
    return ContextManager(system_prompt="System")


@pytest.mark.asyncio
async def test_cmd_permissions_with_file(mock_app, ctx):
    with patch("pathlib.Path.exists", return_value=True):
        # 🔥 CORREGIDO: El JSON debe ser un diccionario
        with patch("pathlib.Path.read_text", return_value='{"session_allowed": {"bash:ls": "always"}}'):
            assert await handle_command("/permissions", ctx, {}, None, mock_app) is True
            assert "Permisos Permanentes" in mock_app.write_to_chat.call_args[0][0]


@pytest.mark.asyncio
async def test_cmd_help(mock_app, ctx):
    assert await handle_command("/help", ctx, {}, None, mock_app) is True
    assert "Comandos Disponibles" in mock_app.write_to_chat.call_args[0][0]


@pytest.mark.asyncio
async def test_cmd_shortcuts(mock_app, ctx):
    assert await handle_command("/shortcuts", ctx, {}, None, mock_app) is True
    assert "Atajos de Teclado" in mock_app.write_to_chat.call_args[0][0]


@pytest.mark.asyncio
async def test_cmd_tools(mock_app, ctx):
    assert await handle_command("/tools", ctx, {}, None, mock_app) is True
    assert "Herramientas Disponibles" in mock_app.write_to_chat.call_args[0][0]


@pytest.mark.asyncio
async def test_cmd_tools_no_registry(mock_app, ctx):
    mock_app.registry = None
    assert await handle_command("/tools", ctx, {}, None, mock_app) is True
    assert "no está inicializado" in mock_app.write_to_chat.call_args[0][0]


@pytest.mark.asyncio
async def test_cmd_subagents(mock_app, ctx):
    assert await handle_command("/subagents", ctx, {}, None, mock_app) is True
    assert "Subagentes Registrados" in mock_app.write_to_chat.call_args[0][0]


@pytest.mark.asyncio
async def test_cmd_subagents_empty(mock_app, ctx):
    mock_app.registry.names.return_value = ["bash"]
    assert await handle_command("/subagents", ctx, {}, None, mock_app) is True
    assert "No hay subagentes" in mock_app.write_to_chat.call_args[0][0]


@pytest.mark.asyncio
async def test_cmd_tokens(mock_app, ctx):
    class MockLLM:
        max_context_window = 1000
    assert await handle_command("/tokens", ctx, {}, MockLLM(), mock_app) is True
    assert "Uso de Tokens" in mock_app.write_to_chat.call_args[0][0]


@pytest.mark.asyncio
async def test_cmd_clear(mock_app, ctx):
    ctx.add_user("Hola")
    assert await handle_command("/clear", ctx, {}, None, mock_app) is True
    assert len(ctx.messages) == 1
    mock_app.query_one.return_value.remove_children.assert_called_once()


@pytest.mark.asyncio
async def test_cmd_model_show(mock_app, ctx):
    with patch("app.tui.commands.list_providers", return_value=["fake", "openai"]):
        assert await handle_command("/model", ctx, {"provider": "fake"}, None, mock_app) is True
        assert "Configuración Actual" in mock_app.write_to_chat.call_args[0][0]


@pytest.mark.asyncio
async def test_cmd_model_change_success(mock_app, ctx):
    with patch("app.tui.commands.get_llm", new_callable=MagicMock):
        state = {"provider": "fake"}
        assert await handle_command("/model openai", ctx, state, None, mock_app) is True
        assert state["provider"] == "openai"
        mock_app.update_dashboard.assert_called()


@pytest.mark.asyncio
async def test_cmd_model_change_error(mock_app, ctx):
    with patch("app.tui.commands.get_llm", side_effect=Exception("Error")):
        assert await handle_command("/model unknown", ctx, {"provider": "fake"}, None, mock_app) is True
        assert "Error al cambiar" in mock_app.write_to_chat.call_args[0][0]


@pytest.mark.asyncio
async def test_cmd_compact(mock_app, ctx):
    for i in range(10):
        ctx.add_user(f"Msg {i}")
    mock_llm = MagicMock()
    mock_llm.chat = AsyncMock(return_value=LLMResponse(content="Summary"))
    assert await handle_command("/compact", ctx, {}, mock_llm, mock_app) is True
    assert "Contexto compactado" in mock_app.write_to_chat.call_args[0][0]


@pytest.mark.asyncio
async def test_cmd_compact_invalid_strategy(mock_app, ctx):
    assert await handle_command("/compact invalid", ctx, {}, None, mock_app) is True
    assert "Estrategias válidas" in mock_app.write_to_chat.call_args[0][0]


@pytest.mark.asyncio
async def test_cmd_verbose(mock_app, ctx):
    assert await handle_command("/verbose on", ctx, {}, None, mock_app) is True
    assert mock_app.verbose_mode is True

    assert await handle_command("/verbose off", ctx, {}, None, mock_app) is True
    assert mock_app.verbose_mode is False


@pytest.mark.asyncio
async def test_cmd_verbose_show(mock_app, ctx):
    assert await handle_command("/verbose", ctx, {}, None, mock_app) is True
    assert "Verbose" in mock_app.write_to_chat.call_args[0][0]


@pytest.mark.asyncio
async def test_cmd_debug(mock_app, ctx):
    assert await handle_command("/debug on", ctx, {}, None, mock_app) is True
    mock_app.toggle_debug_panel.assert_called_with(True)

    assert await handle_command("/debug off", ctx, {}, None, mock_app) is True
    mock_app.toggle_debug_panel.assert_called_with(False)

    assert await handle_command("/debug clear", ctx, {}, None, mock_app) is True
    mock_app.clear_debug_events.assert_called_once()


@pytest.mark.asyncio
async def test_cmd_debug_show(mock_app, ctx):
    assert await handle_command("/debug", ctx, {}, None, mock_app) is True
    assert "Debug" in mock_app.write_to_chat.call_args[0][0]


@pytest.mark.asyncio
async def test_cmd_permissions_no_file(mock_app, ctx):
    with patch("pathlib.Path.exists", return_value=False):
        assert await handle_command("/permissions", ctx, {}, None, mock_app) is True
        assert "No hay permisos" in mock_app.write_to_chat.call_args[0][0]


@pytest.mark.asyncio
async def test_cmd_quit(mock_app, ctx):
    assert await handle_command("/quit", ctx, {}, None, mock_app) is True
    mock_app.exit.assert_called_once()


@pytest.mark.asyncio
async def test_cmd_unknown(mock_app, ctx):
    assert await handle_command("/inventado", ctx, {}, None, mock_app) is True
    assert "Comando desconocido" in mock_app.write_to_chat.call_args[0][0]


@pytest.mark.asyncio
async def test_cmd_tools_empty_registry(mock_app, ctx):
    """Cubre las líneas 65-66: cuando el registry está vacío."""
    mock_app.registry.names.return_value = []  # Simulamos registry vacío
    assert await handle_command("/tools", ctx, {}, None, mock_app) is True
    assert "No hay herramientas" in mock_app.write_to_chat.call_args[0][0]


@pytest.mark.asyncio
async def test_cmd_subagents_no_registry(mock_app, ctx):
    """Cubre las líneas 81-82: cuando el registry es None."""
    mock_app.registry = None
    assert await handle_command("/subagents", ctx, {}, None, mock_app) is True
    assert "no está inicializado" in mock_app.write_to_chat.call_args[0][0]


@pytest.mark.asyncio
async def test_cmd_compact_verbose(mock_app, ctx):
    """Cubre las líneas 174-176: resumen con verbose activado."""
    for i in range(10):
        ctx.add_user(f"Msg {i}")

    mock_llm = MagicMock()
    mock_llm.chat = AsyncMock(return_value=LLMResponse(content="Summary"))

    # 🔥 Activamos verbose en la app
    mock_app.verbose_mode = True

    assert await handle_command("/compact summarize", ctx, {}, mock_llm, mock_app) is True

    # Verificamos que se imprimió el resumen
    calls = [str(call) for call in mock_app.write_to_chat.call_args_list]
    assert any("Resumen de compactación" in c for c in calls)


@pytest.mark.asyncio
async def test_cmd_verbose_invalid(mock_app, ctx):
    """Cubre la línea 193: subcomando inválido."""
    assert await handle_command("/verbose invalid", ctx, {}, None, mock_app) is True
    assert "Usa `/verbose on` o `/verbose off`" in mock_app.write_to_chat.call_args[0][0]


@pytest.mark.asyncio
async def test_cmd_debug_invalid(mock_app, ctx):
    """Cubre la línea 217: subcomando inválido."""
    assert await handle_command("/debug invalid", ctx, {}, None, mock_app) is True
    assert "Subcomando desconocido" in mock_app.write_to_chat.call_args[0][0]


@pytest.mark.asyncio
async def test_cmd_permissions_empty_list(mock_app, ctx):
    """Cubre las líneas 233-234: archivo válido pero sin permisos."""
    with patch("pathlib.Path.exists", return_value=True):
        with patch("pathlib.Path.read_text", return_value='{"session_allowed": {}}'):
            assert await handle_command("/permissions", ctx, {}, None, mock_app) is True
            assert "No hay herramientas con 'Permitir siempre'" in mock_app.write_to_chat.call_args[
                0][0]


@pytest.mark.asyncio
async def test_cmd_export(mock_app, ctx):
    """Cubre el comando /export en todas sus variantes."""
    # Añadimos un mensaje para exportar
    ctx.add_user("Hola mundo")

    # 1. Exportar a stdout (sin archivo)
    assert await handle_command("/export markdown", ctx, {}, None, mock_app) is True
    assert "Hola mundo" in mock_app.write_to_chat.call_args[0][0]

    # 2. Exportar a un archivo
    import tempfile
    import os
    with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as tmp:
        file_path = tmp.name

    try:
        assert await handle_command(f"/export markdown {file_path}", ctx, {}, None, mock_app) is True
        # Verificamos que se creó el archivo
        with open(file_path, "r") as f:
            content = f.read()
        assert "Hola mundo" in content
    finally:
        os.unlink(file_path)

    # 3. Exportar a JSON
    assert await handle_command("/export json", ctx, {}, None, mock_app) is True
    assert '"role": "user"' in mock_app.write_to_chat.call_args[0][0]
