# Informe de Arquitectura — Agent Harness

**Proyecto:** Agent Harness  
**Versión:** 0.1.0  
**Python:** >=3.11,<3.13  
**Gestor de paquetes:** `uv` / Hatchling  
**Fecha del análisis:** 2026-11-16  

---

## 1. Resumen Ejecutivo

El proyecto **Agent Harness** es un motor de ejecución de agentes autónomos de nivel producción, construido desde cero en Python. Sigue una arquitectura hexagonal donde el núcleo (`AgentLoop`) está completamente desacoplado de los proveedores de IA y de las herramientas.

La arquitectura se organiza en capas bien definidas:

| Capa | Responsabilidad | Ejemplos |
|------|----------------|----------|
| **Presentación** | TUI (Textual), CLI, comandos del sistema | `app/tui/` |
| **Orquestación** | Bucle ReAct, A2A (agente-agente), subagentes | `app/core/harness/` |
| **Dominio** | LLM, herramientas, permisos, contexto, precios | `app/core/llm/`, `app/core/harness/tool.py`, `app/core/pricing/` |
| **Infraestructura** | Memoria (SQLite/vectores), sesiones, logging | `app/core/harness/memory/`, `.harness/` |

---

## 2. Arquitectura de Alto Nivel

```
┌─────────────┐
│   Usuario   │
└──────┬──────┘
       ▼
┌─────────────────┐
│   Textual TUI   │  ← Presentación (Rich, temas, debug panel)
└────────┬────────┘
         ▼
┌─────────────────┐
│   AgentLoop     │  ← Orquestación ReAct (núcleo desacoplado)
└────────┬────────┘
         ├──────────────┬──────────────┐
         ▼              ▼              ▼
   ┌─────────┐   ┌──────────┐   ┌──────────┐
   │ BaseLLM │   │ ToolReg  │   │ PermGate │  ← Dominio (inyectado)
   └─────────┘   └──────────┘   └──────────┘
         │              │
         ▼              ▼
   ┌─────────┐   ┌──────────┐
   │Providers│   │ MCP Cli. │  ← Adaptadores (OpenAI, OpenRouter, Groq)
   └─────────┘   └──────────┘
         │
         ▼
   ┌─────────┐   ┌──────────┐
   │ Context │   │ Memory   │  ← Memoria (SQLite, vectores, archivos)
   └─────────┘   └──────────┘
```

---

## 3. Desglose por Módulos

### 3.1. Núcleo del Harness (`app/core/harness/`)

| Módulo | Responsabilidad | Clave clave |
|--------|----------------|-------------|
| `loop.py` | Bucle ReAct principal (`AgentLoop`). Orquesta LLM → herramientas → contexto. Maneja reintentos, permisos y costes. | `AgentLoop`, `LoopResult` |
| `context.py` | Gestión del historial de mensajes, compactación de contexto (resumen/deslizante/ninguno). | `ContextManager` |
| `tool.py` | Registro y ejecución de herramientas locales y remotas (MCP). | `ToolRegistry`, `BaseTool`, `ToolResult` |
| `permissions.py` | Gate de permisos con diff-first. Interfaz para aprobar/denegar ejecución de herramientas. | `PermissionGate`, `Decision` |
| `compaction.py` | Estrategias de compactación de contexto: resumen, ventana deslizante, ninguno. | `CompactionStrategy`, `SummarizationStrategy`, `SlidingWindowStrategy`, `NoneStrategy` |
| `session.py` | Gestión de sesiones (guardado, carga, historial JSON). | — |
| `transcript.py` | Transcripción de conversaciones. | — |
| `memory/` | Backends de memoria persistente: SQLite (FTS5), vectores (sqlite-vec+fastembed), archivos, fanout. | `SQLiteMemory`, `VectorMemory`, `FilesMemory`, `InMemoryMemory`, `FanoutMemory` |
| `a2a/` | Orquestación agente-agente con 4 estrategias: supervisor, secuencial, paralelo, swarm. | `OrchestratorTool`, `AgentCard`, `SupervisorStrategy`, etc. |

### 3.2. Capa de LLM (`app/core/llm/`)

| Módulo | Responsabilidad |
|--------|----------------|
| `base.py` | Interfaz abstracta `BaseLLM` y `LLMResponse`. Proveedores inyectables. |
| `providers/openai_provider.py` | Proveedor OpenAI / OpenRouter / Groq (compatibles con SDK de OpenAI). |
| `providers/fake.py` | Proveedor falso para tests sin consumo de tokens. |
| `registry.py` | Registro de proveedores (patrón Registry). |

### 3.3. Capa de Precios (`app/core/pricing/`)

| Módulo | Responsabilidad |
|--------|----------------|
| `base.py` | Interfaz de cálculo de costes. |
| `registry.py` | Registro de fuentes de precios. |
| `sources/` | Fuentes: API (OpenRouter), JSON estático (OpenAI/Groq), fake. |

### 3.4. Interfaz de Usuario (`app/tui/`)

| Módulo | Responsabilidad |
|--------|----------------|
| `app.py` | Aplicación principal de Textual. |
| `dashboard.py` | Panel principal de la TUI. |
| `debug_screen.py` | Panel de debug (F1). |
| `widgets.py` | Widgets reutilizables (tablas, árboles, bloques de código). |
| `commands.py` | Comandos del sistema (`/help`, `/model`, `/tools`, `/session`, etc.). |
| `prompt.py` | Entrada de usuario, soporte para imágenes (Base64). |
| `suggester.py` | Autocompletado. |

---

## 4. Patrón de Diseño Principal: ReAct

El `AgentLoop` implementa una variante del patrón **ReAct** (Reasoning + Acting):

1. El LLM recibe el historial de mensajes y los esquemas de herramientas disponibles.
2. El LLM responde con:
   - **Texto final** → se retorna `LoopResult` y termina el bucle.
   - **Llamadas a herramientas** → se validan permisos (`PermissionGate`), se ejecutan (`ToolRegistry`), y los resultados se inyectan al contexto.
3. El ciclo se repite hasta `max_iterations` o respuesta final.

### Flujo detallado

```
Usuario → TUI → AgentLoop.run()
         │
         ▼
   ┌─────────────────┐
   │ ContextManager  │ ← Añade mensaje de usuario
   └────────┬────────┘
            │
            ▼
   ┌─────────────────┐    pasos < max_steps?
   │ LLM.chat()      │ ───No───┐
   └────────┬────────┘         │
            │ Sí               │
   ┌────────▼────────┐         │
   │ ¿Hay tool_calls?│─────────┘
   └────────┬────────┘
            │ No
            ▼
   ┌─────────────────┐
   │ LoopResult      │ ← Respuesta final
   └─────────────────┘
            │ Sí
            ▼
   ┌─────────────────┐
   │ PermissionGate  │ ← Verifica permiso
   └────────┬────────┘
            │ DENY → error en contexto
            │ ALLOW
            ▼
   ┌─────────────────┐
   │ ToolRegistry    │ ← Ejecuta herramienta
   └────────┬────────┘
            │ Éxito/Fallo
            ▼
   ┌─────────────────┐
   │ ContextManager  │ ← Inyecta resultado
   └────────┬────────┘
            │
            └────► (vuelve al paso 2)
```

---

## 5. Patrones de Diseño Identificados

| Patrón | Ubicación | Descripción |
|--------|-----------|-------------|
| **Hexagonal / Ports & Adapters** | `app/core/` | Núcleo desacoplado de proveedores y herramientas. |
| **ReAct (Reasoning + Acting)** | `loop.py` | Bucle LLM → herramientas → contexto. |
| **Registry** | `llm/registry.py`, `harness/tool.py` | Registro de proveedores y herramientas. |
| **Strategy** | `harness/compaction.py`, `harness/a2a/strategies/` | Estrategias de compactación y de A2A intercambiables. |
| **Dependency Injection** | Constructor de `AgentLoop` | LLM, herramientas, permisos inyectados. |
| **Command** | `tui/commands.py` | Comandos del sistema (`/help`, `/model`, etc.). |
| **Factory** | `harness/memory/factory.py` | Creación de backends de memoria. |
| **Observer / Pub-Sub** | `harness/a2a/orchestrator.py` | Delegación de tareas entre agentes. |

---

## 6. Acoplamiento y Dependencias

### 6.1. Dependencias de producción

| Categoría | Dependencias |
|-----------|--------------|
| Núcleo | `python-dotenv`, `pydantic-settings`, `httpx` |
| LLM | `openai` (SDK base compatible con OpenRouter/Groq) |
| MCP | `mcp` (cliente Model Context Protocol) |
| TUI | `rich`, `textual>=8.2.8`, `textual-image[textual]>=0.12.0` |
| Resiliencia | `tenacity>=9.2.1` |
| Memoria vectorial | `onnxruntime<1.24.1`, `sqlite-vec>=0.1.9`, `fastembed>=0.9.1` |

### 6.2. Dependencias de desarrollo

| Dependencia | Propósito |
|-------------|-----------|
| `pytest` | Tests unitarios y de integración. |
| `pytest-asyncio` | Soporte para código asíncrono. |
| `pytest-cov` | Medición de cobertura. |
| `tomlscript` | Scripts definidos en `pyproject.toml`. |

---

## 7. Problemas de Arquitectura Detectados

### 7.1. Críticos (en `loop.py`)

| # | Problema | Severidad |
|---|----------|-----------|
| 1 | `ToolResult` usado pero no importado → `NameError` | Alta |
| 2 | `LoopResult.usage_total` con `default_factory=list` en vez de `dict` | Alta |
| 3 | F-string roto en último `yield` de `stream()` → `SyntaxError` | Alta |
| 4 | `run()` no inyecta `ctx.add_tool_result()` en éxito de herramienta → rompe ReAct | Media-Alta |

### 7.2. Estructurales

| # | Problema | Severidad |
|---|----------|-----------|
| 5 | Duplicación masiva entre `run()` y `stream()` | Alta |
| 6 | `repair_counts` inconsistente (instancia vs local) | Alta |
| 7 | `run()` sin timeout; `stream()` sí | Media |
| 8 | Contratos de retorno heterogéneos (`LoopResult` vs `dict`) | Media |
| 9 | Acoplamiento a `settings.LLM_STREAM_TIMEOUT` global | Media |
| 10 | `Any` importado sin usar | Baja |

---

## 8. Recomendaciones de Refactorización

### Inmediatas (bloqueantes)

1. Importar `ToolResult` desde `.tool`.
2. Corregir `default_factory=list` → `default_factory=dict` en `LoopResult.usage_total`.
3. Arreglar f-string roto en `stream()` (`"tools_used": tools_used,`).

### Estructurales

4. Extraer método privado `_execute_tool_calls()` para eliminar duplicación entre `run()` y `stream()`.
5. Unificar `repair_counts` como estado local por ejecución.
6. Añadir `ctx.add_tool_result()` en `run()` cuando la herramienta tiene éxito.
7. Añadir timeout a `run()` con `asyncio.timeout`.
8. Tipar `stream()` como `AsyncGenerator`.
9. Crear interfaz/Protocolo para reducir acoplamiento.
10. Calcular `cost_usd` también en `run()`.

### Calidad de código

11. Eliminar comentarios con emojis y código comentado.
12. Eliminar import `Any` sin usar.
13. Añadir docstrings a métodos públicos.
14. Hacer `max_repair_attempts` configurable.

---

## 9. Métricas del Proyecto

| Métrica | Valor |
|---------|-------|
| Lenguaje | Python 3.11+ |
| Gestor de paquetes | `uv` |
| Sistema de construcción | Hatchling |
| Paquete principal | `app` |
| Cobertura reportada | 100% (según README) |
| Framework de tests | `pytest`, `pytest-asyncio`, `pytest-cov` |
| Framework TUI | `Textual` |
| Memoria vectorial | `sqlite-vec` + `fastembed` |
| Protocolo de herramientas | `MCP` |
| Estrategias A2A | Supervisor, Secuencial, Paralelo, Swarm |

---

## 10. Conclusión

El proyecto tiene una arquitectura sólida y bien estructurada con separación clara de responsabilidades, inyección de dependencias y patrones de diseño modernos (hexagonal, ReAct, Strategy, Registry). Sin embargo, el archivo `loop.py` presenta problemas críticos de sintaxis e importación que impiden su ejecución correcta, además de duplicación de código e inconsistencias de estado que deben corregirse antes de considerar el módulo estable para producción.

---
*Informe generado en la carpeta `reports/` — Archivos anteriores eliminados previamente.*