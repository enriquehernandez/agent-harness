# Renderizado Rico (RichMessage)

## El Problema
El Markdown estándar no puede mostrar tablas con bordes, árboles jerárquicos o código resaltado de forma nativa.

## La Solución: RichMessage
`RichMessage` es un widget de Textual que parsea el texto del agente con Regex y renderiza bloques especiales:

- **```table**: Tablas Markdown → `rich.table.Table`.
- **```tree**: Árboles jerárquicos → `rich.tree.Tree`.
- **```json**: Listas de dicts → `rich.table.Table` (automático).
- **```python**: Código → `rich.syntax.Syntax`.

## Skill
La skill `rich-formatting` enseña al agente a usar estos bloques.