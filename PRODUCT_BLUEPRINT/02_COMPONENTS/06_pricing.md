# Pricing (Costes)

## El Problema
Los LLMs cuestan dinero por token. Sin telemetría, el usuario no sabe cuánto gasta.

## La Solución: PricingProvider
El `PricingProvider` calcula el coste usando una `PricingSource`:

- **APIPricingSource**: Consulta la API del proveedor (OpenRouter) y cachea en `.harness/pricing_cache.json` con TTL configurable.
- **JSONPricingSource**: Lee un archivo local (`pricing.json`) para proveedores sin API pública (OpenAI, Groq).
- **FakePricingSource**: Sin coste (tests).

## Integración
`AgentLoop._calculate_cost()` llama al provider al final de cada step y acumula el coste en `usage_total` + `cost_usd`. La TUI muestra el acumulado en el dashboard.