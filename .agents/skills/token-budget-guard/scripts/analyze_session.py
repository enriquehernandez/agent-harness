import json
import argparse
from pathlib import Path
from fetch_pricing import get_pricing


def analyze_session(session_file: Path, model_name: str = "openai/gpt-4o"):
    if not session_file.exists():
        return None

    data = json.loads(session_file.read_text())
    usage = data.get("usage_total", {})

    prompt = usage.get("prompt_tokens", 0)
    completion = usage.get("completion_tokens", 0)
    total = usage.get("total_tokens", prompt + completion)

    pricing = get_pricing(model_name)
    cost = (prompt * pricing["input"]) + (completion * pricing["output"])

    return {
        "session_id": data.get("session_id", "unknown"),
        "model": model_name,
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": total,
        "cost_usd": round(cost, 6),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--session", required=True)
    parser.add_argument("--model", default="openai/gpt-4o")
    args = parser.parse_args()

    session_file = Path(f".harness/sessions/{args.session}.json")
    result = analyze_session(session_file, args.model)

    if result is None:
        print(f"Error: Session {args.session} not found.")
    else:
        print(json.dumps(result, indent=2))
