# Checklist de Validación y Seguridad

Antes de dar una tarea por terminada, el agente DEBE verificar:

## 1. Validación Automática
- [ ] `uv run tom test` pasa sin errores. El script `test` de `pyproject.toml` incluye `--cov-fail-under=100`, así que el comando falla si la cobertura baja del 100%; CI lo ejecuta y además sube `coverage.xml` a Codecov.
- [ ] `uv run tom test-integration` pasa (verifica que los servidores MCP respondan).
- [ ] `uv run python scripts/check_pricing.py` valida la configuración de precios.

## 2. Validación Manual (si aplica cambios en la TUI)
- [ ] La TUI arranca (`uv run tom dev`).
- [ ] El streaming de chat funciona correctamente (eventos `AgentEvent`: texto, herramientas, resultado/errores).
- [ ] Los modales de permisos aparecen al usar `bash` o `write_file` (y también al usar `read_file`/`list_dir`).
- [ ] El panel de debug (F1) muestra los eventos y el flujo de agentes.
- [ ] La vista previa de imágenes funciona (si la terminal lo soporta): al pegar un PNG/JPG se muestra en el chat con `HalfcellImage` cuando `TERM_PROGRAM=WarpTerminal` y con `TerminalImage` en otros terminales; el adjunto aparece en la barra de archivos.
- [ ] El comando `/session list` muestra las sesiones guardadas.

## 3. Reglas de Seguridad
- [ ] No hay API keys hardcodeadas.
- [ ] No se usa `print()` en el código de producción (solo `logger` o `app.write_to_chat()`).
- [ ] El archivo `.env` no se ha subido al repositorio.
