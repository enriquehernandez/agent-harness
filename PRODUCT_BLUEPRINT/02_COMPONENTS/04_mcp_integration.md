# Integración con MCP (Model Context Protocol)

## ¿Qué es MCP?
MCP es un protocolo abierto que estandariza cómo un modelo de IA (o un Harness) se conecta a herramientas y fuentes de datos externas. En lugar de programar cada herramienta dentro de tu proyecto, el Harness actúa como un **Cliente** que se conecta a **Servidores MCP** (que pueden estar escritos en cualquier lenguaje).

## Flujo de Integración

1. **Configuración:** El usuario define los servidores en `mcp_config.json`:
   
```json
{
    "mcpServers": {
    "filesystem": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem@2.4.1", "/ruta"]
    }
    }
}
```

2. **Conexión (stdio)**: El `MCPClient` lanza el proceso del servidor mediante `stdio` (Standard Input/Output). Se crea un `ClientSession`. `connect()` limita `_do_connect()` con `asyncio.wait_for(..., timeout=settings.MCP_CONNECT_TIMEOUT)` (**10 s** por defecto) y usa `tenacity` con `stop_after_attempt(3)` y `wait_exponential(multiplier=1, min=1, max=10)`: **3 intentos** con backoff exponencial.
3. **Descubrimiento**: El Harness llama a `session.list_tools()`. El servidor MCP responde con un JSON describiendo sus herramientas.
4. **Adaptación (Proxy Pattern)**: El Harness no expone las herramientas MCP directamente al LLM. Las envuelve en `MCPToolProxy`, que implementa la interfaz local `BaseTool`, y las registra con el prefijo `mcp_<servidor>_` (`mcp_{server_name}_{mcp_tool.name}`) para evitar colisiones con herramientas locales.
5. **Ejecución**: Cuando el LLM pide usar una herramienta, `MCPToolProxy.run()` -> `_call()` invoca `session.call_tool(self.original_name, arguments=kwargs)` con `asyncio.wait_for(..., timeout=settings.TOOL_TIMEOUT)` (**30 s** por defecto). Si no hay sesión o la llamada falla, intenta `reconnect()` y una segunda llamada antes de devolver `ToolResult(success=False, ...)`.
6. **Entorno y versiones**: `MCPClient` no copia `os.environ` al servidor. Entrega solo variables de ejecución no sensibles (`PATH`, `HOME`, `LANG`, temporales y equivalentes de sistema) y las que el servidor declare explícitamente en `allowed_env`; `env` fija valores literales y prevalece sobre lo heredado. Así, las credenciales del Harness no llegan a los procesos externos. Los paquetes lanzados con `uvx`/`npx` se fijan a versiones concretas para que el arranque no cambie de comportamiento sin revisión.

## Ventajas

- **Interoperabilidad**: Tu agente puede usar herramientas creadas por la comunidad (ej. navegar por Playwright, leer bases de datos Postgres) sin escribir una sola línea de código de adaptación.
- **Seguridad**: El servidor MCP se ejecuta en su propio proceso, aislando posibles fallos.
- **Dinamismo**: Las herramientas se descubren en tiempo de ejecución al arrancar la TUI.