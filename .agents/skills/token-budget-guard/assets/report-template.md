# Token Budget Report

**Session:** `{{session_id}}`
**Model:** `{{model}}`
**Date:** {{timestamp}}

## Financial Summary

| Concept | Tokens | Cost (USD) |
| :--- | :--- | :--- |
| Prompt (Input) | {{prompt_tokens}} | ${{prompt_cost}} |
| Completion (Output) | {{completion_tokens}} | ${{completion_cost}} |
| **Total** | **{{total_tokens}}** | **${{total_cost}}** |

## Budget Status

- **Budget:** ${{budget_usd}}
- **Status:** {{status_icon}} **{{status_text}}**

{{#if_exceeded}}
> ⚠️ **Warning:** The total cost of ${{total_cost}} exceeds your budget of ${{budget_usd}}.
> **Recommendation:** Consider switching to a cheaper model or enabling prompt caching.
{{/if_exceeded}}