# Checklist de Validación y Seguridad

Antes de dar una tarea por terminada, el agente DEBE verificar:

## 1. Validación Automática
- [ ] `uv run tom test` pasa sin errores y con >99% de cobertura.
- [ ] `uv run tom test-integration` pasa (verifica que los servidores MCP respondan).
- [ ] `uv run python scripts/check_pricing.py` valida la configuración de precios.

## 2. Validación Manual (si aplica cambios en la TUI)
- [ ] La TUI arranca (`uv run tom dev`).
- [ ] El streaming de chat funciona correctamente.
- [ ] Los modales de permisos aparecen al usar `bash` o `write_file`.
- [ ] El panel de debug (F1) muestra los eventos y el flujo de agentes.
- [ ] El comando `/session list` muestra las sesiones guardadas.

## 3. Reglas de Seguridad
- [ ] No hay API keys hardcodeadas.
- [ ] No se usa `print()` en el código de producción (solo `logger` o `app.write_to_chat()`).
- [ ] El archivo `.env` no se ha subido al repositorio.