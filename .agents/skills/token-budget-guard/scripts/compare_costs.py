import json
import argparse
from pathlib import Path
from analyze_session import analyze_session


def compare(old_session: str, new_session: str, model: str):
    old = analyze_session(Path(f".harness/sessions/{old_session}.json"), model)
    new = analyze_session(Path(f".harness/sessions/{new_session}.json"), model)

    if old is None or new is None:
        missing = old_session if old is None else new_session
        return {"error": f"Session {missing} not found."}

    cost_diff = new["cost_usd"] - old["cost_usd"]
    token_diff = new["total_tokens"] - old["total_tokens"]

    return {
        "old_session": old["session_id"],
        "new_session": new["session_id"],
        "cost_delta": round(cost_diff, 6),
        "token_delta": token_diff,
        "status": "increased" if cost_diff > 0 else "decreased",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Compare token usage/cost between two sessions.")
    parser.add_argument("--old", required=True, help="Old session ID")
    parser.add_argument("--new", required=True, help="New session ID")
    parser.add_argument("--model", default="openai/gpt-5")
    args = parser.parse_args()
    print(json.dumps(compare(args.old, args.new, args.model), indent=2))
