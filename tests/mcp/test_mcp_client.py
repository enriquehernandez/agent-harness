import json
import re
from pathlib import Path

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.mcp.client import MCPClient, MCPToolProxy
from app.core.harness.tool import ToolRegistry


def test_mcp_client_does_not_inherit_secrets(monkeypatch):
    """El entorno del hijo no incluye claves ni tokens del proceso padre."""
    monkeypatch.setenv("PATH", "/bin:/usr/bin")
    monkeypatch.setenv("OPENAI_API_KEY", "VALOR_DE_PRUEBA_NO_FILTRAR")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "VALOR_DE_PRUEBA_NO_FILTRAR")
    monkeypatch.setenv("MY_TOKEN", "VALOR_DE_PRUEBA_NO_FILTRAR")

    client = MCPClient("test", [], env={"CUSTOM_ENV": "value"})

    assert client.env["PATH"] == "/bin:/usr/bin"
    assert client.env["CUSTOM_ENV"] == "value"
    for secret_name in ("OPENAI_API_KEY", "LANGFUSE_SECRET_KEY", "MY_TOKEN"):
        assert secret_name not in client.env
    assert client.server_params.env == client.env


def test_mcp_client_forwards_only_allowed_env(monkeypatch):
    """Solo las variables permitidas explícitamente se copian del padre."""
    monkeypatch.setenv("HARNESS_E2E", "1")
    monkeypatch.setenv("OTRO_SECRETO", "no-debe-filtrarse")

    client = MCPClient("test", [], allowed_env=["HARNESS_E2E"])

    assert client.env.get("HARNESS_E2E") == "1"
    assert "OTRO_SECRETO" not in client.env


def test_mcp_config_pins_external_tool_versions():
    """Los servidores externos usan versiones fijas, no `latest` implícito."""
    config = json.loads(Path("mcp_config.json").read_text(encoding="utf-8"))
    uvx_packages = [
        conf["args"][0]
        for conf in config["mcpServers"].values()
        if conf["command"] == "uvx"
    ]

    assert uvx_packages
    assert all(re.fullmatch(r"[A-Za-z0-9._-]+==[A-Za-z0-9._-]+", package)
               for package in uvx_packages)

    wrapper = Path("scripts/filesystem_mcp_wrapper.sh").read_text(
        encoding="utf-8")
    assert re.search(
        r"@modelcontextprotocol/server-filesystem@[0-9]+\.[0-9]+\.[0-9]+",
        wrapper)


@pytest.mark.asyncio
@patch("app.mcp.client.stdio_client")
@patch("app.mcp.client.ClientSession")
async def test_mcp_client_full_flow(mock_session_class, mock_stdio_client):
    # 1. Configuramos los mocks
    mock_read = MagicMock()
    mock_write = MagicMock()

    mock_stdio_client.return_value.__aenter__ = AsyncMock(
        return_value=(mock_read, mock_write))
    mock_stdio_client.return_value.__aexit__ = AsyncMock()

    mock_session = mock_session_class.return_value.__aenter__.return_value
    mock_session.initialize = AsyncMock()

    mock_tool = MagicMock()
    mock_tool.name = "test_tool"
    mock_tool.description = "Una tool"
    mock_tool.input_schema = {"type": "object"}
    mock_session.list_tools = AsyncMock(
        return_value=MagicMock(tools=[mock_tool]))

    # 2. Ejecutamos el cliente
    client = MCPClient(command="test", args=[])
    await client.connect()

    registry = ToolRegistry()
    await client.register_tools(registry, server_name="fs")
    await client.disconnect()

    # 3. Verificaciones
    mock_session.initialize.assert_called_once()

    # ✅ El nombre está prefijado (Bug 6)
    expected_name = "mcp_fs_test_tool"
    assert expected_name in registry.names(), (
        f"Esperaba '{expected_name}', tengo: {registry.names()}"
    )

    tool = registry.get(expected_name)
    assert tool.description == "[MCP] (fs) Una tool"
    assert tool.original_name == "test_tool"  # 🔥 el nombre original se conserva


@pytest.mark.asyncio
@patch("app.mcp.client.stdio_client")
@patch("app.mcp.client.ClientSession")
async def test_mcp_client_connect_error(mock_session_class, mock_stdio_client):
    # Si no se llama connect, register_tools debe fallar
    client = MCPClient(command="test", args=[])
    registry = ToolRegistry()

    with pytest.raises(RuntimeError, match="Not connected"):
        await client.register_tools(registry)


@pytest.mark.asyncio
async def test_mcp_tool_proxy_success():
    from app.mcp.client import MCPToolProxy, MCPClient
    from unittest.mock import AsyncMock, MagicMock

    mock_client = MagicMock(spec=MCPClient)
    mock_client.session = AsyncMock()

    mock_content = MagicMock()
    mock_content.type = "text"
    mock_content.text = "Resultado simulado MCP"

    mock_result = MagicMock()
    mock_result.content = [mock_content]
    mock_result.isError = False
    mock_result.is_error = False

    mock_client.session.call_tool.return_value = mock_result

    proxy = MCPToolProxy(name="test", description="desc",
                         parameters_schema={}, client=mock_client)
    result = await proxy.run()

    assert result.success is True
    assert "Resultado simulado MCP" in result.content


@pytest.mark.asyncio
async def test_mcp_tool_proxy_error():
    from app.mcp.client import MCPToolProxy, MCPClient
    from unittest.mock import AsyncMock, MagicMock

    mock_client = MagicMock(spec=MCPClient)
    mock_client.session = AsyncMock()

    mock_content = MagicMock()
    mock_content.type = "text"
    mock_content.text = "Fallo en MCP"

    mock_result = MagicMock()
    mock_result.content = [mock_content]
    mock_result.isError = True

    mock_client.session.call_tool.return_value = mock_result

    proxy = MCPToolProxy(name="test", description="desc",
                         parameters_schema={}, client=mock_client)
    result = await proxy.run()

    assert result.success is False
    assert "Fallo en MCP" in result.error


@pytest.mark.asyncio
async def test_mcp_tool_proxy_exception():
    from app.mcp.client import MCPToolProxy, MCPClient
    from unittest.mock import AsyncMock, MagicMock

    mock_client = MagicMock(spec=MCPClient)
    mock_client.session = AsyncMock()
    mock_client.session.call_tool.side_effect = Exception("Network Error")

    # Simulamos que la reconexión falla
    mock_client.reconnect = AsyncMock(return_value=False)

    proxy = MCPToolProxy(name="test", description="",
                         parameters_schema={}, client=mock_client)
    result = await proxy.run()

    assert result.success is False
    assert "Network Error" in result.error


@pytest.mark.asyncio
async def test_mcp_tool_proxy_non_text_content():
    from app.mcp.client import MCPToolProxy, MCPClient
    from unittest.mock import AsyncMock, MagicMock

    mock_client = MagicMock(spec=MCPClient)
    mock_client.session = AsyncMock()

    mock_content = MagicMock()
    mock_content.type = "image"

    mock_result = MagicMock()
    mock_result.content = [mock_content]
    mock_result.isError = False
    mock_result.is_error = False

    mock_client.session.call_tool.return_value = mock_result

    proxy = MCPToolProxy(name="test", description="",
                         parameters_schema={}, client=mock_client)
    result = await proxy.run()

    assert result.success is True
    assert "[image data]" in result.content


@pytest.mark.asyncio
async def test_mcp_disconnect_exception():
    client = MCPClient(command="test", args=[])
    client.exit_stack.aclose = AsyncMock(
        side_effect=Exception("Disconnect error"))
    await client.disconnect()
    assert client.session is None


@pytest.mark.asyncio
@patch("app.mcp.client.stdio_client")
@patch("app.mcp.client.ClientSession")
async def test_mcp_client_connection_error_and_env(mock_session_class, mock_stdio_client):
    """Cubre el env custom (línea 17) y el except de connect (línea 37-39)."""
    mock_stdio_client.return_value.__aenter__ = AsyncMock(
        side_effect=Exception("Connection failed"))

    client = MCPClient(command="test", args=[], env={"CUSTOM_ENV": "value"})
    assert client.server_params.env["CUSTOM_ENV"] == "value"

    with pytest.raises(Exception, match="Connection failed"):
        await client.connect()
