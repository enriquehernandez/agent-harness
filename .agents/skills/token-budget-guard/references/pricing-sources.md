# Pricing Sources

## Primary Source: OpenRouter API
The script `scripts/fetch_pricing.py` fetches model pricing directly from OpenRouter's public API:
`https://openrouter.ai/api/v1/models`

This ensures that the costs reported are always up-to-date and reflect the actual rates charged by the provider (for models routed through OpenRouter).

## Caching Mechanism
To avoid hitting the API on every request and to respect rate limits, the pricing data is cached locally:
- **Location:** `.harness/token-budget-guard/pricing_cache.json`
- **TTL (Time-To-Live):** 1 day (configurable in `fetch_pricing.py` via `CACHE_TTL_DAYS`).

If the cache is valid (less than 1 day old), the script uses the local file. If it's expired or missing, it fetches fresh data from the API.

## Fallback Behavior
If the API is unreachable or returns an error:
1. The script will log a warning.
2. It will attempt to use the expired cache if it exists.
3. If no cache exists at all, it will use a conservative default rate (`$1e-6` per input token, `$1e-6` per output token) to avoid division by zero and indicate that the cost is an estimate.

## Custom Pricing (Non-OpenRouter Models)
If you are using models directly via OpenAI, Anthropic, or Groq (bypassing OpenRouter), you must manually update the pricing in `scripts/fetch_pricing.py` or ensure your provider returns usage costs in the session JSON.