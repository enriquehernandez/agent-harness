from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class ToolResult:
    """Normalized result from a tool execution."""
    success: bool
    content: str
    error: str | None = None


class BaseTool(ABC):
    """Interface for a local tool."""
    name: str
    description: str
    parameters_schema: dict[str, Any]

    @abstractmethod
    async def run(self, **kwargs) -> ToolResult:
        ...

    def to_openai_schema(self) -> dict[str, Any]:
        """Format expected by OpenAI/OpenRouter/Groq for tool calling."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters_schema,
            },
        }


class FunctionTool(BaseTool):
    """Tool created from a simple function (useful for tests)."""

    def __init__(
        self,
        name: str,
        description: str,
        parameters_schema: dict[str, Any],
        func: Callable[..., Any],
    ):
        self.name = name
        self.description = description
        self.parameters_schema = parameters_schema
        self._func = func

    async def run(self, **kwargs) -> ToolResult:
        try:
            result = self._func(**kwargs)
            if hasattr(result, "__await__"):  # is async
                result = await result
            return ToolResult(success=True, content=str(result))
        except Exception as e:
            return ToolResult(success=False, content="", error=str(e))


class ToolRegistry:
    """Registry of available tools."""

    def __init__(self):
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    def all_schemas(self) -> list[dict[str, Any]]:
        return [t.to_openai_schema() for t in self._tools.values()]

    def names(self) -> list[str]:
        return list(self._tools.keys())

    def __contains__(self, name: str) -> bool:
        return name in self._tools
