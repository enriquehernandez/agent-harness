import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.mcp.client import MCPClient, MCPToolProxy
from app.core.harness.tool import ToolResult


@pytest.mark.asyncio
async def test_mcp_connect_backoff_success():
    """Verifica que connect reintenta hasta 3 veces."""
    client = MCPClient(command="uv", args=["run", "dummy.py"])

    # Simulamos que falla 2 veces y a la 3ª funciona
    with patch.object(client, "_do_connect", new_callable=AsyncMock) as mock_connect:
        mock_connect.side_effect = [
            Exception("Fail 1"), Exception("Fail 2"), None]

        # Mockeamos el sleep para que no espere de verdad
        with patch("asyncio.sleep", new_callable=AsyncMock):
            await client.connect()

        assert mock_connect.call_count == 3


@pytest.mark.asyncio
async def test_mcp_connect_fails_all():
    """Verifica que connect falla tras 3 intentos."""
    client = MCPClient(command="uv", args=["run", "dummy.py"])

    with patch.object(client, "_do_connect", new_callable=AsyncMock) as mock_connect:
        mock_connect.side_effect = Exception("Fail")

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(Exception):
                await client.connect()


@pytest.mark.asyncio
async def test_mcp_tool_proxy_auto_reconnect():
    """Verifica que si una tool falla, reconecta y reintenta."""
    client = MCPClient(command="uv", args=["run", "dummy.py"])
    proxy = MCPToolProxy(name="test_tool", description="",
                         parameters_schema={}, client=client)

    # Mock de la sesión: la primera vez falla, la segunda funciona
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(type="text", text="OK")]
    mock_response.isError = False
    mock_response.is_error = False

    mock_session.call_tool = AsyncMock(
        side_effect=[Exception("Conexión caída"), mock_response])
    client.session = mock_session

    # Mock del reconnect (le decimos que siempre funciona)
    with patch.object(client, "reconnect", new_callable=AsyncMock, return_value=True):
        result = await proxy.run(param="value")

        assert result.success is True
        assert "OK" in result.content
        assert mock_session.call_tool.call_count == 2


@pytest.mark.asyncio
async def test_mcp_reconnect_success():
    """Cubre la línea 87: reconnect exitoso."""
    client = MCPClient(command="uv", args=["run", "dummy.py"])
    with patch.object(client, "connect", new_callable=AsyncMock) as mock_connect:
        mock_connect.return_value = None
        assert await client.reconnect() is True
        mock_connect.assert_called_once()


@pytest.mark.asyncio
async def test_mcp_reconnect_fails():
    """Cubre la línea 89-91: reconnect falla."""
    client = MCPClient(command="uv", args=["run", "dummy.py"])
    with patch.object(client, "connect", new_callable=AsyncMock) as mock_connect:
        mock_connect.side_effect = Exception("Fallo de conexión")
        assert await client.reconnect() is False
        mock_connect.assert_called_once()


@pytest.mark.asyncio
async def test_mcp_proxy_no_session_reconnect_fails():
    """Cubre la línea 126: no hay sesión y reconnect falla."""
    client = MCPClient(command="uv", args=["run", "dummy.py"])
    client.session = None

    # Mock de reconnect que devuelve False
    client.reconnect = AsyncMock(return_value=False)

    proxy = MCPToolProxy(name="test", description="",
                         parameters_schema={}, client=client)
    result = await proxy.run()

    assert result.success is False
    assert "no disponible" in result.error


@pytest.mark.asyncio
async def test_mcp_proxy_fallback_retry_fails():
    """Cubre la línea 152: fallback de reconexión falla al reintentar."""
    client = MCPClient(command="uv", args=["run", "dummy.py"])

    # Mock de la sesión: falla la primera vez
    mock_session = MagicMock()
    mock_session.call_tool = AsyncMock(side_effect=Exception("Error inicial"))
    client.session = mock_session

    # Mock de reconnect que devuelve True (para que entre al fallback)
    client.reconnect = AsyncMock(return_value=True)

    proxy = MCPToolProxy(name="test", description="",
                         parameters_schema={}, client=client)

    # Parcheamos el segundo call_tool para que lance excepción
    mock_session.call_tool.side_effect = [
        Exception("Error inicial"), Exception("Error secundario")]

    result = await proxy.run()

    assert result.success is False
    assert "Fallo tras reconexión" in result.error
