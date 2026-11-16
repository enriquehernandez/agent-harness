# Token Budget Guard

A skill for the **Agent Harness** that monitors LLM token usage and enforces budgets.

## Features
- Analyze session history for token consumption.
- Generate cost reports in USD.
- Suggest cheaper models or prompt caching strategies.

## Installation
1. Place this skill in `.agents/skills/token-budget-guard/`.
2. Restart the Agent Harness TUI.
3. Use `@token-budget-guard` in the chat to load the skill.

## Usage
Ask the agent:
- "How much have I spent on this session?"
- "Am I exceeding my $5 budget?"
- "Which model is cheaper than GPT-4o?"

## Limitations
- Pricing is hardcoded in `scripts/pricing.py`. Update it for custom rates.
- Only analyzes sessions stored in `.harness/sessions/`.
- Does not enforce real-time limits (only post-hoc analysis).

## License
MIT