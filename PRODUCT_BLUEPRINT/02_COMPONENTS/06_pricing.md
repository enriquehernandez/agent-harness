# Pricing (Costes)

## El Problema
Los LLMs cuestan dinero por token. Sin telemetría, el usuario no sabe cuánto gasta.

## La Solución: PricingProvider
El `PricingProvider` calcula el coste usando una `PricingSource`:

- **APIPricingSource**: Consulta la API del proveedor (OpenRouter) y cachea en `.harness/pricing_cache.json` con TTL configurable.
- **JSONPricingSource**: Lee un archivo local (`pricing.json`) para proveedores sin API pública (OpenAI, Groq).
- **FakePricingSource**: Sin coste (tests).

## Integración
El coste se calcula **al terminar el bucle**, no en cada step: `AgentLoop._calculate_total_cost()` consulta al provider (`get_cost()`) al devolver la respuesta final y al agotar `max_iterations`, tanto en `run()` como en `stream()`, y guarda el importe en `cost_usd` junto al `usage_total` acumulado. Existe un método `_calculate_cost()` (`get_cost_pricing()`), pero el loop no lo invoca. La TUI muestra el acumulado en el dashboard.