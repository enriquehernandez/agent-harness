# Estrategia de Testing (100% Coverage)

El proyecto alcanza un 100% de cobertura gracias a una combinación de mocks y pruebas de integración reales.

## 1. FakeLLM (Mock del LLM)
Hemos creado un `FakeLLM` que implementa `BaseLLM`. Se le inyecta una lista de respuestas pre-programadas (`LLMResponse`). Esto permite testear el `AgentLoop`, la compactación y los permisos en milisegundos y sin gastar tokens.

## 2. Mocking del Cliente MCP
Para los tests unitarios del cliente MCP, se mockea el método `session.call_tool` para evitar levantar subprocesos reales. Para los tests de integración, se levanta un servidor MCP local real en modo `stdio`.

## 3. Testing de la TUI (Textual)
Testear una interfaz de usuario es complejo. Usamos el **`Pilot`** de Textual, que simula las pulsaciones de teclado y clics de un usuario real. 

Ejemplo de test de la TUI:
```python
async with app.run_test() as pilot:
    await pilot.press("f1") # Abre el panel de debug
    await pilot.pause()
    assert app.query_one("#debug-panel").display is True
```

## 4. Exclusiones de Cobertura (Coverage.py)
Las líneas visuales (CSS, BINDINGS, definiciones de `compose`) y los `except` de los callbacks de la UI se excluyen en el `pyproject.toml` ya que no son lógica de negocio y son imposibles de testear sin un entorno gráfico real.