# Renderizado Rico: tablas, árboles y JSON (RichMessage)

## El Problema
El Markdown estándar no puede mostrar tablas con bordes ni árboles jerárquicos de forma nativa.

## La Solución: RichMessage
`RichMessage` es un widget de Textual (`app/tui/widgets/rich_message.py`). Detecta si el texto contiene bloques cercados con `table`, `tree` o `json` (triple backtick); solo entonces aplica el regex `r"```(table|tree|json)\s*\n(.*?)\n```"` y procesa los bloques. Si no aparece ninguno de esos tres tags, el contenido se renderiza como `rich.markdown.Markdown`.

- **```table**: Tablas Markdown con cabecera y fila separadora (`| --- |`) → `rich.table.Table`. Las filas cuyo número de celdas no coincide con el de la cabecera se omiten.
- **```tree**: Cada línea no vacía → un nodo de `rich.tree.Tree` bajo la raíz `📁 Root`.
- **```json**: Un JSON válido que sea una lista no vacía de dicts → `rich.table.Table` con una columna por clave; en cualquier otro caso → `rich.syntax.Syntax` con tema `monokai` y números de línea.

`RichMessage` **no tiene un bloque `python` propio**: el código con esa etiqueta se deja dentro del Markdown normal. Si un bloque reconocido es inválido, se muestra un aviso `⚠️ Error renderizando bloque ...`.

## Skill
La skill `rich-formatting` (`.agents/skills/rich-formatting/SKILL.md`) enseña al agente a usar estos bloques; para el resaltado de código recomienda los bloques Markdown con identificador de lenguaje.

## Ver también
- [Renderizado de imágenes en la TUI](09_rich_rendering.md): la previsualización de adjuntos usa otro mecanismo, no `RichMessage`.
