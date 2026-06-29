# orchestration/ — Reviewer Enforcement Map

> Thin enforcement map for the unified reviewer. Cites rule IDs from
> [`orchestration/AGENTS.md`](AGENTS.md) and root [`AGENTS.md`](../AGENTS.md);
> never restates prose. AST findings run first and win.

| rule_id | source | detection | severity | reviewer dimension |
|---|---|---|---|---|
| Invariant #8 (orchestration is the only langgraph importer) | root AGENTS.md | LLM | note | D1 |
| AP-5 (nodes are thin wrappers, ≤10–15 lines) | orchestration/AGENTS.md §AP-5 | LLM | warning | D5 |
| New graph node (⚠️ Ask first → ADR) | orchestration/AGENTS.md §Adding a graph node | LLM | warning | D2 |
| Config split (thresholds in routing_config, prose in .j2) | orchestration/AGENTS.md §Config rule | LLM | note | D2 |
| Live LLM in CI | orchestration/AGENTS.md §L4 testing rules | LLM | warning | D3 |
