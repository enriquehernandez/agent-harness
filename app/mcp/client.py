import asyncio
from contextlib import AsyncExitStack
from typing import Any
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from app.core.harness.tool import BaseTool, ToolRegistry, ToolResult


class MCPClient:
    """Cliente para conectarse a un servidor MCP."""

    def __init__(self, command: str, args: list[str], env: dict[str, str] | None = None):
        self.server_params = StdioServerParameters(
            command=command,
            args=args,
            env=env
        )
        self.session: ClientSession | None = None
        self.exit_stack = AsyncExitStack()

    async def connect(self):
        """Inicia el subproceso del servidor MCP y crea la sesión."""
        # Inicia el transporte stdio
        read, write = await self.exit_stack.enter_async_context(
            stdio_client(self.server_params)
        )
        # Inicia la sesión con el servidor
        self.session = await self.exit_stack.enter_async_context(
            ClientSession(read, write)
        )
        await self.session.initialize()

    async def disconnect(self):
        """Cierra la conexión limpiamente."""
        await self.exit_stack.aclose()

    async def register_tools(self, registry: ToolRegistry):
        """Descubre las herramientas del servidor MCP y las registra en el Harness."""
        if not self.session:
            raise RuntimeError("No conectado. Llama a connect() primero.")

        # 1. Pedir la lista de herramientas al servidor MCP
        mcp_tools = await self.session.list_tools()

        # 2. Convertir cada herramienta MCP en una Tool del Harness
        for mcp_tool in mcp_tools.tools:
            tool = MCPToolProxy(
                name=mcp_tool.name,
                description=mcp_tool.description or "",
                parameters_schema=mcp_tool.input_schema,
                session=self.session
            )
            registry.register(tool)


class MCPToolProxy(BaseTool):
    """Adaptador que envuelve una herramienta remota MCP para que el AgentLoop la use."""

    def __init__(self, name: str, description: str, parameters_schema: dict, session: ClientSession):
        self.name = name
        self.description = f"[MCP] {description}"
        self.parameters_schema = parameters_schema
        self.session = session

    async def run(self, **kwargs) -> ToolResult:
        try:
            # Llamar a la herramienta remota a través del protocolo MCP
            result = await self.session.call_tool(self.name, arguments=kwargs)

            # Extraer el texto del resultado (MCP devuelve una lista de bloques de contenido)
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
