# Decisiones de Arquitectura y Patrones

## 1. Registry Pattern y Polimorfismo (SOLID - Open/Closed)
**Problema:** Queremos que el Harness sea agnóstico al LLM.
**Solución:** No usamos `if/elif` para instanciar modelos. Usamos un `_PROVIDER_REGISTRY` en `app/core/llm/registry.py`.
**Beneficio:** Si mañana queremos añadir Anthropic (Claude) nativo, solo creamos un archivo `anthropic_provider.py` que herede de `BaseLLM` y lo registramos en una línea de código, sin tocar el `AgentLoop`.

## 2. Strategy Pattern (Compactación)
**Problema:** Las conversaciones largas superan el límite de tokens.
**Solución:** La clase `ContextManager` delega la tarea a una interfaz `CompactionStrategy`.
**Beneficio:** Podemos implementar `SummarizationStrategy` (resumir), `TruncationStrategy` (cortar lo más viejo) o `LCMStrategy` (Lossless Context Management) y cambiarlas en caliente.

## 3. MCP (Model Context Protocol)
**Problema:** Crear herramientas locales es útil, pero limita al agente al filesystem local.
**Solución:** Implementación de `MCPClient` usando transporte `stdio`. El Harness descubre las herramientas en tiempo de ejecución mediante `session.list_tools()` y las adapta a `BaseTool` usando un patrón **Proxy**.
**Beneficio:** El agente puede usar herramientas escritas en otros lenguajes (Node.js, Go) o conectarse a APIs externas complejas (ej. GitHub, bases de datos) de forma estandarizada.