import pytest
from app.core.llm.base import LLMResponse
from app.core.llm.providers.fake import FakeLLM
from app.core.harness.tool import ToolRegistry, FunctionTool


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
