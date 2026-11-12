from datetime import datetime

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.core.harness.memory.base import MemoryEntry
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


@pytest.mark.asyncio
async def test_cmd_skills(mock_app, ctx):
    handled = await handle_command("/skills", ctx, {}, None, mock_app)
    assert handled is True
    assert "Skills Disponibles" in mock_app.write_to_chat.call_args[0][0]


@pytest.mark.asyncio
async def test_cmd_memory_clear(mock_app, ctx):
    mock_app.memory_store = MagicMock()
    mock_app.memory_store.clear = AsyncMock()
    handled = await handle_command("/memory clear", ctx, {}, None, mock_app)
    assert handled is True
    mock_app.memory_store.clear.assert_called_once()


@pytest.mark.asyncio
async def test_cmd_memory_migrate(mock_app, ctx):
    from unittest.mock import patch
    mock_app.memory_store = MagicMock()
    # 🔥 Cambiamos get_all por recall
    mock_app.memory_store.get_all = AsyncMock(return_value=[])
    with patch("app.core.harness.memory.factory.create_memory_store") as mock_create:
        handled = await handle_command("/memory migrate sqlite", ctx, {}, None, mock_app)
        assert handled is True
        mock_create.assert_called_once()


@pytest.mark.asyncio
async def test_cmd_skills_no_registry(mock_app, ctx):
    mock_app.registry = None
    assert await handle_command("/skills", ctx, {}, None, mock_app) is True
    assert "no está inicializado" in mock_app.write_to_chat.call_args[0][0]


@pytest.mark.asyncio
async def test_cmd_memory_no_store(mock_app, ctx):
    mock_app.memory_store = None  # 🔥 Aseguramos que sea None
    assert await handle_command("/memory clear", ctx, {}, None, mock_app) is True
    assert "Store no inicializado" in mock_app.write_to_chat.call_args[0][0]


@pytest.mark.asyncio
async def test_cmd_memory_invalid_subcommand(mock_app, ctx):
    assert await handle_command("/memory invalid", ctx, {}, None, mock_app) is True
    assert "Uso:" in mock_app.write_to_chat.call_args[0][0]


@pytest.mark.asyncio
async def test_cmd_memory_invalid_subcommand(mock_app, ctx):
    assert await handle_command("/memory invalid", ctx, {}, None, mock_app) is True
    assert "Uso:" in mock_app.write_to_chat.call_args[0][0]


@pytest.mark.asyncio
async def test_cmd_memory_migrate_no_store(mock_app, ctx):
    mock_app.memory_store = None
    assert await handle_command("/memory migrate sqlite", ctx, {}, None, mock_app) is True
    assert "Store no inicializado" in mock_app.write_to_chat.call_args[0][0]


@pytest.mark.asyncio
async def test_cmd_memory_migrate_with_entries(mock_app, ctx):
    """Cubre la línea 311: migración con entradas reales."""
    from unittest.mock import patch, MagicMock, AsyncMock
    from app.core.harness.memory.base import MemoryEntry
    from datetime import datetime

    # Mock del store actual con una entrada
    mock_app.memory_store = MagicMock()
    mock_app.memory_store.get_all = AsyncMock(return_value=[
        MemoryEntry(key="test", value="Hello", timestamp=datetime.now())
    ])
    mock_app.memory_store.clear = AsyncMock()

    # Mock del nuevo store
    mock_new_store = MagicMock()
    mock_new_store.save = AsyncMock()

    with patch("app.core.harness.memory.factory.create_memory_store", return_value=mock_new_store):
        handled = await handle_command("/memory migrate sqlite", ctx, {}, None, mock_app)
        assert handled is True
        # 🔥 Verificamos que se llamó a save (cubre línea 311)
        mock_new_store.save.assert_called_once()


@pytest.mark.asyncio
async def test_memory_migrate_re_registers_tools():
    """Verifica que al migrar la memoria se actualicen las tools del registry."""
    app = MagicMock()
    app.write_to_chat = AsyncMock()

    # Mock del store viejo
    old_store = AsyncMock()
    old_store.get_all.return_value = [MemoryEntry(
        key="k", value="v", timestamp=datetime.now(), kind="fact")]
    app.memory_store = old_store

    # Mock del registry
    app.registry = MagicMock()

    ctx = MagicMock()
    state = {}
    llm = MagicMock()

    with patch("app.core.harness.memory.factory.create_memory_store") as mock_factory:
        new_store = AsyncMock()
        mock_factory.return_value = new_store

        with patch("app.tools.memory.MemorySaveTool") as mock_save, \
                patch("app.tools.memory.MemoryRecallTool") as mock_recall:

            await handle_command("/memory migrate sqlite", ctx, state, llm, app)

            # Verifica que se creó el nuevo store
            mock_factory.assert_called_once_with("sqlite")
            # Verifica que se migraron las entradas
            new_store.save.assert_called_once()
            # Verifica que se re-registraron las tools
            assert app.registry.register.call_count == 2
            app.write_to_chat.assert_called_once()


@pytest.mark.asyncio
async def test_cmd_skills_no_installed(mock_app, ctx):
    """Cubre commands.py línea 143: sin skills instaladas."""
    with patch("app.tools.skills.LoadSkillTool.discover_skills", return_value=[]):
        await handle_command("/skills", ctx, {}, None, mock_app)
        assert "No hay skills instaladas" in mock_app.write_to_chat.call_args[0][0]


@pytest.mark.asyncio
async def test_cmd_session_list_empty(mock_app, ctx):
    """Cubre commands.py líneas 366-373: listar sesiones vacías."""
    with patch("app.core.harness.session.SessionManager.list_sessions", return_value=[]):
        await handle_command("/session list", ctx, {}, None, mock_app)
        assert "No hay sesiones guardadas" in mock_app.write_to_chat.call_args[0][0]


@pytest.mark.asyncio
async def test_cmd_session_list_with_data(mock_app, ctx):
    """Cubre commands.py líneas 375-382: listar sesiones con datos."""
    sessions = [
        {"id": "123", "timestamp": "2024-01-01T10:00:00", "message_count": 5}]
    with patch("app.core.harness.session.SessionManager.list_sessions", return_value=sessions):
        await handle_command("/session list", ctx, {}, None, mock_app)
        assert "123" in mock_app.write_to_chat.call_args[0][0]


@pytest.mark.asyncio
async def test_cmd_session_load(mock_app, ctx):
    """Cubre commands.py líneas 384-396: cargar sesión."""
    with patch("app.core.harness.session.SessionManager.load", return_value=[{"role": "user", "content": "Hola"}]):
        await handle_command("/session load 123", ctx, {}, None, mock_app)
        assert "cargada" in mock_app.write_to_chat.call_args[0][0]


@pytest.mark.asyncio
async def test_cmd_session_load_empty(mock_app, ctx):
    """Cubre commands.py líneas 394-395: sesión no encontrada."""
    with patch("app.core.harness.session.SessionManager.load", return_value=[]):
        await handle_command("/session load 123", ctx, {}, None, mock_app)
        assert "no encontrada" in mock_app.write_to_chat.call_args[0][0]


@pytest.mark.asyncio
async def test_cmd_session_delete(mock_app, ctx):
    """Cubre commands.py líneas 398-408: borrar sesión."""
    with patch("app.core.harness.session.SessionManager.delete_session", return_value=True):
        await handle_command("/session delete 123", ctx, {}, None, mock_app)
        assert "eliminada" in mock_app.write_to_chat.call_args[0][0]


@pytest.mark.asyncio
async def test_cmd_session_save(mock_app, ctx):
    """Cubre commands.py líneas 410-414: guardar sesión."""
    mock_app.session_manager = MagicMock()
    mock_app.session_manager.save.return_value = "/ruta/fake.json"
    await handle_command("/session save", ctx, {}, None, mock_app)
    assert "guardada" in mock_app.write_to_chat.call_args[0][0]


@pytest.mark.asyncio
async def test_cmd_session_help(mock_app, ctx):
    """Cubre commands.py líneas 419-427: mostrar ayuda de sesión."""
    await handle_command("/session", ctx, {}, None, mock_app)
    assert "Comandos de Sesión" in mock_app.write_to_chat.call_args[0][0]


@pytest.mark.asyncio
async def test_cmd_reload_skills(mock_app, ctx):
    """Cubre commands.py líneas 149-173: recargar skills."""
    mock_app.ctx = ctx
    with patch("app.tools.skills.LoadSkillTool.discover_skills", return_value=["skill1"]):
        await handle_command("/reload-skills", ctx, {}, None, mock_app)
        assert "Skills recargadas" in mock_app.write_to_chat.call_args[0][0]


@pytest.mark.asyncio
async def test_cmd_session_all_subcommands(mock_app, ctx):
    """Cubre commands.py líneas 397, 406-408, 415-418: todos los subcomandos de /session."""
    # load sin id
    await handle_command("/session load", ctx, {}, None, mock_app)
    # delete sin id
    await handle_command("/session delete", ctx, {}, None, mock_app)
    # save sin sesión activa
    mock_app.session_manager = None
    await handle_command("/session save", ctx, {}, None, mock_app)
    # subcomando inválido
    await handle_command("/session invalid", ctx, {}, None, mock_app)


@pytest.mark.asyncio
async def test_cmd_session_delete_not_found(mock_app, ctx):
    """Cubre la línea 406 de commands.py: sesión no encontrada al borrar."""
    with patch("app.core.harness.session.SessionManager.delete_session", return_value=False):
        await handle_command("/session delete fake_id", ctx, {}, None, mock_app)
        assert "no encontrada" in mock_app.write_to_chat.call_args[0][0]


@pytest.mark.asyncio
async def test_cmd_doctor(mock_app, ctx):
    """Cubre el comando /doctor al 100%."""
    # Mockeamos el session_manager para que no falle al llamar a list_sessions
    mock_app.session_manager = MagicMock()
    mock_app.session_manager.list_sessions.return_value = [{"id": "1"}]

    # Forzamos que no haya issues para cubrir el caso "Todo en orden"
    with patch("pathlib.Path.exists", return_value=True):
        with patch("pathlib.Path.read_text", return_value='{"mcpServers": {"test": {"command": "uv"}}}'):
            with patch("app.core.config.settings.LLM_PROVIDER", "openai"):
                with patch("app.core.config.settings.OPENAI_API_KEY", "sk-12345"):
                    with patch("app.tools.skills.LoadSkillTool.discover_skills", return_value=["skill1"]):
                        await handle_command("/doctor", ctx, {}, None, mock_app)
                        assert "Diagnóstico del Sistema" in mock_app.write_to_chat.call_args[0][0]


@pytest.mark.asyncio
async def test_cmd_trace(mock_app, ctx):
    """Cubre el comando /trace al 100%."""
    # Seteamos el usage y el modelo
    mock_app.last_usage = {"prompt_tokens": 100,
                           "completion_tokens": 50, "total_tokens": 150}
    mock_app.last_model = "gpt-4o"

    await handle_command("/trace", ctx, {}, None, mock_app)
    assert "Traza de la Última Llamada" in mock_app.write_to_chat.call_args[0][0]


@pytest.mark.asyncio
async def test_cmd_doctor_full_coverage(tmp_path, monkeypatch, mock_app, ctx):
    """Cubre TODAS las ramas del comando /doctor de forma robusta."""
    # Cambiamos al directorio temporal para que los Path("...") apunten aquí
    monkeypatch.chdir(tmp_path)
    mock_app.session_manager = MagicMock()
    mock_app.session_manager.list_sessions.return_value = []

    # --- Caso 1: Todo mal (FakeLLM, sin MCP, sin skills, sin permisos) ---
    with patch("app.core.config.settings.LLM_PROVIDER", "fake"):
        await handle_command("/doctor", ctx, {}, None, mock_app)
        output = mock_app.write_to_chat.call_args[0][0]
        assert "FakeLLM" in output
        assert "No existe `mcp_config.json`" in output
        assert "No existe el directorio" in output
        assert "No hay permisos guardados" in output

    # --- Caso 2: Cubrir ramas específicas (API Key vacía, MCP vacío, sin skills) ---
    # Creamos un mcp_config.json VACÍO
    (tmp_path / "mcp_config.json").write_text('{"mcpServers": {}}')
    # Creamos la carpeta de skills pero sin SKILL.md dentro
    skills_dir = tmp_path / ".agents" / "skills"
    skills_dir.mkdir(parents=True)

    with patch("app.core.config.settings.LLM_PROVIDER", "openai"):
        with patch("app.core.config.settings.OPENAI_API_KEY", ""):
            await handle_command("/doctor", ctx, {}, None, mock_app)
            output = mock_app.write_to_chat.call_args[0][0]
            assert "Falta `OPENAI_API_KEY`" in output
            assert "No hay servidores MCP configurados" in output
            assert "No hay skills instaladas" in output
            assert "problema(s) crítico(s)" in output

    # --- Caso 3: Todo bien (OpenAI, MCP configurado, skills, SQLite, permisos) ---
    # Sobrescribimos el mcp_config con un servidor
    (tmp_path /
     "mcp_config.json").write_text('{"mcpServers": {"test": {"command": "uv"}}}')
    # Creamos una skill real
    real_skill = skills_dir / "test_skill"
    real_skill.mkdir()
    (real_skill / "SKILL.md").write_text("# Test")

    # 🔥 Como hicimos monkeypatch.chdir(tmp_path), el permissions_file
    # apuntará automáticamente a .harness/permissions.json dentro de tmp_path
    (tmp_path / ".harness").mkdir(exist_ok=True)
    (tmp_path / ".harness" / "permissions.json").write_text("{}")

    with patch("app.core.config.settings.LLM_PROVIDER", "openai"):
        with patch("app.core.config.settings.OPENAI_API_KEY", "sk-123"):
            # 🔥 Ya NO parcheamos settings.permissions_file
            await handle_command("/doctor", ctx, {}, None, mock_app)
            output = mock_app.write_to_chat.call_args[0][0]
            assert "LLM configurado" in output
            assert "Todo en orden" in output


@pytest.mark.asyncio
async def test_cmd_trace_full_coverage(mock_app, ctx):
    """Cubre TODAS las ramas del comando /trace."""
    # Caso 1: Sin usage (retorno temprano)
    mock_app.last_usage = None
    await handle_command("/trace", ctx, {}, None, mock_app)
    assert "No hay datos de uso" in mock_app.write_to_chat.call_args[0][0]

    # Caso 2: Con usage y con cached tokens
    mock_app.last_usage = {
        "prompt_tokens": 100,
        "completion_tokens": 50,
        "total_tokens": 150,
        "prompt_tokens_details": {"cached_tokens": 20}
    }
    mock_app.last_model = "gpt-4o"
    await handle_command("/trace", ctx, {}, None, mock_app)
    assert "Cached (Ahorro)" in mock_app.write_to_chat.call_args[0][0]
    assert "Prompt Caching activo" in mock_app.write_to_chat.call_args[0][0]

    # Caso 3: Con usage pero SIN cached tokens
    mock_app.last_usage = {"prompt_tokens": 10,
                           "completion_tokens": 5, "total_tokens": 15}
    await handle_command("/trace", ctx, {}, None, mock_app)
    assert "Consejo: Activa" in mock_app.write_to_chat.call_args[0][0]


@pytest.mark.asyncio
async def test_cmd_doctor_memory_branches(tmp_path, monkeypatch, mock_app, ctx):
    """Cubre las ramas de memoria en /doctor (archivo existe y no existe)."""
    monkeypatch.chdir(tmp_path)
    mock_app.session_manager = MagicMock()
    mock_app.session_manager.list_sessions.return_value = []

    # 1. Simulamos que NO existen los archivos (para cubrir las líneas 122-123 y 134-135)
    with patch("app.core.config.settings.LLM_PROVIDER", "fake"):  # Para que no falle por API Key
        # SQLite no existe
        with patch("app.core.config.settings.MEMORY_BACKEND", "sqlite"):
            await handle_command("/doctor", ctx, {}, None, mock_app)
            assert "La base de datos SQLite (FTS5) aún no se ha creado" in mock_app.write_to_chat.call_args[
                0][0]

        # Files no existe
        with patch("app.core.config.settings.MEMORY_BACKEND", "files"):
            await handle_command("/doctor", ctx, {}, None, mock_app)
            assert "El directorio de archivos de memoria aún no se ha creado" in mock_app.write_to_chat.call_args[
                0][0]

    # 2. Simulamos que SÍ existen los archivos (para cubrir las líneas 124-125, 129-131, 136-137)
    # Creamos los archivos/directorios reales en tmp_path
    (tmp_path / ".harness").mkdir()
    (tmp_path / ".harness" / "memory.db").touch()
    (tmp_path / ".harness" / "vector.db").touch()
    (tmp_path / ".harness" / "memory").mkdir()

    with patch("app.core.config.settings.LLM_PROVIDER", "fake"):
        with patch("pathlib.Path.exists", return_value=True):  # 🔥 Forzamos que existan
            with patch("pathlib.Path.read_text", return_value='{"mcpServers": {"test": {}}}'):
                # Mock de la skill
                mock_skill = MagicMock()
                mock_skill.name = "test_skill"
                mock_skill.__truediv__.return_value.exists.return_value = True
                with patch("pathlib.Path.iterdir", return_value=[mock_skill]):
                    # SQLite existe
                    with patch("app.core.config.settings.MEMORY_BACKEND", "sqlite"):
                        await handle_command("/doctor", ctx, {}, None, mock_app)
                        assert "Base de datos FTS5 en" in mock_app.write_to_chat.call_args[0][0]

                    # Vector existe
                    with patch("app.core.config.settings.MEMORY_BACKEND", "vector"):
                        await handle_command("/doctor", ctx, {}, None, mock_app)
                        assert "Base de datos vectorial en" in mock_app.write_to_chat.call_args[
                            0][0]

                    # Files existe
                    with patch("app.core.config.settings.MEMORY_BACKEND", "files"):
                        await handle_command("/doctor", ctx, {}, None, mock_app)
                        assert "Archivos de memoria en" in mock_app.write_to_chat.call_args[0][0]

                    # Memory (fallback)
                    with patch("app.core.config.settings.MEMORY_BACKEND", "memory"):
                        await handle_command("/doctor", ctx, {}, None, mock_app)
                        assert "Almacenamiento en" in mock_app.write_to_chat.call_args[0][0]
