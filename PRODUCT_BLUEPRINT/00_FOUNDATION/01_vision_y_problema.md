# Visión y Problema

## El Problema
Los LLMs son excelentes generando texto, pero no pueden interactuar con el mundo real por sí solos. Los "chatbots" tradicionales están atrapados en una ventana de chat. Para que la IA sea útil de verdad, necesita **ejecutar acciones** (leer archivos, consultar APIs, ejecutar comandos).

Sin embargo, darle acceso a un LLM a un sistema operativo o a una API de producción es peligroso:
1. **Alucinaciones:** El LLM podría intentar ejecutar un comando destructivo (`rm -rf /`) por error.
2. **Pérdida de Contexto:** Las conversaciones largas hacen que el LLM olvide lo que hizo hace 5 minutos.
3. **Dependencia de Proveedor:** El código se acopla a OpenAI, lo que dificulta cambiar a un modelo local o más barato.

## La Solución: El Agent Harness
Este proyecto es un **Harness** (arnés): la infraestructura que envuelve al LLM y le da "manos" de forma segura y controlada.

Nuestra visión es construir un motor genérico que:
- Sea **Agnóstico al LLM**: La lógica de negocio no sabe si está hablando con GPT-4o, Claude o un modelo local.
- Sea **Seguro por defecto**: El usuario tiene la última palabra antes de ejecutar acciones críticas.
- Sea **Extensible (MCP)**: Pueda conectarse a cualquier herramienta del mundo mediante el estándar *Model Context Protocol*.
- Gestione su propia **Memoria**: Sepa resumir conversaciones para no romper el límite de tokens.

Este proyecto demuestra cómo llevar la IA generativa desde un "juguete" de pruebas de concepto hasta un entorno operativo real.