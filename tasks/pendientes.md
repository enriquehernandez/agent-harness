# Tareas Pendientes — Funcionalidad documentada como ausente

> Recopilado tras la auditoría de los commits del 16–24 de noviembre de 2026.
> Cada item corresponde a una afirmación que tuvo que corregirse en la documentación
> porque el código **no implementa** esa funcionalidad (o la implementa de forma distinta).
> Las tareas en ejecución están en `tasks/actual.md`; las completadas, en `tasks/completadas.md`.

## Prioridad media — Documentos y calidad

- [ ] **Extraer texto de `.doc`, `.xls` y `.ppt`.** `FileAwareInput`
      (`app/tui/widgets/file_aware_input.py`) los acepta como adjuntos, pero
      `read_document` (`app/tools/documents.py`) los rechaza con
      `Formato '…' no soportado por read_document.`. Escenario: usuario adjunta un `.doc`
      heredado y el agente no puede leerlo. Ver `PRODUCT_BLUEPRINT/02_COMPONENTS/10_document_reading.md`.

## Prioridad baja — Limpieza y artefactos

- [ ] **Verificar soporte del modelo antes de aplicar prompt caching.**
      `OpenAICompatibleProvider` inyecta `cache_control` cuando `ENABLE_PROMPT_CACHING=True`
      (`app/core/llm/providers/openai_provider.py`), sin comprobar que el modelo lo
      acepte. La doc lo refleja como limitación conocida en `docs/herramientas.md`.
