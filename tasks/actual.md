# Tarea Actual

Estas son las 2 tareas en ejecución, en este orden. Cada una debe implementarse con test primero (`uv run tom test` al terminar).

- [ ] **Corregir las tools copiadas a los subagentes.** En la TUI se intentan copiar
      `read_text_file`, `list_directory` y `bash` (`app/tui/app.py`),
      pero los dos primeros no están en el registry: en la práctica el reviewer legacy y las
      tools base A2A se quedan solo con `bash`. Implica usar `read_file` / `list_dir` o
      registrar alias. Ver `PRODUCT_BLUEPRINT/02_COMPONENTS/05_subagents.md`.

- [ ] **Registrar una tool `edit_file` (o quitarla de las políticas).** La documentación
      (`AGENTS.md`, `README.md`, `docs/herramientas.md`) y `app/core/harness/permissions.py`
      mencionan `edit_file`, pero `register_core_tools()` (`app/tools/__init__.py`) no la registra.
      Hoy un cambio puntual exige reescribir el archivo completo con `write_file`.
      Escenario: el agente recibe una instrucción de edición quirúrgica y no puede hacerla
      con el diff-first existente (`permissions.py`), que sí sabe generar diffs para `write_file`.
      Requiere decidir el diseño antes de implementarla.

## Notas

- Tareas completadas: `tasks/completadas.md`.
- Inventario del resto de funcionalidad pendiente: `tasks/pendientes.md`.
