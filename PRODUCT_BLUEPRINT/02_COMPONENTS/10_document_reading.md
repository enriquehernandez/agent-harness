# Document Reading (read_document)

## El Problema
Los LLMs no pueden leer archivos binarios (PDF, Word, Excel, PowerPoint) directamente. Si se les pasa el archivo como Base64, ven una cadena de caracteres sin sentido.

## La Solución: `read_document`
La tool `read_document` detecta la extensión del archivo y usa la librería adecuada para extraer el texto:
- **PDF**: `pypdf`
- **DOC/DOCX**: `olefile` (lee el stream `WordDocument` del formato 97-2003 y extrae cadenas imprimibles, primero en UTF-16LE y luego en Latin-1) / `python-docx`
- **XLS/XLSX**: `xlrd` (incluye celdas de fecha) / `openpyxl`
- **PPT/PPTX**: `olefile` (lee el stream `PowerPoint Document` con el mismo criterio) / `python-pptx`

La extracción de `.doc` y `.ppt` es best-effort: recupera cadenas legibles de los streams OLE, pero no conserva formato y puede incluir algún texto de metadatos. Para documentos complejos conviene convertirlos a `.docx`/`.pptx`.

El texto extraído se inyecta en el contexto del agente como un `ToolResult` normal.

## Límites y seguridad

- La tool recibe un único parámetro, `path`, y lo resuelve como `base_dir / path`. `_is_within_base_dir()` usa `target.resolve().relative_to(base_dir.resolve())`: si el archivo queda fuera de `base_dir`, devuelve `Access denied: outside base directory.`
- `settings.MAX_DOCUMENT_CHARS` es **15000** (`app/core/config.py`). Si el texto supera ese límite se trunca y se añade el aviso `--- ⚠️ [DOCUMENTO TRUNCADO] ---`, con el total de caracteres y la indicación de pedir al usuario una parte concreta o aumentar el límite en `.env`.
- Si el documento no contiene texto extraíble, la tool devuelve `success=True` con `(El documento no contiene texto extraíble. Podría estar vacío o ser una imagen escaneada.)`.
- `FileAwareInput` admite como adjuntos `.doc`, `.xls` y `.ppt` (`file_aware_input.py`) y `read_document` los extrae con `olefile`/`xlrd` (`documents.py`). Cualquier otra extensión devuelve `Formato '...' no soportado por read_document.`

## Flujo
1. El usuario adjunta un documento.
2. El `FileAwareInput` lo copia a `.harness/temp_attachments/` (si está fuera del proyecto).
3. El agente detecta la extensión y usa `read_document`.
4. El texto extraído se pasa al LLM.