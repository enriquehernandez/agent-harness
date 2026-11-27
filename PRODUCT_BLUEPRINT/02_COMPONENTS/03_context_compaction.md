# Context Compaction (Gestión de Memoria)

## El Problema de la Ventana de Contexto
Los LLMs tienen un límite estricto de tokens (ej. 128,000 en GPT-4o). Si una conversación, o los resultados de múltiples herramientas, superan este límite, la API devuelve un error y la sesión muere.

## La Solución: Estrategias de Compactación
En lugar de simplemente "borrar" los mensajes más antiguos (lo que hace que el agente olvide el contexto), utilizamos una **estrategia de resumen**.

### SummarizationStrategy
1. Cuando el `ContextManager` detecta que se ha superado el 80% de la ventana de contexto (`maybe_compact`), se activa.
2. Separa el historial en dos: **Mensajes Antiguos** y **Mensajes Recientes** (los últimos 4, por defecto).
3. Envía los mensajes antiguos al LLM con un prompt: *"Resume esta conversación manteniendo hechos clave y herramientas usadas"*.
4. Reemplaza los mensajes antiguos por un único mensaje de rol `system` que contiene el resumen.
5. Mantiene los mensajes recientes intactos.

## Patrón Strategy
La clase `ContextManager` no sabe *cómo* se compacta. Delega la tarea a una interfaz `CompactionStrategy`. Las estrategias implementadas son `SummarizationStrategy` (por defecto), `SlidingWindowStrategy` y `NoneStrategy` (`compaction.py`); `set_strategy()` permite seleccionar `summarization`, `sliding` o `none` en caliente.

## Persistencia de sesiones

`SessionManager` guarda el historial en `.harness/sessions/<id>.json` y carga la última sesión al arrancar la TUI. Los IDs son nombres planos formados por letras, dígitos, `_` y `-`: las rutas relativas, absolutas y cualquier separador se rechazan en el constructor, en `list_sessions()` y en `delete_session()`, de modo que ninguna sesión puede apuntar a otro archivo. `load()` devuelve un historial vacío si el JSON no existe, no se puede leer o no es válido, y descarta los mensajes `system` del archivo.

Al restaurar un historial, la TUI antepone los mensajes `system` presentes en el contexto actual (`merge_session_history()`): las instrucciones vigentes nunca se sustituyen por contenido del archivo, tanto al arrancar como con `/session load <id>`. Si el ID no es válido, `/session load` muestra el error y no intenta leer ningún archivo. `/session new` guarda la sesión anterior, crea una nueva, conserva el system prompt y reinicia los contadores de reparación.