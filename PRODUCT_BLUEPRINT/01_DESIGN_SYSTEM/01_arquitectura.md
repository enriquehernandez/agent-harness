# Arquitectura del Sistema

El Harness está diseñado con un enfoque de **puertos y adaptadores** (Arquitectura Hexagonal). El núcleo (`AgentLoop`) no sabe si el LLM es OpenAI o si las herramientas vienen de un servidor MCP local o remoto.

## Diagrama de Alto Nivel

```mermaid
graph TD
    User([Usuario]) -->|Texto / Drag & Drop| TUI[Textual TUI]
    TUI -->|Input| Loop[AgentLoop]
    
    subgraph Core ["Core del Harness"]
        Loop -->|1. Razonamiento Streaming| LLM[BaseLLM]
        Loop -->|2. Permisos| Gate[PermissionGate]
        Loop -->|3. Ejecución| Tools[ToolRegistry]
        Loop <-->|4. Memoria| Context[ContextManager]
        Context <-->|Compactación| Compactor[SummarizationStrategy]
        Context <-->|Persistencia| MemoryFile[(summary.md)]
    end
    
    subgraph Adaptadores
        LLM -.->|Registry| Providers[OpenAI / OpenRouter / Groq]
        Tools -.->|Local| LocalTools[Bash, File, Memory]
        Tools -.->|MCP Client| MCP[Servidores MCP Externos]
        Tools -.->|Delegate| Subagent[Subagente Reviewer]
        Subagent -.->|Nuevo Loop| Loop
    end
    
    subgraph UI ["UI Components"]
        TUI --> DebugPanel[Debug Panel]
        TUI --> PermissionModal[Permission Modal]
        TUI --> Chat[Chat con Streaming]
    end
```

## Flujo de Ejecución (ReAct Pattern)

```mermaid
sequenceDiagram
    participant U as Usuario
    participant T as Textual TUI
    participant L as AgentLoop
    participant LLM as BaseLLM

    U->>T: "Escribe un poema"
    T->>L: stream("Escribe un poema")
    L->>LLM: stream_chat(messages)
    
    loop Por cada token
        LLM-->>L: chunk
        L-->>T: yield chunk
        T->>T: Actualiza widget Markdown
    end
    
    T-->>U: Muestra texto completo
```
