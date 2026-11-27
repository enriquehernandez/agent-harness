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
- **Simular fallos de tools**: `FunctionTool.run()` devuelve el `ToolResult` tal cual si la función ya devolvió uno (`isinstance(result, ToolResult)`), conservando `success=False` y `error`. Solo envuelve el valor en `ToolResult(success=True, content=str(result))` cuando **no** es un `ToolResult`; las excepciones sí se capturan y se convierten en `ToolResult(success=False, ...)`.
  - **Solución**: Para simular un fallo basta con devolver `ToolResult(success=False, content="", error="Fallo simulado")`; lanza una excepción (`raise ValueError("Fallo")`) solo si además quieres cubrir el `except`.

## 4. Trampas del Testing de la TUI (Textual)
Testear interfaces de terminal es complejo. Usamos `app.run_test()` y `pilot`.

- `initialize_agent` **es asíncrono**: En la mayoría de tests de TUI, debes mockear `initialize_agent` para evitar que intente conectar con MCPs reales o LLMs reales.

- **Cuidado con los** `None`: Si mockeas `initialize_agent`, `self.agent_loop` será `None`. Cualquier método que use `self.agent_loop.llm` explotará.
  - **Solución**: Usa `if self.agent_loop and self.agent_loop.llm`: en el código de producción, y en los tests inyecta un `MagicMock()` si necesitas simular un loop.

- `push_screen_wait`: En los tests del modal de permisos, usa `patch.object(app, "push_screen_wait", new_callable=AsyncMock)` para simular las respuestas `y/n/a` sin necesidad de interactuar con la UI.

## 5. Cobertura de Ramas y Líneas "Fantasma"
Algunas líneas son difíciles de cubrir porque son defensivas (ej. `if not file.exists(): return {}`).

- **No las ignores**: Escribe un test específico que fuerce esa condición (ej. no crees el archivo).
- **Si es imposible (ej. excepciones del sistema)**: Usa `# pragma: no cover` con una justificación clara. En este proyecto, `pyproject.toml` (`[tool.coverage.report].exclude_lines`) solo tiene **3 reglas**: `pragma: no cover` (exclusión explícita), `if __name__ == .__main__.:` (bloques de entrada no ejecutados en tests) y `^\s*\.\.\.\s*$` (cuerpos abstractos/stubs). Las ramas `except`/`continue`/`return` y los callbacks de Textual (`on_`, `watch_`, `compose`) **se miden**: hay tests que provocan esos errores y comprueban el comportamiento resultante. No se añadan exclusiones nuevas sin justificación.

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

El informe de cobertura debe marcar **100%** de líneas: el script `test` de `pyproject.toml` usa `--cov-fail-under=100`, por lo que `uv run tom test` (y por extensión CI) falla si baja de ese umbral. La suite incluye `tests/integration` y no silencia `RuntimeWarning`: los coroutines sin await y las fugas de recursos se corrigen en los tests, no se ocultan. En la TUI (`app/tui/`), los manejadores `on_`, `watch_` y `compose` y las ramas de error se cubren con tests de comportamiento, como se detalla en la sección 5.

## 10. Mocking de Pricing
El `PricingProvider` se mockea fácilmente porque usa `PricingSource` (interfaz). Para tests:

```python
class MockSource(PricingSource):
    async def get_prices(self):
        return {"model1": {"input": 2.5e-6, "output": 1e-5}}
```

## 11. Mocking de Vectores
El `VectorStore` usa `fastembed`, que descarga un modelo ONNX (~90MB). Para tests rápidos:

- Usa `tmp_path` para la BD (`VectorStore(db_path=tmp_path / "test.db")`).
- El modelo se cachea en `~/.cache/huggingface/` la primera vez, pero luego es rápido.
- **No mockees** `fastembed`: los tests de integración lo usan real.

## 12. PropertyMock en Pydantic
Cuando necesites parchear una `@property` de `Settings` (ej. `pricing_config_path`), **no uses** `patch` **directamente**. Usa `patch("pathlib.Path.exists", return_value=False)` o `monkeypatch.chdir(tmp_path)` para evitar el error AttributeError: property has no setter.

## 13. Mocking de A2A
Para testear las estrategias A2A:
- Mockea `AgentLoop` con `patch(...)`.
- Mockea `get_llm` para evitar dependencias de red.
- Para cubrir el `log_agent_flow`, parchea `debug_collector.agent_flow` con eventos falsos.

## 14. Cobertura de Ramas en A2A
Las estrategias tienen ramas de error (agente no encontrado, límite de saltos, handoff inválido). Para cubrirlas:
- Usa `AgentCard` con nombres falsos (`ghost_agent`).
- Fuerza el `max_hops` con un agente que siempre devuelva `HANDOFF: <otro>`.
- Parchea `get_llm` para simular modelos específicos.

## 15. Mocking de Document Parsers
Para testear `read_document`, mockea las librerías de extracción (`PdfReader`, `Document`, `load_workbook`, `Presentation`, `xlrd.open_workbook` y `olefile.OleFileIO`) para evitar depender de archivos reales y mantener los tests rápidos. Para los formatos legacy se puede mockear el stream OLE devolviendo bytes UTF-16LE con texto conocido.