# Token Budget Guard

A skill for the **Agent Harness** that monitors LLM token usage and enforces budgets.

## Features
- Analyze session history for token consumption.
- Generate cost reports in USD (per-session, per-model).
- Configurable budgets via `budget-config.json`, with an early-warning threshold (default 80%).
- Suggest cheaper models with savings computed from live prices (OpenRouter), plus prompt-caching tips.

## Installation
1. Place this skill in `.agents/skills/token-budget-guard/`.
2. Install the only dependency: `pip install httpx`.
3. Restart the Agent Harness TUI.
4. Use `@token-budget-guard` in the chat to load the skill.

## Usage
Ask the agent:
- "How much have I spent on this session?"
- "Am I exceeding my $5 budget?"
- "Which model is cheaper than GPT-5?"

## Configuration (optional)
Create `.harness/token-budget-guard/budget-config.json` to set a default budget, an alert threshold, and per-model budgets. See `assets/budget-config.schema.json`.

## Limitations
- Prices are fetched live from OpenRouter and cached for 1 day; non-OpenRouter providers may differ (see `references/pricing-sources.md`).
- Only analyzes sessions stored in `.harness/sessions/`.
- Does not enforce real-time limits (only post-hoc analysis with threshold alerts).

## License
MIT
