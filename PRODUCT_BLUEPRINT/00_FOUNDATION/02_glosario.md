# Glosario de Términos

- **Agent Harness:** La capa de software que orquesta el ciclo de razonamiento del agente, la ejecución de herramientas, la gestión de memoria, la interfaz de usuario y los subagentes. Es el "esqueleto" del agente.
- **Agent Loop (ReAct):** El bucle donde el agente Razonay Actúa: *Piensa -> Llama a herramienta -> Observa resultado -> Piensa de nuevo -> Responde*. En este proyecto se implementa en `AgentLoop`.
- **Compaction (Compactación):** Proceso de resumir o descartar mensajes antiguos del historial cuando se acerca al límite de tokens del LLM. Se implementan tres estrategias: `summarize`, `sliding` y `none`.
- **Diff-First Approval:** Técnica de seguridad en la que el `PermissionGate` muestra un *diff* de los cambios propuestos (usando `difflib`) antes de pedir confirmación al usuario para modificar archivos.
- **Delegate Tool (Subagente):** Una herramienta especial que instancia un nuevo `AgentLoop` aislado (con su propio contexto y herramientas restringidas) para realizar una tarea y devolver un resumen al agente principal.
- **LLM (Large Language Model):** El modelo de lenguaje (ej. GPT-4o) que actúa como el "cerebro" del agente. La interfaz `BaseLLM` abstrae los diferentes proveedores.
- **MCP (Model Context Protocol):** Un estándar abierto creado por Anthropic para que los LLMs se conecten a fuentes de datos y herramientas externas. En este proyecto, el `MCPClient` actúa como un puente que adapta las herramientas MCP a `BaseTool`.
- **Multimodalidad:** Capacidad del agente de procesar y entender imágenes además de texto. Se implementa codificando la imagen en Base64 y enviándola al LLM como un bloque `image_url`.
- **Permission Gate:** El componente de seguridad que intercepta las llamadas a herramientas sensibles. Evalúa políticas (`ALLOW`, `ASK`, `DENY`) y utiliza la interfaz `ask_user` para pedir confirmación.
- **Provider-Agnostic:** Capacidad de un sistema para funcionar independientemente del proveedor subyacente (OpenAI, Groq, OpenRouter, etc.).
- **Prompt Caching:** Técnica para ahorrar costes y latencia haciendo que el proveedor del LLM reutilice el procesamiento del *system prompt* y las definiciones de herramientas entre llamadas.
- **Registry Pattern (Patrón Registro):** Un patrón de diseño que utiliza un diccionario central para mapear nombres de proveedores o herramientas a sus funciones constructoras, respetando el principio Open/Closed de SOLID.
- **Repair Policy (Reintentos):** Mecanismo del `AgentLoop` que cuenta los fallos consecutivos de una herramienta. Si falla 3 veces, inyecta un mensaje de sistema para que el LLM se detenga y pida ayuda al usuario.
- **Safe Split Point:** Algoritmo de la compactación que garantiza que nunca se separe una llamada a herramienta (`tool_call`) de su resultado (`tool_result`), evitando errores 400 en la API del LLM.
- **Streaming:** Técnica de renderizado en la que la respuesta del agente se muestra token por token en la TUI, en lugar de esperar a que se complete toda la respuesta.
- **TUI (Terminal User Interface):** Interfaz de usuario basada en texto. En este proyecto, se construye con **Textual** para ofrecer temas, modales, paneles divididos y una experiencia de usuario moderna.
- **Tool (Herramienta):** Una función que el LLM puede invocar (ej. `read_file`, `bash`, `memory_save`). Tiene un nombre, descripción y un esquema de parámetros (JSON Schema).
- **Tool Calling:** La capacidad del LLM de devolver una estructura JSON indicando qué herramienta quiere usar y con qué argumentos, en lugar de devolver solo texto plano.