# Estrategia de Testing, Mocks y 100% Coverage

El proyecto mantiene un **100% de cobertura** (excluyendo UI visual y ramas defensivas) gracias a una combinación de mocks deterministas y pruebas de integración reales. Este documento no solo describe la estrategia, sino que documenta las **trampas** y **decisiones de diseño** que surgieron al llegar al 100%, para que futuros desarrolladores no repitan los mismos errores.

## 1. El FakeLLM (El santo grial del testing)
En lugar de hacer llamadas reales a OpenAI/OpenRouter (que cuestan dinero, tiempo y son no deterministas), inyectamos un `FakeLLM`.

**Regla de oro:** El `FakeLLM` **debe** implementar el mismo contrato que `BaseLLM`. 
- `chat()` devuelve un `LLMResponse`.
- `stream_chat()` **debe** emitir `str` para el texto, y diccionarios para `{"type": "tool_call"}` y `{"type": "usage"}`. Si no emites los tool_calls en el stream, el `AgentLoop.stream()` nunca los ejecutará y los tests fallarán de forma silenciosa.

```python
# Correcto en FakeLLM.stream_chat
async def stream_chat(self, messages, tools=None, **kwargs):
    resp = await self.chat(messages, tools, **kwargs)
    if resp.content: yield resp.content
    if resp.tool_calls:
        for tc in resp.tool_calls:
            yield {"type": "tool_call", "id": tc["id"], "name": tc["name"], "arguments": tc["arguments"]}
    if resp.usage:
        yield {"type": "usage", "usage": resp.usage}
```

## 2. Trampas de Pydantic y la Configuración (`Settings`)
`Settings` usa Pydantic v2. Las propiedades definidas con `@property` (ej. `sessions_dir`, `permissions_file`) son de solo lectura.

- ❌ **Nunca** uses `patch("app.core.config.settings.sessions_dir", tmp_path)`.
- ❌ **Nunca** uses `monkeypatch.setattr(settings, "sessions_dir", ...)`.
- ✅ **Solución**: Usa `monkeypatch.chdir(tmp_path)` en el test. Como las propiedades usan rutas relativas (ej. `Path(".harness/permissions.json")`), al cambiar el cwd, los archivos se crean dentro de `tmp_path` de forma natural y aislada.

```python
def test_permissions(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".harness").mkdir()
    (tmp_path / ".harness" / "permissions.json").write_text("{}")
    # Ahora settings.permissions_file apunta a tmp_path
```

## 3. Trampas del AgentLoop y las Herramientas
El `AgentLoop` interactúa con `ToolRegistry` y `PermissionGate`. Hay dos detalles críticos:

- **Permisos por defecto**: Si no inyectas un `PermissionGate`, el loop usa el por defecto, que tiene `bash` y `write_file` en `ASK`. Como en los tests no hay UI, el gate devuelve `DENY`, por lo que l**as tools nunca se ejecutan** y `tools_used` queda vacío.
  - **Solución**: En los tests, inyecta `gate = PermissionGate(policies={"tu_tool": Decision.ALLOW})`.
- **Simular fallos de tools**: El `FunctionTool` envuelve todo en `try/except`. Si tu función de test devuelve un `ToolResult(success=False)`, el `FunctionTool` lo ignorará y devolverá `success=True` (porque no lanzó excepción).
  - **Solución**: Para simular un fallo real, la función debe lanzar una excepción (`raise ValueError("Fallo")`).

## 4. Trampas del Testing de la TUI (Textual)
Testear interfaces de terminal es complejo. Usamos `app.run_test()` y `pilot`.

- `initialize_agent` **es asíncrono**: En la mayoría de tests de TUI, debes mockear `initialize_agent` para evitar que intente conectar con MCPs reales o LLMs reales.

- **Cuidado con los** `None`: Si mockeas `initialize_agent`, `self.agent_loop` será `None`. Cualquier método que use `self.agent_loop.llm` explotará.
  - **Solución**: Usa `if self.agent_loop and self.agent_loop.llm`: en el código de producción, y en los tests inyecta un `MagicMock()` si necesitas simular un loop.

- `push_screen_wait`: En los tests del modal de permisos, usa `patch.object(app, "push_screen_wait", new_callable=AsyncMock)` para simular las respuestas `y/n/a` sin necesidad de interactuar con la UI.

## 5. Cobertura de Ramas y Líneas "Fantasma"
Algunas líneas son difíciles de cubrir porque son defensivas (ej. `if not file.exists(): return {}`).

- **No las ignores**: Escribe un test específico que fuerce esa condición (ej. no crees el archivo).
- **Si es imposible (ej. excepciones del sistema)**: Usa `# pragma: no cover` con una justificación clara. En este proyecto, `pyproject.toml` ya excluye líneas de UI (CSS, BINDINGS) y `except` de callbacks.

## 6. El `except` del Timeout en `AgentLoop.stream()`
El bloque `except (asyncio.TimeoutError, TimeoutError)` solo se ejecuta si el LLM se cuelga. Para cubrirlo, el `FakeLLM` debe tener un método `stream_chat` que haga un await `asyncio.sleep(2)` antes de devolver un chunk, y el test debe llamar a `loop.stream(..., timeout_seconds=0.1).`

## 7. Aislamiento de Archivos
Nunca escribas en el `.harness/` real durante los tests. Usa siempre `tmp_path` y `monkeypatch.chdir(tmp_path)`. Esto evita que los tests de memoria o sesiones contaminen tu base de datos local y hace que los tests sean reproducibles en CI (Docker).

## 8. Cuidado con los dobles imports y `UnboundLocalError`
Python a veces se confunde si importas un módulo (ej. `import json`) dentro de una función (por ejemplo, dentro de un `if` de un comando).

- **Regla**: Todos los imports (`import json`, `from pathlib import Path`) deben ir al **principio del archivo**, nunca dentro del `handle_command`. Esto evita el error `UnboundLocalError: cannot access local variable 'json' where it is not associated with a value`.

## 9. Resumen del Pipeline de CI
```bash
# Ejecuta tests con cobertura
uv run tom test

# Ejecuta tests de integración MCP (requiere levantar servidores)
uv run tom test-integration
```

La cobertura mínima exigida es del **100%** para los módulos del núcleo (`app/core/`). Los archivos de la TUI (`app/tui/`) pueden tener pequeñas exclusiones visuales justificadas en `pyproject.toml`.