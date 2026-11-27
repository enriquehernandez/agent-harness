import pytest
from unittest.mock import patch
from textual.app import App
from app.tui.debug_screen import DebugDetailScreen
from textual.widgets import Static


class DebugTestApp(App):
    def on_mount(self):
        self.push_screen(DebugDetailScreen(title="Test", payload='{"a": 1}'))


@pytest.mark.asyncio
async def test_debug_screen_mount_and_render():
    app = DebugTestApp()
    async with app.run_test() as pilot:
        assert isinstance(app.screen, DebugDetailScreen)
        # Verifica que se renderizó el JSON
        detail = app.screen.query_one("#detail-content")
        assert detail is not None


@pytest.mark.asyncio
async def test_debug_screen_close():
    app = DebugTestApp()
    async with app.run_test() as pilot:
        assert isinstance(app.screen, DebugDetailScreen)
        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, DebugDetailScreen)


@pytest.mark.asyncio
async def test_debug_screen_falls_back_when_syntax_fails():
    """Si Syntax no puede resaltar el payload, se muestra el texto plano."""
    class DebugFallbackApp(App):
        def on_mount(self):
            self.push_screen(DebugDetailScreen(title="Roto", payload="texto"))

    app = DebugFallbackApp()
    with patch("app.tui.debug_screen.Syntax", side_effect=Exception("Sin syntax")):
        async with app.run_test() as pilot:
            container = app.screen.query_one("#detail-content")
            static = container.query_one(Static)
            assert str(static.render()) == "texto"
