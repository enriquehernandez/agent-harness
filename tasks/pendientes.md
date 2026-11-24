# Tareas Pendientes — Funcionalidad documentada como ausente

> Recopilado tras la auditoría de los commits del 16–24 de noviembre de 2026.
> Cada item corresponde a una afirmación que tuvo que corregirse en la documentación
> porque el código **no implementa** esa funcionalidad (o la implementa de forma distinta).
> Las tareas en ejecución están en `tasks/actual.md`; las completadas, en `tasks/completadas.md`.

## Prioridad baja — Limpieza y artefactos

- [ ] **Verificar soporte del modelo antes de aplicar prompt caching.**
      `OpenAICompatibleProvider` inyecta `cache_control` cuando `ENABLE_PROMPT_CACHING=True`
      (`app/core/llm/providers/openai_provider.py`), sin comprobar que el modelo lo
      acepte. La doc lo refleja como limitación conocida en `docs/herramientas.md`.
