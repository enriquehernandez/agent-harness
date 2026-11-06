# Glosario de Términos

- **Agent Harness:** La capa de software que orquesta el ciclo de razonamiento del agente, la ejecución de herramientas, la gestión de memoria y la interfaz de usuario. Es el "esqueleto" del agente.
- **Agent Loop (ReAct):** El bucle infinito (hasta cierto límite) donde el agente Razonay Actúa: *Piensa -> Llama a herramienta -> Observa resultado -> Piensa de nuevo -> Responde*.
- **Compaction (Compactación):** Proceso de resumir mensajes antiguos del historial de conversación cuando este se acerca al límite de tokens del LLM, para evitar errores y ahorrar costes.
- **LLM (Large Language Model):** El modelo de lenguaje (ej. GPT-4o) que actúa como el "cerebro" del agente.
- **MCP (Model Context Protocol):** Un estándar abierto creado por Anthropic para que los LLMs se conecten a fuentes de datos y herramientas externas de manera estandarizada y segura. Es el "USB-C de las herramientas de IA".
- **Permission Gate:** El componente de seguridad que intercepta las llamadas a herramientas sensibles y pide confirmación al usuario antes de proceder.
- **Provider-Agnostic:** Capacidad de un sistema para funcionar independientemente del proveedor subyacente (en este caso, OpenAI, Groq, OpenRouter, etc.).
- **Registry Pattern (Patrón Registro):** Un patrón de diseño que utiliza un diccionario central para mapear nombres de proveedores o herramientas a sus funciones constructoras, respetando el principio Open/Closed de SOLID.
- **TUI (Terminal User Interface):** Interfaz de usuario basada en texto. En este proyecto, se construye con `prompt_toolkit` y `rich` para ofrecer historial, edición de línea y colores en la terminal.
- **Tool (Herramienta):** Una función que el LLM puede invocar (ej. `read_file`, `bash`, `get_weather`). Tiene un nombre, descripción y un esquema de parámetros (JSON Schema).
- **Tool Calling:** La capacidad del LLM de devolver una estructura JSON indicando qué herramienta quiere usar y con qué argumentos, en lugar de devolver solo texto plano.