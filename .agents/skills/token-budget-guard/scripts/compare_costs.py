import json
import argparse
from pathlib import Path


def compare(old_report: Path, new_report: Path):
    old = json.loads(old_report.read_text())
    new = json.loads(new_report.read_text())

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
    parser = argparse.ArgumentParser()
    parser.add_argument("old")
    parser.add_argument("new")
    args = parser.parse_args()
    print(json.dumps(compare(Path(args.old), Path(args.new)), indent=2))
