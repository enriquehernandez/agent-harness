import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.mcp.client import MCPClient, MCPToolProxy
from app.core.harness.tool import ToolRegistry


@pytest.mark.asyncio
@patch("app.mcp.client.stdio_client")
@patch("app.mcp.client.ClientSession")
async def test_mcp_client_full_flow(mock_session_class, mock_stdio_client):
    # 1. Configuramos los mocks
    mock_read = MagicMock()
    mock_write = MagicMock()

    # Mock del context manager stdio_client
    mock_stdio_client.return_value.__aenter__ = AsyncMock(
        return_value=(mock_read, mock_write))
    mock_stdio_client.return_value.__aexit__ = AsyncMock()

    # Mock de ClientSession
    mock_session = mock_session_class.return_value.__aenter__.return_value
    mock_session.initialize = AsyncMock()

    # Mock de list_tools
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
    await client.register_tools(registry)
    await client.disconnect()

    # 3. Verificaciones
    mock_session.initialize.assert_called_once()
    assert "test_tool" in registry.names()
    assert registry.get("test_tool").description == "[MCP:unknown] Una tool"


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
