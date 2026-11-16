import argparse
import json

RECOMMENDATIONS = {
    "openai/gpt-4o": {"cheaper": "openai/gpt-4o-mini", "savings": "~94%", "tip": "Enable caching."},
    "anthropic/claude-3.5-sonnet": {"cheaper": "google/gemini-2.0-flash-001", "savings": "~97%", "tip": "Use for simple queries."},
}


def suggest(current_model: str):
    return RECOMMENDATIONS.get(current_model, {"error": "No recommendations."})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    args = parser.parse_args()
    print(json.dumps(suggest(args.model), indent=2))
