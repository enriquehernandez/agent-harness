# Document Reading (read_document)

## El Problema
Los LLMs no pueden leer archivos binarios (PDF, Word, Excel, PowerPoint) directamente. Si se les pasa el archivo como Base64, ven una cadena de caracteres sin sentido.

## La Solución: `read_document`
La tool `read_document` detecta la extensión del archivo y usa la librería adecuada para extraer el texto:
- **PDF**: `pypdf`
- **DOCX**: `python-docx`
- **XLSX**: `openpyxl`
- **PPTX**: `python-pptx`

El texto extraído se inyecta en el contexto del agente como un `ToolResult` normal.

## Flujo
1. El usuario adjunta un documento.
2. El `FileAwareInput` lo copia a `.harness/temp_attachments/` (si está fuera del proyecto).
3. El agente detecta la extensión y usa `read_document`.
4. El texto extraído se pasa al LLM.