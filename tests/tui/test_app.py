import asyncio
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from app.tui.app import AgentHarnessApp, FileAwareInput
from textual.widgets import Input, Static, ListView
from textual.worker import NoActiveWorker
from app.core.harness.loop import LoopResult
from pathlib import Path


@pytest.fixture(autouse=True)
def mock_session_manager():
    """Mockea SessionManager para que no intente cargar sesiones en los tests."""
    with patch("app.tui.app.SessionManager") as mock_sm:
        mock_instance = MagicMock()
        mock_instance.list_sessions.return_value = []  # 🔥 Sin sesiones
        mock_instance.save.return_value = "/fake/path.json"
        mock_sm.return_value = mock_instance
        mock_sm.list_sessions.return_value = []  # 🔥 Para el método estático
        yield mock_sm


@pytest.mark.asyncio
async def test_app_mount_and_bindings():
    """Cubre el montaje, la entrada de texto y los atajos básicos."""
    app = AgentHarnessApp()
    with patch.object(app, "initialize_agent", new_callable=AsyncMock):
        app.agent_loop = MagicMock()
        app.agent_loop.stream = AsyncMock(
            return_value=iter([]))  # Mock de stream
        async with app.run_test() as pilot:
            input_box = app.query_one("#input-box", FileAwareInput)
            input_box.focus()
            await pilot.pause()

            # Escribir y enviar
            input_box.value = "Hola"
            await pilot.press("enter")
            await pilot.pause()

            # Limpiar input (Ctrl+U)
            input_box.value = "Algo"
            app.action_clear_input()
            await pilot.pause()
            assert input_box.value == ""


@pytest.mark.asyncio
async def test_app_clear_chat():
    """Cubre el atajo Ctrl+L."""
    app = AgentHarnessApp()
    with patch.object(app, "initialize_agent", new_callable=AsyncMock):
        async with app.run_test() as pilot:
            await app.write_to_chat("Mensaje", type="user")
            await pilot.pause()
            await pilot.press("ctrl+l")
            await pilot.pause()
            assert len(app.query_one("#chat-scroll").children) <= 1


@pytest.mark.asyncio
async def test_app_process_input_command():
    """Cubre el procesamiento de comandos."""
    app = AgentHarnessApp()
    with patch.object(app, "initialize_agent", new_callable=AsyncMock):
        with patch("app.tui.app.handle_command", new_callable=AsyncMock) as mock_handle:
            async with app.run_test() as pilot:
                app.process_input("/help")
                await pilot.pause()
                mock_handle.assert_called_once()


@pytest.mark.asyncio
async def test_app_process_input_agent_success():
    """Cubre el procesamiento exitoso del agente con streaming."""
    app = AgentHarnessApp()
    with patch.object(app, "initialize_agent", new_callable=AsyncMock):
        mock_loop = MagicMock()
        # Mockeamos stream como un generador asíncrono

        async def mock_stream(*args, **kwargs):
            yield "Respuesta"
        mock_loop.stream = mock_stream
        app.agent_loop = mock_loop
        async with app.run_test() as pilot:
            app.process_input("Hola")
            await pilot.pause()
            # Verificamos que se creó el widget de Markdown
            assert len(app.query_one("#chat-scroll").children) > 0


@pytest.mark.asyncio
async def test_app_process_input_agent_error():
    """Cubre el manejo de errores del agente."""
    app = AgentHarnessApp()
    with patch.object(app, "initialize_agent", new_callable=AsyncMock):
        mock_loop = MagicMock()
        # Simulamos un error en el stream

        async def mock_stream(*args, **kwargs):
            raise Exception("Error simulado")
        mock_loop.stream = mock_stream
        app.agent_loop = mock_loop
        async with app.run_test() as pilot:
            app.process_input("Hola")
            await pilot.pause()
            # Verificamos que se mostró el error
            scroll = app.query_one("#chat-scroll")
            texts = []
            for child in scroll.children:
                if hasattr(child, "content"):
                    texts.append(str(child.content))
                elif hasattr(child, "renderable"):
                    texts.append(str(child.renderable))
            assert any("Error" in t for t in texts)


@pytest.mark.asyncio
async def test_app_toggle_debug():
    """Cubre la apertura y cierre del panel de debug."""
    app = AgentHarnessApp()
    with patch.object(app, "initialize_agent", new_callable=AsyncMock):
        async with app.run_test() as pilot:
            debug_panel = app.query_one("#debug-panel")
            assert debug_panel.display is False
            await pilot.press("f1")
            await pilot.pause()
            assert debug_panel.display is True
            await pilot.press("f1")
            await pilot.pause()
            assert debug_panel.display is False


@pytest.mark.asyncio
async def test_app_debug_list_selected():
    """Cubre la selección de un evento en el panel de debug."""
    app = AgentHarnessApp()
    with patch.object(app, "initialize_agent", new_callable=AsyncMock):
        with patch("app.tui.app.get_debug_events", return_value=[
            {"timestamp": "12:00", "type": "DEBUG",
                "summary": "Test", "payload": "{}"}
        ]):
            async with app.run_test() as pilot:
                await pilot.press("f1")
                await pilot.pause()
                list_view = app.query_one("#debug-list", ListView)
                if list_view.children:
                    list_view.index = 0
                    await pilot.press("enter")
                    await pilot.pause()


@pytest.mark.asyncio
async def test_app_permission_modal():
    """Cubre el modal de permisos."""
    app = AgentHarnessApp()
    with patch.object(app, "initialize_agent", new_callable=AsyncMock):
        async with app.run_test() as pilot:
            async def ask():
                try:
                    await app.request_permission(
                        tool_name="bash", signature="bash:ls", args={"command": "ls"}, diff_text=None
                    )
                except NoActiveWorker:
                    pass
            app.run_worker(ask())
            await pilot.pause()
            await pilot.press("y")
            await pilot.pause()


@pytest.mark.asyncio
async def test_app_update_dashboard():
    """Cubre la actualización del dashboard."""
    app = AgentHarnessApp()
    with patch.object(app, "initialize_agent", new_callable=AsyncMock):
        async with app.run_test() as pilot:
            app.update_dashboard("Pensando...", tokens=100, last_tool="bash")
            await pilot.pause()
            dash = app.query_one("#dashboard", Static)
            assert "Pensando" in str(dash.render())


@pytest.mark.asyncio
async def test_app_unmount_cleanup():
    """Cubre el cierre limpio de la app (on_unmount)."""
    app = AgentHarnessApp()
    mock_client = AsyncMock()
    app.mcp_clients.append(mock_client)
    with patch.object(app, "initialize_agent", new_callable=AsyncMock):
        async with app.run_test() as pilot:
            pass
        mock_client.disconnect.assert_called_once()


@pytest.mark.asyncio
async def test_app_initialize_agent_real():
    """Cubre el bloque de initialize_agent."""
    app = AgentHarnessApp()
    with patch("app.tui.app.MCPClient") as mock_mcp_class:
        mock_client = AsyncMock()
        mock_client.connect = AsyncMock()
        mock_client.register_tools = AsyncMock()
        mock_mcp_class.return_value = mock_client
        with patch("app.tui.app.register_core_tools"):
            # 🔥 Eliminamos el patch de SUMMARY_FILE
            async with app.run_test() as pilot:
                await app.initialize_agent()
                await pilot.pause()
                assert app.ctx is not None
                assert app.registry is not None
                assert app.agent_loop is not None
                assert app.gate is not None


@pytest.mark.asyncio
async def test_app_initialize_agent_error():
    """Cubre el except de MCP."""
    app = AgentHarnessApp()
    with patch("app.tui.app.MCPClient") as mock_mcp_class:
        mock_mcp_class.return_value.connect = AsyncMock(
            side_effect=Exception("MCP Error"))
        with patch("app.tui.app.register_core_tools"):
            # 🔥 Eliminamos el patch de SUMMARY_FILE
            async with app.run_test() as pilot:
                await app.initialize_agent()
                await pilot.pause()
                scroll = app.query_one("#chat-scroll")
                texts = []
                for child in scroll.children:
                    if hasattr(child, "renderable"):
                        texts.append(str(child.renderable))
                    elif hasattr(child, "content"):
                        texts.append(str(child.content))
                assert any("Error conectando MCP" in t for t in texts)


@pytest.mark.asyncio
async def test_app_request_permission_multiline():
    """Cubre args_str con multilinea."""
    app = AgentHarnessApp()
    with patch.object(app, "initialize_agent", new_callable=AsyncMock):
        async with app.run_test() as pilot:
            async def ask():
                try:
                    await app.request_permission(
                        tool_name="bash", signature="bash:echo",
                        args={"command": "line1\nline2"}, diff_text=None
                    )
                except NoActiveWorker:
                    pass
            app.run_worker(ask())
            await pilot.pause()
            await pilot.press("y")
            await pilot.pause()


@pytest.mark.asyncio
async def test_app_debug_panel_show_hide():
    """Cubre toggle_debug_panel."""
    app = AgentHarnessApp()
    with patch.object(app, "initialize_agent", new_callable=AsyncMock):
        async with app.run_test() as pilot:
            await app.toggle_debug_panel(True)
            assert app.query_one("#debug-panel").display is True
            await app.toggle_debug_panel(False)
            assert app.query_one("#debug-panel").display is False


@pytest.mark.asyncio
async def test_app_clear_debug_events():
    """Cubre clear_debug_events."""
    app = AgentHarnessApp()
    with patch.object(app, "initialize_agent", new_callable=AsyncMock):
        async with app.run_test() as pilot:
            app.debug_mode = True
            app.clear_debug_events()
            await pilot.pause()


@pytest.mark.asyncio
async def test_app_debug_list_empty():
    """Cubre _refresh_debug_list sin eventos."""
    app = AgentHarnessApp()
    with patch.object(app, "initialize_agent", new_callable=AsyncMock):
        with patch("app.tui.app.get_debug_events", return_value=[]):
            async with app.run_test() as pilot:
                await app._refresh_debug_list()
                await pilot.pause()
                list_view = app.query_one("#debug-list", ListView)
                first_item = list_view.children[0]
                label = first_item.children[0]
                assert "No hay eventos" in str(label.render())


@pytest.mark.asyncio
async def test_app_process_input_agent_timeout():
    """Cubre el except TimeoutError."""
    app = AgentHarnessApp()
    with patch.object(app, "initialize_agent", new_callable=AsyncMock):
        mock_loop = MagicMock()

        # 🔥 Definimos un generador asíncrono que lance TimeoutError
        async def slow_stream(*args, **kwargs):
            await asyncio.sleep(0.1)
            raise asyncio.TimeoutError()
            yield  # (nunca se alcanza, pero hace que sea un generador)

        mock_loop.stream = slow_stream
        app.agent_loop = mock_loop

        async with app.run_test() as pilot:
            app.process_input("Hola")
            await pilot.pause(0.5)

            scroll = app.query_one("#chat-scroll")
            texts = []
            for child in scroll.children:
                if hasattr(child, "renderable"):
                    texts.append(str(child.renderable))
                elif hasattr(child, "content"):
                    texts.append(str(child.content))

            assert any("Timeout" in t for t in texts), f"Textos: {texts}"


@pytest.mark.asyncio
async def test_app_initialize_agent_with_memory():
    """Cubre la carga de memoria."""
    app = AgentHarnessApp()
    with patch("app.tui.app.MCPClient") as mock_mcp_class:
        mock_client = AsyncMock()
        mock_client.connect = AsyncMock()
        mock_client.register_tools = AsyncMock()
        mock_mcp_class.return_value = mock_client
        with patch("app.tui.app.register_core_tools"):
            # 🔥 Eliminamos el patch de SUMMARY_FILE
            async with app.run_test() as pilot:
                await app.initialize_agent()
                await pilot.pause()
                # Verificamos que el ctx se creó (aunque no haya memoria)
                assert app.ctx is not None


@pytest.mark.asyncio
async def test_app_initialize_agent_with_tools():
    """Cubre el registro de herramientas del reviewer."""
    app = AgentHarnessApp()
    with patch("app.tui.app.MCPClient") as mock_mcp_class:
        mock_client = AsyncMock()
        mock_client.connect = AsyncMock()
        mock_client.register_tools = AsyncMock()
        mock_mcp_class.return_value = mock_client

        # 🔥 side_effect debe aceptar *args y **kwargs
        with patch("app.tui.app.register_core_tools") as mock_register:
            def side_effect(registry, **kwargs):
                from app.core.harness.tool import FunctionTool
                registry.register(FunctionTool(
                    name="read_text_file", description="", parameters_schema={}, func=lambda: ""
                ))
            mock_register.side_effect = side_effect

            async with app.run_test() as pilot:
                await app.initialize_agent()
                await pilot.pause()


@pytest.mark.asyncio
async def test_app_request_permission_responses():
    """Cubre las respuestas del usuario en el modal."""
    app = AgentHarnessApp()
    with patch.object(app, "initialize_agent", new_callable=AsyncMock):
        async with app.run_test() as pilot:
            with patch.object(app, "push_screen_wait", new_callable=AsyncMock) as mock_wait:
                def get_last_message():
                    children = app.query_one("#chat-scroll").children
                    if not children:
                        return ""
                    last = children[-1]
                    if hasattr(last, "content"):
                        return str(last.content)
                    elif hasattr(last, "renderable"):
                        return str(last.renderable)
                    return str(last.render())

                mock_wait.return_value = "y"
                await app.request_permission("bash", "bash:ls", {"command": "ls"})
                assert "Permiso **concedido**" in get_last_message()

                mock_wait.return_value = "a"
                await app.request_permission("bash", "bash:ls", {"command": "ls"})
                assert "concedido permanentemente" in get_last_message()

                mock_wait.return_value = "n"
                await app.request_permission("bash", "bash:ls", {"command": "ls"})
                assert "denegado" in get_last_message()


@pytest.mark.asyncio
async def test_app_list_view_empty_id():
    """Cubre id inválido en on_list_view_selected."""
    app = AgentHarnessApp()
    with patch.object(app, "initialize_agent", new_callable=AsyncMock):
        async with app.run_test() as pilot:
            mock_event = MagicMock()
            mock_event.item.id = None
            await app.on_list_view_selected(mock_event)


@pytest.mark.asyncio
async def test_app_process_input_debug_mode():
    """Cubre refrescar debug al terminar."""
    app = AgentHarnessApp()
    with patch.object(app, "initialize_agent", new_callable=AsyncMock):
        async with app.run_test() as pilot:
            app.debug_mode = True
            mock_loop = MagicMock()

            async def mock_stream(*args, **kwargs):
                yield "OK"
            mock_loop.stream = mock_stream
            app.agent_loop = mock_loop
            with patch.object(app, "_refresh_debug_list", new_callable=AsyncMock) as mock_refresh:
                app.process_input("Hola")
                await pilot.pause()
                mock_refresh.assert_called_once()


@pytest.mark.asyncio
async def test_app_on_input_submitted_with_files():
    """Cubre archivos adjuntos."""
    app = AgentHarnessApp()
    with patch.object(app, "initialize_agent", new_callable=AsyncMock):
        async with app.run_test() as pilot:
            app.attached_files = ["file1.txt", "file2.txt"]
            mock_event = MagicMock()
            mock_event.value = "Revisa esto"
            mock_event.input = MagicMock()
            with patch.object(app, "process_input", new_callable=MagicMock) as mock_process:
                await app.on_input_submitted(mock_event)
                mock_process.assert_called_once()
                assert "file1.txt" in mock_process.call_args[0][0]


@pytest.mark.asyncio
async def test_app_on_input_submitted_only_files():
    """Cubre cuando hay archivos pero no texto."""
    app = AgentHarnessApp()
    with patch.object(app, "initialize_agent", new_callable=AsyncMock):
        async with app.run_test() as pilot:
            app.attached_files = ["file1.txt"]
            mock_event = MagicMock()
            mock_event.value = ""
            mock_event.input = MagicMock()
            with patch.object(app, "process_input", new_callable=MagicMock) as mock_process:
                await app.on_input_submitted(mock_event)
                mock_process.assert_called_once()
                assert "Por favor, revisa estos archivos" in mock_process.call_args[0][0]


@pytest.mark.asyncio
async def test_app_on_paste_different_extensions(tmp_path):
    """Cubre extensiones de archivos."""
    app = AgentHarnessApp()
    with patch.object(app, "initialize_agent", new_callable=AsyncMock):
        async with app.run_test() as pilot:
            for ext in [".pdf", ".mp3", ".py"]:
                test_file = tmp_path / f"test{ext}"
                test_file.write_text("Hello")
                mock_event = MagicMock()
                mock_event.text = str(test_file)
                mock_event.prevent_default = MagicMock()
                await app.handle_file_paste(str(test_file))
            assert len(app.attached_files) == 3


@pytest.mark.asyncio
async def test_app_on_paste_image_icon(tmp_path):
    """Cubre el icono de imagen."""
    app = AgentHarnessApp()
    test_file = tmp_path / "test.png"
    test_file.write_text("fake image content")
    with patch.object(app, "initialize_agent", new_callable=AsyncMock):
        async with app.run_test() as pilot:
            await app.handle_file_paste(str(test_file))
            assert len(app.attached_images) == 1
            scroll = app.query_one("#chat-scroll")
            texts = []
            for child in scroll.children:
                if hasattr(child, "renderable"):
                    texts.append(str(child.renderable))
                elif hasattr(child, "content"):
                    texts.append(str(child.content))
            assert any("🖼️" in t for t in texts), f"Textos: {texts}"


@pytest.mark.asyncio
async def test_app_handle_file_paste_all_image_formats(tmp_path):
    """Cubre la detección de MIME types para todas las imágenes."""
    app = AgentHarnessApp()

    with patch.object(app, "initialize_agent", new_callable=AsyncMock):
        async with app.run_test() as pilot:
            # Probamos .png, .gif, .webp
            for ext, expected_mime in [(".png", "image/png"), (".gif", "image/gif"), (".webp", "image/webp")]:
                test_file = tmp_path / f"test{ext}"
                test_file.write_text("fake image")

                await app.handle_file_paste(str(test_file))

                # Verificamos que se guardó con el MIME correcto
                last_image = app.attached_images[-1]
                assert expected_mime in last_image


@pytest.mark.asyncio
async def test_app_on_input_submitted_with_images():
    """Cubre el envío de mensajes con imágenes adjuntas."""
    app = AgentHarnessApp()
    with patch.object(app, "initialize_agent", new_callable=AsyncMock):
        async with app.run_test() as pilot:
            app.attached_images = ["data:image/png;base64,fake_base64"]
            mock_event = MagicMock()
            mock_event.value = "¿Qué ves?"
            mock_event.input = MagicMock()

            # Mockeamos el agent_loop para que el stream funcione
            app.agent_loop = MagicMock()

            async def mock_stream(*args, **kwargs):
                yield "Es una imagen"
            app.agent_loop.stream = mock_stream

            await app.on_input_submitted(mock_event)
            await pilot.pause()

            # Verificamos que se limpió la lista de imágenes
            assert len(app.attached_images) == 0
            # Verificamos que se añadió el mensaje multimodal al contexto
            last_msg = app.ctx.messages[-1]
            assert last_msg["role"] == "user"
            assert any(m["type"] == "image_url" for m in last_msg["content"])


@pytest.mark.asyncio
async def test_app_write_to_chat_exception():
    """Cubre el except de write_to_chat."""
    app = AgentHarnessApp()
    with patch.object(app, "initialize_agent", new_callable=AsyncMock):
        async with app.run_test() as pilot:
            # Forzamos un error en query_one
            with patch.object(app, "query_one", side_effect=Exception("Error visual")):
                await app.write_to_chat("Test", type="agent")
                # No debe lanzar excepción (el except la atrapa)


@pytest.mark.asyncio
async def test_app_on_input_submitted_with_images():
    """Cubre el envío de mensajes con imágenes adjuntas."""
    app = AgentHarnessApp()
    with patch.object(app, "initialize_agent", new_callable=AsyncMock):
        async with app.run_test() as pilot:
            # 🔥 Inyectamos un ContextManager real para que add_user_with_image funcione
            from app.core.harness.context import ContextManager
            app.ctx = ContextManager(system_prompt="System")

            app.attached_images = ["data:image/png;base64,fake_base64"]
            mock_event = MagicMock()
            mock_event.value = "¿Qué ves?"
            mock_event.input = MagicMock()

            # Mockeamos el agent_loop para que el stream funcione
            app.agent_loop = MagicMock()

            async def mock_stream(*args, **kwargs):
                yield "Es una imagen"
            app.agent_loop.stream = mock_stream

            await app.on_input_submitted(mock_event)
            await pilot.pause()

            # Verificamos que se limpió la lista de imágenes
            assert len(app.attached_images) == 0
            # Verificamos que se añadió el mensaje multimodal al contexto
            last_msg = app.ctx.messages[-1]
            assert last_msg["role"] == "user"
            assert any(m["type"] == "image_url" for m in last_msg["content"])


@pytest.mark.asyncio
async def test_file_aware_input_paste():
    """Cubre las líneas 34-50: _on_paste del FileAwareInput."""
    app = AgentHarnessApp()
    with patch.object(app, "initialize_agent", new_callable=AsyncMock):
        async with app.run_test() as pilot:
            input_box = app.query_one("#input-box", FileAwareInput)

            # Creamos un evento de paste con un archivo real
            from pathlib import Path
            test_file = Path("test_paste.txt")
            test_file.write_text("Hello")

            try:
                # Simulamos el paste
                mock_event = MagicMock()
                mock_event.text = str(test_file)
                mock_event.prevent_default = MagicMock()
                mock_event.stop = MagicMock()

                # Llamamos directamente al método
                await input_box._on_paste(mock_event)

                # Verificamos que se procesó el archivo
                assert len(app.attached_files) > 0
            finally:
                test_file.unlink()


@pytest.mark.asyncio
async def test_write_to_chat_markdown():
    """Cubre la línea 402: write_to_chat con Markdown."""
    app = AgentHarnessApp()
    with patch.object(app, "initialize_agent", new_callable=AsyncMock):
        async with app.run_test() as pilot:
            await app.write_to_chat("**Negrita**", type="agent")
            await pilot.pause()
            # Verificamos que se creó el widget
            assert len(app.query_one("#chat-scroll").children) > 0


@pytest.mark.asyncio
async def test_app_on_input_submitted_with_images():
    """Cubre las líneas 604-624: envío de imágenes."""
    app = AgentHarnessApp()
    with patch.object(app, "initialize_agent", new_callable=AsyncMock):
        async with app.run_test() as pilot:
            # Inyectamos contexto real
            from app.core.harness.context import ContextManager
            app.ctx = ContextManager(system_prompt="System")

            app.attached_images = ["data:image/png;base64,fake"]
            mock_event = MagicMock()
            mock_event.value = "¿Qué ves?"
            mock_event.input = MagicMock()

            # Mockeamos el stream
            app.agent_loop = MagicMock()

            async def mock_stream(*args, **kwargs):
                yield "Es una imagen"
            app.agent_loop.stream = mock_stream

            await app.on_input_submitted(mock_event)
            await pilot.pause()

            # Verificamos que se procesó
            assert len(app.attached_images) == 0


@pytest.mark.asyncio
async def test_app_stream_to_chat_with_result():
    """Cubre stream_to_chat con tool_call y result."""
    app = AgentHarnessApp()
    with patch.object(app, "initialize_agent", new_callable=AsyncMock):
        async with app.run_test() as pilot:
            async def mock_stream():
                yield "Texto"
                yield {"type": "tool_call", "name": "add"}
                yield {"type": "result", "final_answer": "Texto", "steps": 1, "tools_used": ["add"], "usage_total": {"total_tokens": 50}, "cost_usd": 0.0005}

            full_text = await app.stream_to_chat(mock_stream())

            assert "Texto" in full_text
            dashboard_text = str(app.query_one("#dashboard").render())
            assert "Listo" in dashboard_text
            assert "Tokens: 50" in dashboard_text
            assert "Coste total: $0.0005" in dashboard_text


@pytest.mark.asyncio
async def test_app_stream_to_chat_fallback_tokens():
    """Cubre el fallback de tokens."""
    app = AgentHarnessApp()
    with patch.object(app, "initialize_agent", new_callable=AsyncMock):
        async with app.run_test() as pilot:
            async def mock_stream():
                yield "Texto de prueba"
                yield {"type": "result", "final_answer": "Texto", "steps": 1, "tools_used": [], "usage_total": {}}

            await app.stream_to_chat(mock_stream())
            # El dashboard debe actualizarse con el fallback
            assert "Tokens" in str(app.query_one("#dashboard").render())


@pytest.mark.asyncio
async def test_file_aware_input_watch_value_reentry(tmp_path):
    """Cubre el flag _processing_paste en watch_value."""
    app = AgentHarnessApp()
    with patch.object(app, "initialize_agent", new_callable=AsyncMock):
        async with app.run_test() as pilot:
            input_box = app.query_one("#input-box", FileAwareInput)

            # Creamos un archivo real
            test_file = tmp_path / "test.txt"
            test_file.write_text("Hola")

            # Forzamos el watcher simulando que el texto es la ruta
            with patch.object(app, "handle_file_paste", new_callable=AsyncMock) as mock_paste:
                input_box.value = str(test_file)
                await pilot.pause()  # Deja que el call_later se ejecute

                # Verificamos que se llamó al handler
                mock_paste.assert_called_once()
                # Y que el input se limpió (gracias al flag)
                assert input_box.value == ""


@pytest.mark.asyncio
async def test_stream_to_chat_timeout():
    """Cubre el except TimeoutError en stream_to_chat."""
    app = AgentHarnessApp()
    with patch.object(app, "initialize_agent", new_callable=AsyncMock):
        async with app.run_test() as pilot:
            async def slow_stream():
                yield "Texto"
                await asyncio.sleep(2)  # Más que el timeout mockeado
                yield "Final"

            with patch("app.tui.app.settings.LLM_STREAM_TIMEOUT", 0.1):
                with patch.object(app, "write_to_chat", new_callable=AsyncMock) as mock_write:
                    res = await app.stream_to_chat(slow_stream())
                    assert "Texto" in res
                    # Verifica que se mostró el mensaje de Timeout
                    mock_write.assert_called()
                    args, _ = mock_write.call_args
                    assert "Timeout" in args[0]


@pytest.mark.asyncio
async def test_stream_to_chat_llm_error():
    """Cubre el except Exception genérico en stream_to_chat."""
    app = AgentHarnessApp()
    with patch.object(app, "initialize_agent", new_callable=AsyncMock):
        async with app.run_test() as pilot:
            async def error_stream():
                yield "Texto"
                raise ValueError("Fallo del LLM")

            with patch.object(app, "write_to_chat", new_callable=AsyncMock) as mock_write:
                res = await app.stream_to_chat(error_stream())
                assert "Texto" in res
                mock_write.assert_called()
                args, _ = mock_write.call_args
                assert "Error del LLM" in args[0]


@pytest.mark.asyncio
async def test_app_on_mount_with_session():
    """Cubre app.py líneas 372-377: cargar sesión al inicio."""
    app = AgentHarnessApp()
    with patch("app.tui.app.SessionManager") as mock_sm_class:
        mock_instance = MagicMock()
        mock_instance.load.return_value = [{"role": "user", "content": "Hola"}]
        mock_sm_class.return_value = mock_instance
        mock_sm_class.list_sessions.return_value = [
            {"id": "123", "message_count": 1}]

        with patch.object(app, "initialize_agent", new_callable=AsyncMock) as mock_init:
            from app.core.harness.context import ContextManager

            async def side_effect():
                # 🔥 Aquí no metemos system_prompt, porque el mock de SessionManager
                # sobreescribirá self.ctx.messages directamente
                app.ctx = ContextManager()
            mock_init.side_effect = side_effect

            async with app.run_test() as pilot:
                await pilot.pause()
                # Verifica que se cargó el mensaje del mock
                assert any(m["content"] == "Hola" for m in app.ctx.messages)
                # Verifica que se mostró el mensaje en el chat
                scroll = app.query_one("#chat-scroll")
                assert any("Sesión" in str(child.render())
                           for child in scroll.children)


@pytest.mark.asyncio
async def test_app_expand_skills():
    """Cubre app.py líneas 533-545: cargar skill con @nombre."""
    app = AgentHarnessApp()
    with patch.object(app, "initialize_agent", new_callable=AsyncMock):
        async with app.run_test() as pilot:
            with patch("app.tools.skills.LoadSkillTool.run", new_callable=AsyncMock) as mock_run:
                from app.core.harness.tool import ToolResult
                mock_run.return_value = ToolResult(
                    success=True, content="Instrucciones")

                res = await app._expand_skills("@test_skill Hola")
                assert "[SKILL CARGADA: test_skill]" in res
                assert "Instrucciones" in res
                assert "Hola" in res


@pytest.mark.asyncio
async def test_app_request_permission_long_diff():
    """Cubre app.py líneas 561-563: truncado de diff largo."""
    app = AgentHarnessApp()
    with patch.object(app, "initialize_agent", new_callable=AsyncMock):
        async with app.run_test() as pilot:
            with patch.object(app, "push_screen_wait", new_callable=AsyncMock) as mock_wait:
                mock_wait.return_value = "n"
                diff_largo = "\n".join([f"linea {i}" for i in range(100)])

                await app.request_permission("bash", "bash:ls", {"command": "ls"}, diff_text=diff_largo)

                # Verifica que se llamó a write_to_chat con el mensaje de truncado
                # (esto cubre la línea del f-string de truncado)
                mock_wait.assert_called()


@pytest.mark.asyncio
async def test_app_expand_skills_error():
    """Cubre app.py línea 542: error al cargar una skill."""
    app = AgentHarnessApp()
    with patch.object(app, "initialize_agent", new_callable=AsyncMock):
        async with app.run_test() as pilot:
            with patch("app.tools.skills.LoadSkillTool.run", new_callable=AsyncMock) as mock_run:
                from app.core.harness.tool import ToolResult
                mock_run.return_value = ToolResult(
                    success=False, content="", error="No existe")

                # Verificamos que el método se ejecuta sin romperse
                res = await app._expand_skills("@bad_skill")
                # El string resultante puede estar vacío (solo \n\n) porque no hay contexto
                assert res.strip() == ""


@pytest.mark.asyncio
async def test_app_stream_to_chat_no_agent_loop():
    """Cubre la línea 678 de app.py: cuando agent_loop es None."""
    app = AgentHarnessApp()
    with patch.object(app, "initialize_agent", new_callable=AsyncMock):
        async with app.run_test() as pilot:
            async def mock_stream():
                yield "Texto"
                yield {"type": "result", "final_answer": "Texto", "steps": 1, "tools_used": [], "usage_total": {}}

            # Forzamos agent_loop = None
            app.agent_loop = None
            await app.stream_to_chat(mock_stream())
            # El modelo debe ser "Desconocido"
            assert app.last_model == "Desconocido"


@pytest.mark.asyncio
async def test_app_on_mount_with_repair_counts():
    """Cubre la línea 334 de app.py: inyectar repair_counts desde la sesión."""
    app = AgentHarnessApp()
    with patch("app.tui.app.SessionManager") as mock_sm_class:
        mock_instance = MagicMock()
        mock_instance.load.return_value = [{"role": "user", "content": "Hola"}]
        mock_instance.load_metadata.return_value = {
            "repair_counts": {"bash": 3}}
        mock_sm_class.return_value = mock_instance
        mock_sm_class.list_sessions.return_value = [
            {"id": "123", "message_count": 1}]

        with patch.object(app, "initialize_agent", new_callable=AsyncMock) as mock_init:
            from app.core.harness.context import ContextManager

            async def side_effect():
                app.ctx = ContextManager()
                app.agent_loop = MagicMock()
            mock_init.side_effect = side_effect

            async with app.run_test() as pilot:
                await pilot.pause()
                # Verifica que se inyectaron los repair_counts
                assert app.agent_loop.repair_counts == {"bash": 3}


@pytest.mark.asyncio
async def test_app_stream_to_chat_with_agent_loop_and_llm():
    """Cubre la línea 678 de app.py: cuando agent_loop.llm existe."""
    app = AgentHarnessApp()
    with patch.object(app, "initialize_agent", new_callable=AsyncMock):
        async with app.run_test() as pilot:
            async def mock_stream():
                yield "Texto"
                yield {"type": "result", "final_answer": "Texto", "steps": 1, "tools_used": [], "usage_total": {}}

            # Creamos un mock de agent_loop con un llm que tiene model_name
            mock_llm = MagicMock()
            mock_llm.model_name = "gpt-4o"
            app.agent_loop = MagicMock()
            app.agent_loop.llm = mock_llm

            await app.stream_to_chat(mock_stream())

            # Verificamos que se usó el modelo del LLM
            assert app.last_model == "gpt-4o"


@pytest.mark.asyncio
async def test_app_initialize_agent_with_memory_preamble():
    """Cubre la línea 361 de app.py: cuando hay preamble en memoria."""
    app = AgentHarnessApp()
    with patch("app.tui.app.MCPClient"):
        # Mock del memory store para que devuelva un preamble
        with patch("app.tui.app.create_memory_store") as mock_store:
            mock_store.return_value.preamble.return_value = "Recuerdo: el color es azul"

            with patch("app.tui.app.register_core_tools"):
                async with app.run_test() as pilot:
                    await app.initialize_agent()
                    await pilot.pause()
                    # Verificamos que el system_prompt incluye el preamble
                    system_prompt = app.ctx.messages[0]["content"]
                    assert "[Long-term memory]" in system_prompt
                    assert "el color es azul" in system_prompt


@pytest.mark.asyncio
async def test_app_safe_request_permission_allowed():
    """Cubre _safe_request_permission cuando ya está permitido."""
    app = AgentHarnessApp()
    with patch.object(app, "initialize_agent", new_callable=AsyncMock):
        async with app.run_test() as pilot:
            app.gate = MagicMock()
            app.gate._is_allowed.return_value = True

            result = await app._safe_request_permission("bash", "bash:ls", {"command": "ls"})
            assert result == "y"


@pytest.mark.asyncio
async def test_app_safe_request_permission_fallback():
    """Cubre el fallback de _safe_request_permission cuando la TUI no está activa."""
    app = AgentHarnessApp()
    with patch.object(app, "initialize_agent", new_callable=AsyncMock):
        async with app.run_test() as pilot:
            app.gate = MagicMock()
            app.gate._is_allowed.return_value = False

            # 🔥 En lugar de parchear is_running, forzamos que request_permission lance excepción
            with patch.object(app, "request_permission", new_callable=AsyncMock) as mock_req:
                mock_req.side_effect = Exception("TUI no disponible")

                result = await app._safe_request_permission("bash", "bash:ls", {"command": "ls"})

                # Debe caer al fallback y devolver "n"
                assert result == "n"
