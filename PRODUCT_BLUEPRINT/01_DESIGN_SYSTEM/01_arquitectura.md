# Arquitectura del Sistema

El Harness está diseñado con un enfoque de **puertos y adaptadores** (Arquitectura Hexagonal). El núcleo (`AgentLoop`) no sabe si el LLM es OpenAI o si las herramientas vienen de un servidor MCP local o remoto.

## Diagrama de Alto Nivel

```mermaid
graph TD
    User([Usuario]) -->|Texto / Slash Commands| TUI[TUI Prompt_Toolkit]
    TUI -->|Input| Loop[AgentLoop]
    
    subgraph Core ["Core del Harness"]
        Loop -->|1. Pide razonamiento| LLM[BaseLLM]
        Loop -->|2. ¿Permiso?| Gate[PermissionGate]
        Gate -->|Permitir/Denegar| Loop
        Loop -->|3. Ejecuta| Tools[ToolRegistry]
        Loop <-->|4. Historial| Context[ContextManager]
        Context <-->|Compactación| Compactor[SummarizationStrategy]
    end
    
    subgraph Adaptadores
        LLM -->|Registry Pattern| OpenAI[OpenAI]
        LLM -->|Registry Pattern| OpenRouter[OpenRouter]
        Tools -->|Local| Bash[BashTool]
        Tools -->|Local| File[ReadFileTool]
        Tools -->|MCP Client| MCP[Servidor MCP]
    end
```

## Flujo de Ejecución (ReAct Pattern)

```mermaid
sequenceDiagram
    participant U as Usuario
    participant H as Harness (Loop)
    participant L as LLM
    participant G as PermissionGate
    participant T as Tool (Local/MCP)

    U->>H: "¿Qué OS tengo?"
    H->>L: Enviar historial + Tools disponibles
    L-->>H: Tool Call: `get_system_info`
    H->>G: Verificar permiso para `get_system_info`
    G-->>H: ALLOW
    H->>T: Ejecutar tool
    T-->>H: "OS: macOS 14.0"
    H->>L: Inyectar resultado
    L-->>H: "Usas macOS 14.0"
    H-->>U: Respuesta final
```
