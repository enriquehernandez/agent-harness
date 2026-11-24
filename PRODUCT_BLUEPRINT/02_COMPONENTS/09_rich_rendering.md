# Renderizado de Imágenes en la TUI

## El Problema
La TUI debe mostrar una vista previa de las imágenes que el usuario adjunta y, además, enviarlas al LLM. Este flujo no pasa por `RichMessage` (que solo procesa tablas, árboles y JSON en los mensajes).

## La Solución: widgets de `textual_image`

El input (`FileAwareInput`) acepta rutas de imágenes con extensiones `.png`, `.jpg`, `.jpeg`, `.gif` y `.webp` (`app/tui/widgets/file_aware_input.py`). Al pegarlas, `handle_file_paste()` (`app/tui/app.py`):

1. Monta un widget en `#chat-scroll` con la clase `message-image`: usa **`HalfcellImage`** si `os.environ.get("TERM_PROGRAM") == "WarpTerminal"`; en cualquier otro caso usa **`TerminalImage`** (alias de `textual_image.widget.Image`).
2. Si la creación del widget falla, lo registra con `logger.warning` y muestra `🖼️ Imagen adjunta: nombre (vista previa no disponible)` en el chat, con el nombre del archivo. La imagen sigue quedando adjunta.
3. Lee el archivo en base64 y añade a `attached_images` un data URI: `data:image/png;base64,...` para `.png` y `data:image/jpeg;base64,...` para el resto de extensiones.
4. Al enviar el mensaje, `ctx.add_user_with_image(user_text, self.attached_images)` pasa esas imágenes al LLM; la barra de adjuntos las muestra como `🖼️ Imagen`.

## Ver también
- [Renderizado Rico: tablas, árboles y JSON](07_rich_rendering.md): bloques `table`, `tree` y `json` de `RichMessage`.
