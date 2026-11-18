import json
import httpx
from pathlib import Path
from datetime import datetime, timedelta

CACHE_DIR = Path(".harness/token-budget-guard")
CACHE_FILE = CACHE_DIR / "pricing_cache.json"
CACHE_TTL_DAYS = 1

FALLBACK_PRICING = {"input": 1e-6, "output": 1e-6}


def _read_cache():
    if not CACHE_FILE.exists():
        return None
    try:
        return json.loads(CACHE_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def fetch_prices(force_refresh: bool = False):
    """Fetches prices from OpenRouter and caches them.

    Fallback chain on API error:
    1. Expired cache (better stale prices than invented ones).
    2. Conservative default rate ($1e-6 per token) as last resort.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    cached = _read_cache()
    if cached and not force_refresh:
        age = datetime.now() - datetime.fromisoformat(cached["timestamp"])
        if age < timedelta(days=CACHE_TTL_DAYS):
            return cached["prices"]

    try:
        response = httpx.get("https://openrouter.ai/api/v1/models", timeout=10)
        models = response.json().get("data", [])
        prices = {}
        for m in models:
            pricing = m.get("pricing", {})
            prices[m["id"]] = {
                "input": float(pricing.get("prompt", 0)),
                "output": float(pricing.get("completion", 0)),
            }
        CACHE_FILE.write_text(json.dumps({
            "timestamp": datetime.now().isoformat(),
            "prices": prices,
        }, indent=2))
        return prices
    except Exception as e:
        print(f"Error fetching prices: {e}")
        if cached:
            print("Warning: using expired pricing cache.")
            return cached["prices"]
        print("Warning: no cache available, using conservative default rates.")
        return {}


def get_pricing(model_name: str) -> dict:
    prices = fetch_prices()
    return prices.get(model_name, FALLBACK_PRICING)
