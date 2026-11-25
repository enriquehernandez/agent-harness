"""Aislamiento de la TUI: los tests no deben depender del hooks.json local.

Los tests que quieren comprobar los hooks parchean `emit_hook` explícitamente;
el resto recibe un no-op para que la configuración del usuario (con LLM reales)
no introduzca latencia ni llamadas de red.
"""

import pytest
from unittest.mock import AsyncMock, patch

from app.core.harness.hooks import HookOutcome


@pytest.fixture(autouse=True)
def no_real_hooks():
    with patch("app.tui.app.emit_hook", new_callable=AsyncMock) as emit:
        emit.return_value = HookOutcome()
        yield emit
