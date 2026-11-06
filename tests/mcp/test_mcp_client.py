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
    assert registry.get("test_tool").description == "[MCP] Una tool"


@pytest.mark.asyncio
@patch("app.mcp.client.stdio_client")
@patch("app.mcp.client.ClientSession")
async def test_mcp_client_connect_error(mock_session_class, mock_stdio_client):
    # Si no se llama connect, register_tools debe fallar
    client = MCPClient(command="test", args=[])
    registry = ToolRegistry()

    with pytest.raises(RuntimeError, match="No conectado"):
        await client.register_tools(registry)


@pytest.mark.asyncio
async def test_mcp_tool_proxy_success():
    mock_session = AsyncMock()

    mock_content = MagicMock()
    mock_content.type = "text"
    mock_content.text = "Resultado simulado MCP"

    mock_result = MagicMock()
    mock_result.content = [mock_content]
    mock_result.isError = False
    mock_session.call_tool.return_value = mock_result

    proxy = MCPToolProxy(name="test", description="desc",
                         parameters_schema={}, session=mock_session)
    result = await proxy.run(param="value")

    assert result.success is True
    assert result.content == "Resultado simulado MCP"
    mock_session.call_tool.assert_called_once_with(
        "test", arguments={"param": "value"})


@pytest.mark.asyncio
async def test_mcp_tool_proxy_error():
    mock_session = AsyncMock()

    mock_content = MagicMock()
    mock_content.type = "text"
    mock_content.text = "Fallo en MCP"

    mock_result = MagicMock()
    mock_result.content = [mock_content]
    mock_result.isError = True
    mock_session.call_tool.return_value = mock_result

    proxy = MCPToolProxy(name="test", description="desc",
                         parameters_schema={}, session=mock_session)
    result = await proxy.run()

    assert result.success is False
    assert result.error == "Fallo en MCP"


@pytest.mark.asyncio
async def test_mcp_tool_proxy_exception():
    from app.mcp.client import MCPToolProxy
    mock_session = AsyncMock()
    mock_session.call_tool.side_effect = Exception("Network Error")

    proxy = MCPToolProxy(name="test", description="",
                         parameters_schema={}, session=mock_session)
    res = await proxy.run()

    assert res.success is False
    assert res.error == "Network Error"


@pytest.mark.asyncio
async def test_mcp_tool_proxy_non_text_content():
    from app.mcp.client import MCPToolProxy
    mock_session = AsyncMock()

    mock_content = MagicMock()
    mock_content.type = "image"  # No es text

    mock_result = MagicMock()
    mock_result.content = [mock_content]
    mock_result.isError = False
    mock_session.call_tool.return_value = mock_result

    proxy = MCPToolProxy(name="test", description="",
                         parameters_schema={}, session=mock_session)
    res = await proxy.run()
    assert "[image data]" in res.content  # Cubre línea 76
