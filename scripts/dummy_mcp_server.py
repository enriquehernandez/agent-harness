# scripts/dummy_mcp_server.py
from mcp.server.mcpserver import MCPServer  # 🔥 Cambio de import
import platform
import sys

# 🔥 FastMCP → MCPServer
mcp = MCPServer("DummyServer")


@mcp.tool()
def get_system_info() -> str:
    """Devuelve información sobre el sistema operativo actual."""
    return f"OS: {platform.system()} {platform.release()}\nPython: {sys.version}"


@mcp.tool()
def echo_message(message: str) -> str:
    """Hace eco de un mensaje. Útil para probar la conexión."""
    return f"El servidor MCP dice: {message}"


if __name__ == "__main__":
    mcp.run()  # En v2, run() por defecto usa stdio
