import pytest
from app.core.llm.base import LLMResponse
from app.core.llm.providers.fake import FakeLLM
from app.core.harness.tool import ToolRegistry, FunctionTool


@pytest.fixture
def fake_llm():
    """Retorna un FakeLLM listo para inyectarle respuestas."""
    return FakeLLM()


@pytest.fixture
def basic_registry():
    """Retorna un registry con una tool de suma simple."""
    registry = ToolRegistry()

    def add(a: int, b: int) -> int:
        return a + b

    registry.register(FunctionTool(
        name="add",
        description="Suma dos números",
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
