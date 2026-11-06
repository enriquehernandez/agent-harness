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

## Manejo de Errores y Límites

- **Max Iteraciones**: Si el agente entra en un bucle infinito (ej. llamar a la misma herramienta 10 veces), el bucle se detiene y devuelve un error de control.
- **Errores de Herramientas**: Si una herramienta falla (ej. el archivo no existe), el error no rompe el programa. Se inyecta como un mensaje `tool` para que el LLM "lea" el error y decida si intenta otra cosa o se disculpa.
- **Permisos Denegados**: Si el usuario deniega el uso de `bash`, el LLM recibe un mensaje de error indicando que no tiene permiso, forzándolo a buscar alternativas.

## Código Clave (app/core/harness/loop.py)

```python
for step in range(1, self.max_iterations + 1):
    await ctx.maybe_compact(self.llm) # Chequeo de tokens
    
    response = await self.llm.chat(
        messages=ctx.get_messages(),
        tools=self.tools.all_schemas() or None,
    )
    
    if not response.tool_calls:
        return LoopResult(final_answer=response.content, ...)
        
    ctx.add_assistant(response.content, response.tool_calls)
    
    for tc in response.tool_calls:
        # 1. Permisos, 2. Ejecución, 3. Inyección de resultado
        # ...
```
