# El Agent Loop (Bucle ReAct)

El `AgentLoop` es el corazón del Harness. Su trabajo es orquestar el diálogo entre el LLM y las herramientas.

## Funcionamiento

El bucle sigue el patrón **ReAct** (Reason + Act). Se ejecuta hasta que el LLM decida que ya tiene la respuesta final (es decir, devuelva un mensaje sin `tool_calls`).

```text
Bucle (max_iteraciones):
  1. Llamar al LLM con el historial actual y las herramientas.
  2. Si el LLM no pide herramientas -> Devolver respuesta final. FIN.
  3. Si pide herramientas:
     a. Verificar permisos con el PermissionGate.
     b. Ejecutar la herramienta (Local o MCP).
     c. Inyectar el resultado de la herramienta en el historial como un mensaje de rol `tool`.
  4. Repetir.
```

## Herramientas Locales de Archivos

`register_core_tools()` (`app/tools/__init__.py`) registra `read_file`, `write_file` y `edit_file` sobre un `base_dir` común. `EditFileTool` (`app/tools/filesystem.py`) recibe `path` y una lista `edits` de pares `oldText`/`newText`: valida que la ruta esté dentro de `base_dir`, que el archivo exista y que cada `oldText` aparezca en el contenido; aplica las sustituciones en orden y escribe el resultado. Rechaza `oldText` vacío o no encontrado devolviendo `ToolResult(success=False)`. `PermissionGate` usa ese mismo formato para generar el diff mostrado al pedir confirmación (`app/core/harness/permissions.py`).

## Manejo de Errores y Límites

- **Max Iteraciones**: Si el agente entra en un bucle infinito (ej. llamar a la misma herramienta 10 veces), el bucle se detiene y devuelve un error de control.
- **Errores de Herramientas**: Si una herramienta falla (ej. el archivo no existe), el error no rompe el programa. Se inyecta como un mensaje `tool` para que el LLM "lea" el error y decida si intenta otra cosa o se disculpa.
- **Permisos Denegados**: Si el usuario deniega el uso de `bash`, el LLM recibe un mensaje de error indicando que no tiene permiso, forzándolo a buscar alternativas.

## Código Clave (app/core/harness/loop.py)

`run()` devuelve un `LoopResult` y `stream()` es un generador asíncrono que emite `AgentEvent` (`text_chunk`, `tool_start`, `tool_end`, `result` y `error`; ver `app/core/harness/events.py`). Ambas comparten la misma secuencia:

```text
run(user_input, context=None) -> LoopResult:
  ctx = context or ContextManager(); ctx.add_user(user_input)
  para step en 1..max_iterations:
    await ctx.maybe_compact(llm)                 # al superar el 80% de la ventana
    response = await llm.chat(ctx.get_messages(), tools=schemas)
    _accumulate_usage(usage_total, response.usage)
    si no hay tool_calls:
      final = response.content or ""
      si critic_tool y reintentos < 2:
        critique = await critic_tool.run(proposed_response=final, agent_rules=...)
        si critique.success y content.startswith("REJECTED"):
          reintentos += 1; ctx.add_assistant(final)
          ctx.add_user("[SISTEMA - FEEDBACK DEL CRÍTICO]: ...")
          continuar                              # máx. 2 reintentos
      ctx.add_assistant(final)
      return LoopResult(final, step, tools_used, usage_total,
                        cost_usd=await _calculate_total_cost(usage_total))
    ctx.add_assistant(response.content, response.tool_calls)
    para tc en response.tool_calls:
      await _execute_tool(tc, ctx)               # permisos + ejecución + inyección
      tools_used.append(tc["name"])
  return LoopResult("[Max iterations reached without final answer]", ...,
                    cost_usd=await _calculate_total_cost(usage_total))

stream(user_input, context=None, timeout_seconds=None) -> AsyncIterator[AgentEvent]:
  mismo bucle con llm.stream_chat() dentro de asyncio.timeout(timeout):
    str                   -> yield AgentEvent("text_chunk", {"text": chunk})
    {"type": "tool_call"} -> guardar; yield AgentEvent("tool_start", chunk)
    {"type": "usage"}     -> step_usage; _accumulate_usage(usage_total, ...)
  sin tool_calls: crítico (máx. 2; al límite avisa) ->
                  yield AgentEvent("result", {... "cost_usd": ...})
  con tool_calls:
    success, result = await _execute_tool(tc, ctx)
    yield AgentEvent("tool_end", {"tool": tc["name"],
                                  "success": success, "result": result})
  timeout o excepción -> yield AgentEvent("error", {"message": ..., "is_timeout": bool})

_execute_tool(tc, ctx):
  decision = await permissions.check(tc["name"], tc["arguments"])
  DENY / tool inexistente -> ctx.add_tool_result(id, mensaje de error) -> (False, None)
  result = await tool.run(**args)   # excepciones -> ToolResult(success=False)
  éxito: repair_counts.pop(tool); ctx.add_tool_result(id, result.content)
  fallo: repair_counts[tool] += 1; mensaje "Reintento N/3";
         a partir de 3 -> "Detente y pide ayuda al usuario."
```

El coste se calcula al cerrar el bucle con `_calculate_total_cost()` (tanto en la respuesta final como al agotar `max_iterations`); `_calculate_cost()` existe pero el loop no lo invoca. Al agotar el límite, `run()` devuelve `[Max iterations reached without final answer]` y `stream()` emite `[Max iterations (N) reached without final answer]`.
