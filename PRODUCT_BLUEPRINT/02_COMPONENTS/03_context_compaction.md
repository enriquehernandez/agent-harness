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
La clase `ContextManager` no sabe *cómo* se compacta. Delega la tarea a una interfaz `CompactionStrategy`. Esto permite a los desarrolladores inyectar nuevas estrategias en el futuro (ej. `TruncationStrategy` para solo borrar, o estrategias basadas en grafos como LCM).