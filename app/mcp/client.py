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

# Variables de ejecución necesarias para lanzar procesos; nunca credenciales.
_SAFE_ENV_KEYS = frozenset({
    "PATH", "HOME", "LANG", "LC_ALL", "TMPDIR", "TEMP", "TMP",
    "USER", "LOGNAME", "SHELL", "TERM", "SYSTEMROOT", "COMSPEC",
    "XDG_CACHE_HOME", "XDG_CONFIG_HOME",
})


def _build_server_env(env: dict[str, str] | None,
                      allowed_env: list[str] | None) -> dict[str, str]:
    """Entrega al hijo solo variables seguras y las permitidas explícitamente."""
    keys = _SAFE_ENV_KEYS | set(allowed_env or [])
    server_env = {name: os.environ[name] for name in keys if name in os.environ}
    if env:
        server_env.update(env)
    return server_env


class MCPClient:
    """Client to connect to an MCP server with exponential backoff."""

    def __init__(self, command: str, args: list[str],
                 env: dict[str, str] | None = None,
                 allowed_env: list[str] | None = None):
        server_env = _build_server_env(env, allowed_env)

        self.command = command
        self.args = args
        self.env = server_env
        self.server_params = StdioServerParameters(
            command=command,
            args=args,
            env=server_env,
        )
        self.session: ClientSession | None = None
        self.exit_stack = AsyncExitStack()

    async def _do_connect(self):
        """Lógica interna de conexión (extraída para tenacity)."""
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
        reraise=True,
    )
    async def connect(self):
        """Conecta con backoff exponencial (3 intentos)."""
        if self.session is not None:
            return

        try:
            await asyncio.wait_for(
                self._do_connect(),
                timeout=settings.MCP_CONNECT_TIMEOUT,
            )
            logger.info(f"MCP conectado exitosamente: {self.command}")
            return
        except asyncio.TimeoutError:
            logger.warning(f"Timeout conectando a MCP {self.command}")
            raise
        except Exception as e:
            logger.warning(f"Error conectando a MCP {self.command}: {e}")
            raise

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
            await self.disconnect()
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
            prefixed_name = f"mcp_{server_name}_{mcp_tool.name}"
            tool = MCPToolProxy(
                name=prefixed_name,
                original_name=mcp_tool.name,
                description=mcp_tool.description or "",
                parameters_schema=mcp_tool.input_schema or {
                    "type": "object", "properties": {}},
                client=self,
                server_name=server_name,
            )
            registry.register(tool)


class MCPToolProxy(BaseTool):
    """Adapter que envuelve una tool MCP remota con auto-reconexión."""

    def __init__(
        self,
        name: str,
        description: str,
        parameters_schema: dict,
        client: MCPClient,
        server_name: str = "unknown",
        original_name: str | None = None,
    ):
        self.name = name
        self.description = f"[MCP] ({server_name}) {description}"
        self.parameters_schema = parameters_schema
        self.client = client
        self.server_name = server_name
        self.original_name = original_name or name

    async def _call(self, **kwargs) -> ToolResult:
        result = await asyncio.wait_for(
            self.client.session.call_tool(
                self.original_name, arguments=kwargs),
            timeout=settings.TOOL_TIMEOUT,
        )

        content_str = ""
        for item in getattr(result, "content", []) or []:
            if getattr(item, "type", None) == "text":
                content_str += item.text + "\n"
            else:
                content_str += f"[{getattr(item, 'type', 'unknown')} data]\n"

        is_error = getattr(result, "isError", False) or getattr(
            result, "is_error", False)

        if is_error:
            return ToolResult(success=False, content="", error=content_str.strip())

        return ToolResult(success=True, content=content_str.strip())

    async def run(self, **kwargs) -> ToolResult:
        try:
            if not self.client.session:
                if not await self.client.reconnect():
                    return ToolResult(
                        success=False, content="",
                        error=f"MCP {self.server_name} no disponible.",
                    )
            return await self._call(**kwargs)

        except Exception as e:
            logger.warning(
                f"Fallo en tool MCP {self.name}: {e}. Intentando reconexión...")

            if await self.client.reconnect():
                try:
                    return await self._call(**kwargs)
                except Exception as retry_error:
                    return ToolResult(
                        success=False, content="",
                        error=f"Fallo tras reconexión: {retry_error}",
                    )

            return ToolResult(success=False, content="", error=str(e))
