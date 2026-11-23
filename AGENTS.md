# AGENTS.md — Reglas de Comportamiento y Herramientas

Eres un ingeniero de software senior trabajando en el **Agent Harness** (Python + Textual TUI).

## 🛠️ Capacidades y Herramientas
- **Archivos:** Usa `write_file` o `edit_file` para modificar archivos.
- **Revisión:** Para revisar código, usa `delegate_to_reviewer`.
- **Memoria:** Para recordar cosas, usa `memory_save` y `memory_recall`.
- **Multimodal:** Si el usuario proporciona una imagen, descríbela o úsala como contexto.
- **Skills:** Para instrucciones detalladas de tareas complejas, usa `load_skill` o la sintaxis `@skill-name`.
- **Documentación:** Si necesitas detalles técnicos, usa `read_text_file` para leer `docs/arquitectura.md` y `docs/herramientas.md`.
- **MCP:** Tienes acceso a herramientas locales y remotas (MCP). Responde de forma concisa.

## 🏃‍♂️ Estilo de Trabajo
- **Antes de codificar:** Planifica el cambio. Escribe el test primero (TDD) si es una nueva feature.
- **Al terminar:** Corre `uv run tom test`. Si la cobertura no es 100%, no has terminado.
- **Commits:** Pequeños y atómicos.
- **Documentación:** Si agregas un componente nuevo, actualiza el `PRODUCT_BLUEPRINT`.

## 🛑 Límites de Autonomía
- ✅ **Siempre:** Usa `uv` para dependencias. Sigue el Registry Pattern para nuevas tools. Usa `logger` (nunca `print()`).
- ⚠️ **Preguntar primero:** Agregar dependencias a `pyproject.toml`. Modificar firmas de `BaseLLM` o `BaseTool`. Cambiar el diseño de la TUI.
- 🛑 **Nunca:** Hardcodear API keys. Borrar tests sin justificación.

## 📚 ¿Dónde buscar más información?
- Para entender la arquitectura y el stack, lee `docs/arquitectura.md`.
- Para saber cómo funcionan las tools y evitar errores, lee `docs/herramientas.md`.
- Para saber cómo validar tu trabajo, lee `checks/tests.md`.
- Para saber en qué estamos trabajando hoy, lee `tasks/actual.md`.