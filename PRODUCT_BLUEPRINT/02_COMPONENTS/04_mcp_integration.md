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
        "args": ["-y", "@modelcontextprotocol/server-filesystem", "/ruta"]
    }
    }
}
```

2. **Conexión (stdio)**: El `MCPClient` lanza el proceso del servidor mediante `stdio` (Standard Input/Output). Se crea un `ClientSession`.
3. **Descubrimiento**: El Harness llama a `session.list_tools()`. El servidor MCP responde con un JSON describiendo sus herramientas.
4. **Adaptación (Proxy Pattern)**: El Harness no expone las herramientas MCP directamente al LLM. Las envuelve en `MCPToolProxy`, que implementa la interfaz local `BaseTool`.
5. **Ejecución**: Cuando el LLM pide usar una herramienta, el `MCPToolProxy.run()` llama a `session.call_tool()` enviando los argumentos por el protocolo.

## Ventajas

- **Interoperabilidad**: Tu agente puede usar herramientas creadas por la comunidad (ej. navegar por Playwright, leer bases de datos Postgres) sin escribir una sola línea de código de adaptación.
- **Seguridad**: El servidor MCP se ejecuta en su propio proceso, aislando posibles fallos.
- **Dinamismo**: Las herramientas se descubren en tiempo de ejecución al arrancar la TUI.