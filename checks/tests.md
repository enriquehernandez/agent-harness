# Checklist de Validación y Seguridad

> Parte operativa de `tasks/DEFINITION_OF_DONE.md`. **No se commitea nada hasta que el DoD esté completo**, incluida la `Prueba en TUI` ejecutada y registrada en `tasks/completadas.md`.

Antes de dar una tarea por terminada, el agente DEBE verificar:

## 1. Validación Automática
- [ ] `uv run tom test` pasa sin errores. El script `test` de `pyproject.toml` incluye `--cov-fail-under=100`, así que el comando falla si la cobertura baja del 100%; CI lo ejecuta y además sube `coverage.xml` a Codecov.
- [ ] `uv run tom test-integration` pasa (verifica que los servidores MCP respondan).
- [ ] El pricing se verifica con los tests de `tests/core/test_pricing.py`. Los scripts de diagnóstico (`scripts/check_pricing.py`, `scripts/verify_memory_backends.py`) son opcionales: trabajan en directorios temporales y no forman parte del checklist obligatorio.

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

## 4. Registro antes de commitear

- [ ] La tarea aparece en `tasks/completadas.md` con `**Prueba en TUI:**` (pasos ejecutados + resultado esperado, o `N/A` justificado).
- [ ] `tasks/actual.md` y `tasks/pendientes.md` están sincronizados.
- [ ] `git status` y `git diff` revisados: solo archivos de la tarea, sin secretos ni artefactos generados.
- [ ] DoD completo en `tasks/DEFINITION_OF_DONE.md` y aprobación explícita del usuario antes de hacer commit.
