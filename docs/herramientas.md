# Herramientas, Comportamientos y Pitfalls

## Reglas Generales de Tools
- **Errores:** Las tools deben retornar `ToolResult(success=False)` en lugar de lanzar excepciones.
- **Permisos:** Las tools sensibles (`bash`, `write_file`) siempre piden confirmación (y/a/n). Los permisos "always" se guardan en `.harness/permissions.json`.
- **MCP:** Configurados en `mcp_config.json`. Si un servidor falla al conectar, se ignora. Si una tool falla en ejecución, `MCPToolProxy` reconecta y reintenta 1 vez.
- **Skills:** Se cargan de `.agents/skills/<name>/SKILL.md`. Se pueden invocar con la tool `load_skill` o con la sintaxis `@name` (tiene autocompletado).
- **Sessions:** `SessionManager` guarda en `.harness/sessions/<id>.json`. Carga la última sesión automáticamente al inicio.
- **Memory:** El `MemoryStore` inyecta su `preamble()` en el System Prompt al inicio. Tools: `memory_save`, `memory_recall`.

## Comportamientos Específicos (Pitfalls)
- **Prompt Caching:** `OpenAICompatibleProvider` inyecta `cache_control` solo si `ENABLE_PROMPT_CACHING=True` y el modelo lo soporta.
- **Safe Split Point:** La estrategia de compactación nunca corta un mensaje `tool` de su `assistant` correspondiente.
- **Streaming:** `AgentLoop.stream()` yieldea chunks de texto. La TUI los renderiza en tiempo real. Timeout de 300s. Maneja errores 503 del proveedor sin crashear.
- **Multimodal:** Imágenes van en Base64 (como `image_url`). El `FileAwareInput` intercepta el pegado de archivos para que no se escriban como texto. Usa `read_document` para PDFs, DOCX, XLSX y PPTX.
- **Hooks de Bash:** Si un comando contiene `capture_snapshot.py`, inyecta automáticamente `--tools observations.json` para que la skill `agent-harness-explorer` funcione.
- **Pricing:** Usa `PricingProvider`. OpenRouter consulta API con caché en `.harness/pricing_cache.json` (TTL configurable). OpenAI/Groq leen `pricing.json`. El comando `/cost` muestra el gasto.
- **Rich Rendering:** `RichMessage` parsea bloques ```table, ```tree y ```json y los renderiza con Rich.
- **Flujo de Agentes:** El panel de debug (F1) muestra un `Tree` con el flujo en tiempo real (`start`, `end`, `handoff`).