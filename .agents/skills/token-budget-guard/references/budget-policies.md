# Budget Policies

## Alerts
- **Warning**: 80% of budget consumed.
- **Critical**: 100% of budget consumed.

## Auto-Suggestions
If budget is exceeded, suggest switching to a cheaper model. Use the following hierarchy:
1. Try a cheaper variant of the same provider (e.g., GPT-4o → GPT-4o-mini).
2. Try a faster, cheaper provider (e.g., Gemini Flash).
3. Try a free model (e.g., Nemotron).

## Known Limitations
- The skill does not enforce limits in real-time. It is a post-hoc analysis tool.