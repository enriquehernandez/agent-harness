# Changelog

## [1.0.1] - 2026-11-17
### Fixed
- `generate_report.py`: cost breakdown now uses live prices from `fetch_pricing.py` instead of hardcoded GPT-4o rates (previously wrong for any other model).
- `fetch_pricing.py`: on API failure it now falls back to the expired cache before using default rates, matching the documented behavior.
- `compare_costs.py`: rewritten to compare two sessions directly via `analyze_session` (previously it tried to parse markdown reports as JSON and was unusable).
- `manifest.json`: added the missing `httpx` dependency.
- `SKILL.md`: documented the `--model` and `--budget` flags and the budget config file.
- `README.md`: removed reference to the non-existent `scripts/pricing.py`.
- `CHANGELOG.md`: corrected script names from the initial draft.

### Changed
- `suggest_alternatives.py`: savings percentages are now computed from live prices instead of hardcoded values; updated model recommendations.
- `generate_report.py`: added optional threshold alert ("Approaching budget") driven by `budget-config.json`.
- Default model updated from `openai/gpt-4o` to `openai/gpt-5`.

## [1.0.0] - 2026-11-16
### Added
- Initial release of Token Budget Guard.
- `analyze_session.py`: Analyzes token usage from session files.
- `generate_report.py`: Generates markdown budget reports.
- `suggest_alternatives.py`: Suggests cheaper model alternatives.
- `fetch_pricing.py`: Fetches and caches prices from OpenRouter.
- `SKILL.md`: Instructions for the agent.
- `README.md`, `LICENSE.md`, `manifest.json`.
