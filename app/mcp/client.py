import asyncio
from contextlib import AsyncExitStack
import os
from typing import Any
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from app.core.harness.tool import BaseTool, ToolRegistry, ToolResult
from app.core.logger import logger
from app.core.config import settings


class MCPClient:
    """Client to connect to an MCP server with exponential backoff."""

    def __init__(self, command: str, args: list[str], env: dict[str, str] | None = None):
        server_env = os.environ.copy()
        if env:
            server_env.update(env)

        self.command = command
        self.args = args
        self.env = server_env
        self.server_params = StdioServerParameters(
            command=command,
            args=args,
            env=server_env
        )
        self.session: ClientSession | None = None
        self.exit_stack = AsyncExitStack()

    async def _do_connect(self):
        """Lógica interna de conexión (extraída para tenacity)."""
        # Limpiamos cualquier conexión previa
        await self.disconnect()
        self.exit_stack = AsyncExitStack()

        read, write = await self.exit_stack.enter_async_context(
            stdio_client(self.server_params)
        )
        self.session = await self.exit_stack.enter_async_context(
            ClientSession(read, write)
        )
        await self.session.initialize()
        logger.info(f"MCP conectado exitosamente: {self.command}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(Exception),
        reraise=True
    )
    async def connect(self):
        """Conecta con backoff exponencial (3 intentos)."""
        for attempt in range(3):
            try:
                # Usamos wait_for para el timeout de conexión
                await asyncio.wait_for(
                    self._do_connect(),
                    timeout=settings.MCP_CONNECT_TIMEOUT
                )
                logger.info(f"MCP conectado exitosamente: {self.command}")
                return
            except asyncio.TimeoutError:
                logger.warning(
                    f"Timeout conectando a MCP {self.command} (intento {attempt + 1}/3)")
                if attempt == 2:
                    raise
            except Exception as e:
                logger.warning(
                    f"Error conectando a MCP {self.command}: {e} (intento {attempt + 1}/3)")
                if attempt == 2:
                    raise
            await asyncio.sleep(2 ** attempt)  # 1s, 2s

    async def disconnect(self):
        """Cierra la conexión limpiamente."""
        try:
            await self.exit_stack.aclose()
        except Exception:
            pass
        self.session = None

    async def reconnect(self) -> bool:
        """Fuerza una reconexión (usada por el proxy si una tool falla)."""
        try:
            await self.connect()
            return True
        except Exception as e:
            logger.error(f"Reconexión fallida para MCP {self.command}: {e}")
            return False

    async def register_tools(self, registry: ToolRegistry, server_name: str = "unknown"):
        """Descubre tools y las registra."""
        if not self.session:
            raise RuntimeError("Not connected. Call connect() first.")

        mcp_tools = await self.session.list_tools()

        for mcp_tool in mcp_tools.tools:
            tool = MCPToolProxy(
                name=mcp_tool.name,
                description=mcp_tool.description or "",
                parameters_schema=mcp_tool.input_schema,
                client=self,  # 🔥 Pasamos el cliente, no la sesión
                server_name=server_name
            )
            registry.register(tool)


class MCPToolProxy(BaseTool):
    """Adapter que envuelve una tool MCP remota con auto-reconexión."""

    def __init__(self, name: str, description: str, parameters_schema: dict, client: MCPClient, server_name: str = "unknown"):
        self.name = name
        self.description = f"[MCP:{server_name}] {description}"
        self.parameters_schema = parameters_schema
        self.client = client
        self.server_name = server_name

    async def run(self, **kwargs) -> ToolResult:
        try:
            if not self.client.session:
                # Si no hay sesión, intentamos reconectar
                if not await self.client.reconnect():
                    return ToolResult(success=False, content="", error=f"MCP {self.server_name} no disponible.")

            result = await self.client.session.call_tool(self.name, arguments=kwargs)

            content_str = ""
            for item in result.content:
                if item.type == "text":
                    content_str += item.text + "\n"
                else:
                    content_str += f"[{item.type} data]\n"

            is_error = getattr(result, "isError", False) or getattr(
                result, "is_error", False)

            if is_error:
                return ToolResult(success=False, content="", error=content_str.strip())

            return ToolResult(success=True, content=content_str.strip())

        except Exception as e:
            logger.warning(
                f"Fallo en tool MCP {self.name}: {e}. Intentando reconexión...")

            # 🔥 Fallback: Si falla, reconectamos y reintentamos UNA vez
            if await self.client.reconnect():
                try:
                    result = await self.client.session.call_tool(self.name, arguments=kwargs)
                    content_str = ""
                    for item in result.content:
                        if item.type == "text":
                            content_str += item.text + "\n"
                    return ToolResult(success=True, content=content_str.strip())
                except Exception as retry_error:
                    return ToolResult(success=False, content="", error=f"Fallo tras reconexión: {retry_error}")

            return ToolResult(success=False, content="", error=str(e))
