# 🧠 Agent Harness Blueprint

Bienvenido a la documentación técnica del **Agent Harness**, un motor de ejecución para agentes autónomos construido desde cero en Python. 

A diferencia de otros proyectos, este Harness no está atado a un solo LLM ni a herramientas predefinidas. Implementa los estándares modernos de la industria (MCP, Textual) y patrones de diseño de software para garantizar la escalabilidad y seguridad.

## 🗺️ Índice de Navegación

1. **Fundación**
   - [Visión y Problema](00_FOUNDATION/01_vision_y_problema.md)
   - [Glosario](00_FOUNDATION/02_glosario.md)
2. **Sistema de Diseño**
   - [Arquitectura y Diagramas](01_DESIGN_SYSTEM/01_arquitectura.md)
   - [Patrones de Diseño (SOLID)](01_DESIGN_SYSTEM/02_patrones_diseno.md)
3. **Componentes Core**
   - [El Agent Loop (ReAct)](02_COMPONENTS/01_harness_loop.md)
   - [Permission Gate y Diff-First](02_COMPONENTS/02_permission_gate.md)
   - [Context Compaction (Memoria)](02_COMPONENTS/03_context_compaction.md)
   - [Integración MCP](02_COMPONENTS/04_mcp_integration.md)
   - [Subagentes Delegados](02_COMPONENTS/05_subagents.md)
4. **Seguridad y Auditoría**
   - [Estrategia de Testing con Textual](03_SECURITY_AND_AUDIT/01_testing_y_mocks.md)