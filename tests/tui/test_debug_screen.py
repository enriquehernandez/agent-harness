import pytest
from textual.app import App
from app.tui.debug_screen import DebugDetailScreen
from textual.widgets import Static


class TestDebugApp(App):
    def on_mount(self):
        self.push_screen(DebugDetailScreen(title="Test", payload='{"a": 1}'))


@pytest.mark.asyncio
async def test_debug_screen_mount_and_render():
    app = TestDebugApp()
    async with app.run_test() as pilot:
        assert isinstance(app.screen, DebugDetailScreen)
        # Verifica que se renderizó el JSON
        detail = app.screen.query_one("#detail-content")
        assert detail is not None


@pytest.mark.asyncio
async def test_debug_screen_close():
    app = TestDebugApp()
    async with app.run_test() as pilot:
        assert isinstance(app.screen, DebugDetailScreen)
        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, DebugDetailScreen)
