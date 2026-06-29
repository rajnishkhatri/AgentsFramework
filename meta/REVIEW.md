# meta/ — Reviewer Enforcement Map

> Thin enforcement map for the unified reviewer. Cites rule IDs from
> [`meta/AGENTS.md`](AGENTS.md) and root [`AGENTS.md`](../AGENTS.md); never
> restates prose. AST findings run first and win.

| rule_id | source | detection | severity | reviewer dimension |
|---|---|---|---|---|
| AP-4 (no upward governance calls — meta ⊄ orchestration) | meta/AGENTS.md §AP-4 | AST (`check_dependency_rules`) | critical | D1 |
| AP-6 (no fabricated metrics — `None` not `0.0`) | meta/AGENTS.md §Eval conventions | LLM | warning | D5 |
| Judge drift = Cohen's κ (drift.py L2) | meta/AGENTS.md §Eval conventions | LLM | note | D3 |
| Judge validation = TPR/TNR + Rogan-Gladen | meta/AGENTS.md §Eval conventions | LLM | note | D3 |
| TAP-4 (failure paths first) | meta/AGENTS.md §L4 testing rules | AST (`detect_failure_path_ratio` failure-test ratio) | warning | D3 |
