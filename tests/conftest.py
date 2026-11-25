import pytest
from unittest.mock import AsyncMock, patch

from app.core.llm.base import LLMResponse
from app.core.llm.providers.fake import FakeLLM
from app.core.harness.hooks import HookOutcome
from app.core.harness.tool import ToolRegistry, FunctionTool


@pytest.fixture(autouse=True)
def no_real_loop_hooks():
    """Los tests del loop no deben depender del hooks.json local del usuario.

    Los tests que verifican hooks parchean `emit_hook` explícitamente; el resto
    recibe un no-op para no llamar a LLM/HTTP reales.
    """
    with patch("app.core.harness.loop.emit_hook", new_callable=AsyncMock) as emit:
        emit.return_value = HookOutcome()
        yield emit


@pytest.fixture
def fake_llm():
    """Returns a FakeLLM ready to inject responses."""
    return FakeLLM()


@pytest.fixture
def basic_registry():
    """Returns a registry with a simple add tool."""
    registry = ToolRegistry()

    def add(a: int, b: int) -> int:
        return a + b

    registry.register(FunctionTool(
        name="add",
        description="Adds two numbers",
        parameters_schema={
            "type": "object",
            "properties": {
                "a": {"type": "integer"},
                "b": {"type": "integer"},
            },
            "required": ["a", "b"]
        },
        func=add
    ))
    return registry
