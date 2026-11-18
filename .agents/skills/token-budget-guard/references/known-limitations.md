# Known Limitations

This skill is a **post-hoc analysis tool**. It is designed to be transparent about what it cannot do.

## 1. No Real-Time Enforcement
The budget guard analyzes sessions *after* the LLM calls have been made. It cannot stop an LLM call mid-generation if it exceeds the budget. It acts as an auditor, not a firewall.

## 2. Dependent on Session JSONs
The analysis relies on the `usage_total` field being present and accurate in `.harness/sessions/<id>.json`. If a provider does not return usage data (e.g., some free tiers), the cost will be reported as `$0.00`.

## 3. OpenRouter Bias
The automatic pricing fetch is optimized for OpenRouter. While OpenRouter proxies many models, the prices might not exactly match direct provider prices (e.g., Azure OpenAI). Use the manual override if exact precision is required.

## 4. Token Estimation vs. Real Tokens
If the `usage_total` is missing, the harness might fall back to estimating tokens by character count (`len(text) // 4`). These estimates are approximate and may under-report or over-report costs by up to 20%.