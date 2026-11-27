# Definition of Done (DoD)

> Una tarea solo se mueve a `tasks/completadas.md` y solo puede proponerse para commit cuando **todos** los puntos están en ✅. Si algo no aplica, se escribe `N/A` con el motivo; nunca se omite.
> Este archivo es la fuente de verdad. `checks/tests.md` es la lista operativa de comandos y `tasks/completadas.md` debe dejar constancia de la verificación hecha.

## 1. Código y tests

- [ ] Test escrito **antes** del código si es una feature nueva o un cambio de comportamiento (TDD).
- [ ] `uv run tom test` pasa y la cobertura reportada llega al 100 % (`--cov-fail-under=100`).
- [ ] La cobertura es significativa: los tests nuevos comprueban comportamiento, no números de línea. Mientras siga activa la tarea **P0.8**, revisar además que no se hayan añadido exclusiones en `[tool.coverage.report]` ni `# pragma: no cover` sin justificación.
- [ ] No hay tests duplicados, tests sin `assert` ni `filterwarnings` nuevos que oculten el problema.
- [ ] Si la tarea toca MCP, A2A o HTTP: `uv run tom test-integration` también pasa.
- [ ] Si toca pricing, se verifica con tests. Los scripts de diagnóstico son opcionales: trabajan en directorios temporales y no tocan cachés ni memoria reales del usuario.

## 2. Verificación en la TUI (obligatoria por tarea)

Toda entrada de `tasks/completadas.md` incluye un campo `**Prueba en TUI:**` con la secuencia ejecutada y el resultado esperado. Regla general:

- [ ] Arranca real: `uv run python -m app.main` (o `uv run tom dev`) sin errores de arranque.
- [ ] Flujo comprobado de punta a punta con `LLM_PROVIDER=fake` por defecto para no consumir tokens. Si la tarea exige un proveedor real, indicar cuál y qué se comprobó.
- [ ] Si afecta a tools o permisos: aparece el modal con el diff correcto; `/tools` lista la tool; "permitir siempre" persiste tras reiniciar.
- [ ] Si afecta a hooks: `/hooks` lista los handlers activos y sus errores; F1 (panel de debug) muestra el ciclo del hook; un `denied` bloquea la acción.
- [ ] Si afecta a sesiones o memoria: `/session list|load|save|new` y `/memory`, incluida la recarga de la TUI.
- [ ] Si afecta a provider, modelo o costes: `/provider`, `/model`, `/cost` y `/trace` devuelven valores coherentes.
- [ ] Si es documentación o código sin superficie visible: poner `N/A (solo backend/documentación)` y el comando de sustitución que se ejecutó.
- [ ] La prueba se hace **antes** de marcar la tarea como completada, y se anota tal cual se hizo (no una descripción ideal).

## 3. Seguridad y reglas del proyecto

- [ ] No hay API keys hardcodeadas ni secretos en logs, eventos de hooks ni argumentos impresos.
- [ ] No se usa `print()` en código de producción (solo `logger` o salida de UI).
- [ ] No se añaden dependencias a `pyproject.toml` sin aprobación previa (usar `uv add`).
- [ ] No se cambian las firmas de `BaseLLM`/`BaseTool` ni el diseño de la TUI sin aprobación previa.
- [ ] Toda tool sensible pasa por `PermissionGate` con diff-first; los hooks no amplían permisos ni ignoran un `deny`.
- [ ] Los scripts de verificación usan directorios temporales y restauran lo que tocan; ningún borrado afecta a datos reales.

## 4. Documentación y trazabilidad

- [ ] `tasks/completadas.md` registra: objetivo, decisión de diseño si la hubo, estado, tests y `Prueba en TUI`.
- [ ] Si se añade un componente, se actualiza `PRODUCT_BLUEPRINT` (y `README.md`/`docs/` cuando cambie el uso).
- [ ] La documentación de producto (`README.md`, `docs/`, `PRODUCT_BLUEPRINT/`, skills y `checks/`) describe **comportamiento**: no menciona IDs de tareas (`P0.x`, …) ni números de línea de código. Esas referencias solo viven en `tasks/`, y allí se usan rutas y símbolos en lugar de líneas.
- [ ] `tasks/actual.md` y `tasks/pendientes.md` están sincronizados (la tarea sale de "en curso" y entra en "completadas").

## 5. Puerta de commit

- [ ] Todos los puntos anteriores están en ✅ o `N/A` justificado.
- [ ] `git status` revisado: solo entran los archivos de la tarea. Los cambios ajenos (p. ej. `.harness/hooks.json` o `.gitignore` del usuario) se dejan intactos y se mencionan.
- [ ] `git diff` revisado: sin secretos, sin archivos generados (`coverage.xml`, `htmlcov/`, `junit.xml`, `.coverage` ya están ignorados).
- [ ] Commit pequeño y atómico, **solo con aprobación explícita del usuario**. Sin aprobación, los cambios quedan sin commitear.

## Ciclo de una tarea y plantillas

El mismo ID (`P0.1`, `P1.3`, …) acompaña a la tarea en los tres archivos:

`tasks/pendientes.md` (planificada) → `tasks/actual.md` (en curso) → `tasks/completadas.md` (DoD completo).

La plantilla se cumple **desde el principio**: una tarea pendiente ya debe decir cómo se probará en la TUI, y una tarea en curso debe registrar qué se ha ejecutado realmente. No hace falta rellenar desde el día 1 todo el detalle de cierre, pero sí los campos marcados como obligatorios.

### Plantilla — tarea pendiente (obligatorio)

```markdown
### P0.N <Título>
- **Objetivo:** qué problema resuelve.
- **Criterio de aceptación:** condición observable de éxito.
- **Prueba en TUI prevista:** pasos que se ejecutarán al terminar (o `N/A` justificado).
- **DoD:** ⛔ pendiente — se marca ✅ al cerrar en `tasks/completadas.md`.
```

### Plantilla — tarea en curso (`tasks/actual.md`)

```markdown
## P0.N <Título>
- **Objetivo:** copiado de `tasks/pendientes.md`.
- **Estado:** En curso. Qué se está haciendo.
- **Avance:** [x] test de regresión escrito · [ ] código · [ ] verificación TUI.
- **Pruebas ejecutadas:** comandos y resultado real.
- **Prueba en TUI:** pasos ya ejecutados y resultado observado (o «pendiente»).
- **Bloqueos:** qué impide avanzar, si hay.
- **Siguiente paso:** acción concreta.
```

### Plantilla — tarea completada

```markdown
## P0.N <Título>

- **Objetivo:** qué problema resuelve.
- **Diseño elegido:** decisiones relevantes (si aplica).
- **Estado:** Completada. Dónde vive el cambio.
- **Tests:** `tests/...::test_...` y resultado de `uv run tom test`.
- **Prueba en TUI:** 1) arrancar con `uv run python -m app.main`; 2) `<comando>`; 3) `<comando>`. Esperado: `<resultado visible>`.
- **DoD:** ✅ tests/cobertura · ✅ TUI · ✅ seguridad · ✅ docs · ✅ listo para commit (o ⛔ con lo que falta).
```
