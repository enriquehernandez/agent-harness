import json
import argparse
from pathlib import Path
from datetime import datetime
from analyze_session import analyze_session
from suggest_alternatives import suggest

REPORTS_DIR = Path(".harness/token-budget-guard/reports")
CONFIG_FILE = Path(".harness/token-budget-guard/budget-config.json")


def load_budget_config() -> dict:
    """Loads the optional budget config. Falls back to safe defaults."""
    defaults = {"default_budget_usd": 5.0,
                "alert_threshold": 0.8, "model_overrides": {}}
    if not CONFIG_FILE.exists():
        return defaults
    try:
        user_cfg = json.loads(CONFIG_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return defaults
    defaults.update({k: v for k, v in user_cfg.items() if k in defaults})
    return defaults


def resolve_budget(cli_budget: float, config: dict, model: str) -> float:
    """CLI --budget wins, then per-model override, then config default."""
    if cli_budget is not None:
        return cli_budget
    override = config["model_overrides"].get(model, {})
    if "budget_usd" in override:
        return override["budget_usd"]
    return config["default_budget_usd"]


def budget_status(cost: float, budget: float, threshold: float) -> str:
    if cost > budget:
        return "⚠️ **Budget exceeded**"
    if budget > 0 and cost >= budget * threshold:
        return "⚠️ **Approaching budget** ({:.0f}% used)".format(cost / budget * 100)
    return "✅ **Within budget**"


def generate_report(session_id: str, budget: float, model: str, threshold: float = 0.8):
    session_file = Path(f".harness/sessions/{session_id}.json")
    result = analyze_session(session_file, model)

    if result is None:
        return f"Error: Session {session_id} not found."

    cost = result["cost_usd"]
    status = budget_status(cost, budget, threshold)

    # Recommendations (savings computed from live prices)
    suggestion = suggest(model)

    rec_text = ""
    if "cheaper" in suggestion:
        rec_text = f"- Switch to `{suggestion['cheaper']}` to save {suggestion['savings']}.\n- {suggestion['tip']}"
    else:
        rec_text = "No cheaper alternatives found for this model."

    # Full report saved to disk (with markdown header)
    report = f"""### Token Budget Report

**Session:** `{session_id}`
**Model:** `{model}`
**Budget:** `${budget:.2f}`
**Status:** {status}

### 📊 Cost Breakdown

| Concept | Tokens | Cost (USD) |
| :--- | :--- | :--- |
| Prompt (Input) | {result['prompt_tokens']:,} | ${result['prompt_cost_usd']:.6f} |
| Completion (Output) | {result['completion_tokens']:,} | ${result['completion_cost_usd']:.6f} |
| **Total** | **{result['total_tokens']:,}** | **${cost:.6f}** |

### 💡 Recommendations

{rec_text}
    """

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = REPORTS_DIR / f"{session_id}_{timestamp}.md"
    report_file.write_text(report)

    # Output returned to the TUI (table + summary only, no raw markdown header)
    return f"""
| Concept | Tokens | Cost (USD) |
| :--- | :--- | :--- |
| Prompt (Input) | {result['prompt_tokens']:,} | ${result['prompt_cost_usd']:.6f} |
| Completion (Output) | {result['completion_tokens']:,} | ${result['completion_cost_usd']:.6f} |
| **Total** | **{result['total_tokens']:,}** | **${cost:.6f}** |


Status: {status}

Saved to: {report_file.name}
    """


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--session", required=True)
    parser.add_argument("--budget", type=float, default=None,
                        help="Budget in USD. Overrides the config file.")
    parser.add_argument("--model", default="openai/gpt-5")
    args = parser.parse_args()

    config = load_budget_config()
    budget = resolve_budget(args.budget, config, args.model)

    print(generate_report(args.session, budget,
          args.model, config["alert_threshold"]))
