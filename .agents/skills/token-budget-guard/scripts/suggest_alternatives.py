import argparse
import json
from fetch_pricing import get_pricing

# Map: current model -> (cheaper alternative, usage tip)
RECOMMENDATIONS = {
    "openai/gpt-5": {"cheaper": "openai/gpt-5-mini", "tip": "Enable prompt caching."},
    "openai/gpt-4o": {"cheaper": "openai/gpt-5-mini", "tip": "Enable prompt caching."},
    "anthropic/claude-sonnet-4.5": {"cheaper": "google/gemini-3-flash", "tip": "Use the flash-tier model for simple queries."},
    "anthropic/claude-3.5-sonnet": {"cheaper": "google/gemini-3-flash", "tip": "Use the flash-tier model for simple queries."},
}


def _blended_rate(pricing: dict) -> float:
    return (pricing["input"] + pricing["output"]) / 2


def suggest(current_model: str):
    """Suggest a cheaper alternative with savings computed from live prices."""
    rec = RECOMMENDATIONS.get(current_model)
    if rec is None:
        return {"error": "No recommendations."}

    current_price = get_pricing(current_model)
    cheaper_price = get_pricing(rec["cheaper"])

    savings_pct = 0.0
    current_rate = _blended_rate(current_price)
    if current_rate > 0:
        savings_pct = (1 - _blended_rate(cheaper_price) / current_rate) * 100

    return {
        "cheaper": rec["cheaper"],
        "savings": f"~{savings_pct:.0f}%",
        "tip": rec["tip"],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    args = parser.parse_args()
    print(json.dumps(suggest(args.model), indent=2))
