# Estrategia de Testing (100% Coverage)

Para que un Harness sea confiable, necesita pruebas deterministas. No podemos testear usando un LLM real (cuesta dinero y las respuestas varían).

## FakeLLM (Mock)
Hemos creado un `FakeLLM` que implementa `BaseLLM`. Se le inyecta una lista de respuestas pre-programadas (`LLMResponse`).
```python
fake = get_llm("fake", responses=[
    LLMResponse(tool_calls=[{"id": "1", "name": "get_system_info", "arguments": {}}]),
    LLMResponse(content="El sistema es macOS")
])
```

**Beneficio**: Podemos simular cadenas de herramientas (Tool Chaining), evaluar la compactación de contexto y verificar que el `AgentLoop` actúa correctamente, todo en milisegundos y sin red.

## Mocking del MCP Client
Para los tests unitarios del cliente MCP, se mockea el método `session.call_tool` para devolver un objeto simulado, evitando levantar subprocesos reales.

## Permission Gate Testing
Para probar el `PermissionGate` sin interacción humana, se le inyecta una función `ask_user` falsa que devuelve un valor predefinido ("`y`", "`n`" o "`a`").