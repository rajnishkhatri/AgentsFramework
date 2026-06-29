# services/ — Reviewer Enforcement Map

> Thin enforcement map for the unified reviewer. Cites rule IDs from
> [`services/AGENTS.md`](AGENTS.md) and root [`AGENTS.md`](../AGENTS.md); never
> restates prose. AST findings (from `utils/code_analysis.py`) run first and win.

| rule_id | source | detection | severity | reviewer dimension |
|---|---|---|---|---|
| Invariant #4 (services framework-agnostic) | services/AGENTS.md §What a service is | AST (`check_dependency_rules` framework) | critical | D1 |
| Invariant #7 (services must not import components) | root AGENTS.md | AST (`check_dependency_rules`) | critical | D1 |
| AP-1 (trust types inside a service) | services/AGENTS.md §Anti-patterns | LLM | warning | D4 |
| AP-2 (horizontal-to-horizontal coupling) | services/AGENTS.md §Anti-patterns | LLM | warning | D5 |
| AP-3 (hardcoded prompts) | services/AGENTS.md §Anti-patterns | AST (`detect_anti_patterns` AP-3) | warning | D2 |
| H1 (prompts are .j2 via PromptService) | services/AGENTS.md §Design patterns | LLM | warning | D2 |
| H2 (model tiers from llm_config) | services/AGENTS.md §Design patterns | LLM | warning | D2 |
| H4 (per-concern log file) | services/AGENTS.md §Design patterns | LLM | note | D2 |
| H5 (record every LLM call via eval_capture) | services/AGENTS.md §Design patterns | LLM | warning | D2 |
| TAP-2 (mock addiction, >3 mocks/test) | services/AGENTS.md §L2 testing rules | AST (`detect_mock_abuse` mock-count) | warning | D3 |
| TAP-4 (failure paths first) | services/AGENTS.md §L2 testing rules | AST (`detect_failure_path_ratio` failure-test ratio) | warning | D3 |
| Live LLM in CI | services/AGENTS.md §L2 testing rules | LLM | warning | D3 |
