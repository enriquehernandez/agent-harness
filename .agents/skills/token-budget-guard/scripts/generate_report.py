import json
import argparse
from pathlib import Path
from datetime import datetime
from analyze_session import analyze_session
from suggest_alternatives import suggest

REPORTS_DIR = Path(".harness/token-budget-guard/reports")


def generate_report(session_id: str, budget: float, model: str):
    session_file = Path(f".harness/sessions/{session_id}.json")
    result = analyze_session(session_file, model)

    if result is None:
        return f"Error: Session {session_id} not found."

    cost = result["cost_usd"]
    status = "⚠️ **Budget exceeded**" if cost > budget else "✅ **Within budget**"

    # Recomendaciones
    suggestion = suggest(model)

    rec_text = ""
    if "cheaper" in suggestion:
        rec_text = f"- Switch to `{suggestion['cheaper']}` to save {suggestion['savings']}.\n- {suggestion['tip']}"
    else:
        rec_text = "No cheaper alternatives found for this model."

    # 1. El reporte completo para guardar en disco (SIN indentación en el bloque table)
    report = f"""### Token Budget Report

**Session:** `{session_id}`
**Model:** `{model}`
**Budget:** `${budget:.2f}`
**Status:** {status}

### 📊 Cost Breakdown

| Concept | Tokens | Cost (USD) |
| :--- | :--- | :--- |
| Prompt (Input) | {result['prompt_tokens']:,} | ${result['prompt_tokens'] * 2.5e-6:.6f} |
| Completion (Output) | {result['completion_tokens']:,} | ${result['completion_tokens'] * 1e-5:.6f} |
| **Total** | **{result['total_tokens']:,}** | **${cost:.6f}** |

### 💡 Recommendations

{rec_text}
    """

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = REPORTS_DIR / f"{session_id}_{timestamp}.md"
    report_file.write_text(report)

    # 2. Lo que se devuelve a la TUI (Solo la tabla + resumen, para que no se vea el markdown crudo)
    return f"""
| Concept | Tokens | Cost (USD) |
| :--- | :--- | :--- |
| Prompt (Input) | {result['prompt_tokens']:,} | ${result['prompt_tokens'] * 2.5e-6:.6f} |
| Completion (Output) | {result['completion_tokens']:,} | ${result['completion_tokens'] * 1e-5:.6f} |
| **Total** | **{result['total_tokens']:,}** | **${cost:.6f}** |


Status: {status}

Saved to: {report_file.name}
    """


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--session", required=True)
    parser.add_argument("--budget", type=float, default=5.00)
    parser.add_argument("--model", default="openai/gpt-4o")
    args = parser.parse_args()

    print(generate_report(args.session, args.budget, args.model))
