import asyncio
from contextlib import AsyncExitStack
import os
from typing import Any
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from app.core.harness.tool import BaseTool, ToolRegistry, ToolResult
from app.core.logger import logger


class MCPClient:
    """Client to connect to an MCP server."""

    def __init__(self, command: str, args: list[str], env: dict[str, str] | None = None):
        server_env = os.environ.copy()
        if env:
            server_env.update(env)

        self.server_params = StdioServerParameters(
            command=command,
            args=args,
            env=server_env
        )
        self.session: ClientSession | None = None
        self.exit_stack = AsyncExitStack()

    async def connect(self):
        """Start MCP server subprocess and create session."""
        try:
            read, write = await self.exit_stack.enter_async_context(
                stdio_client(self.server_params)
            )
            self.session = await self.exit_stack.enter_async_context(
                ClientSession(read, write)
            )
            await self.session.initialize()
        except Exception as e:
            logger.error(f"Error connecting to MCP server: {e}")
            raise

    async def disconnect(self):
        """Close connection cleanly."""
        await self.exit_stack.aclose()

    async def register_tools(self, registry: ToolRegistry, server_name: str = "unknown"):
        """Discover MCP server tools and register them in the Harness."""
        if not self.session:
            raise RuntimeError("Not connected. Call connect() first.")

        mcp_tools = await self.session.list_tools()

        for mcp_tool in mcp_tools.tools:
            tool = MCPToolProxy(
                name=mcp_tool.name,
                description=mcp_tool.description or "",
                parameters_schema=mcp_tool.input_schema,
                session=self.session,
                server_name=server_name
            )
            registry.register(tool)


class MCPToolProxy(BaseTool):
    """Adapter that wraps a remote MCP tool so AgentLoop can use it."""

    def __init__(self, name: str, description: str, parameters_schema: dict, session: ClientSession, server_name: str = "unknown"):
        self.name = name
        self.description = f"[MCP:{server_name}] {description}"
        self.parameters_schema = parameters_schema
        self.session = session
        self.server_name = server_name

    async def run(self, **kwargs) -> ToolResult:
        try:
            result = await self.session.call_tool(self.name, arguments=kwargs)

            content_str = ""
            for item in result.content:
                if item.type == "text":
                    content_str += item.text + "\n"
                else:
                    content_str += f"[{item.type} data]\n"

            if result.isError:
                return ToolResult(success=False, content="", error=content_str.strip())

            return ToolResult(success=True, content=content_str.strip())
        except Exception as e:
            return ToolResult(success=False, content="", error=str(e))
