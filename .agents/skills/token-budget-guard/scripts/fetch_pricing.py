import json
import httpx
from pathlib import Path
from datetime import datetime, timedelta

CACHE_DIR = Path(".harness/token-budget-guard")
CACHE_FILE = CACHE_DIR / "pricing_cache.json"
CACHE_TTL_DAYS = 1


def fetch_prices():
    """Fetches prices from OpenRouter and caches them."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    if CACHE_FILE.exists():
        data = json.loads(CACHE_FILE.read_text())
        if datetime.now() - datetime.fromisoformat(data["timestamp"]) < timedelta(days=CACHE_TTL_DAYS):
            return data["prices"]

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
        return {}


def get_pricing(model_name: str) -> dict:
    prices = fetch_prices()
    return prices.get(model_name, {"input": 1e-6, "output": 1e-6})
