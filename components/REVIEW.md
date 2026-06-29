# components/ — Reviewer Enforcement Map

> Thin enforcement map for the unified reviewer. Cites rule IDs from
> [`components/AGENTS.md`](AGENTS.md) and root [`AGENTS.md`](../AGENTS.md); never
> restates prose. AST findings run first and win.

| rule_id | source | detection | severity | reviewer dimension |
|---|---|---|---|---|
| Invariant #3 (components framework-agnostic) | components/AGENTS.md §What a component is | AST (`check_dependency_rules` framework) | critical | D1 |
| Invariant #5 (no peer imports between components) | components/AGENTS.md §What a component is | AST (`detect_anti_patterns` AP-2) | critical | D1 |
| V1 (abstract interface + template methods) | components/AGENTS.md §Design patterns | LLM | note | D2 |
| V2 (router = deterministic heuristics + advisory .j2) | components/AGENTS.md §Design patterns | LLM | warning | D2 |
| V6 (Pydantic models for non-trivial outputs) | components/AGENTS.md §Design patterns | LLM | warning | D2 |
| TAP-3 (determinism theater) | components/AGENTS.md §L3 testing rules | LLM | warning | D3 |
| Test import rule (`tests/components/` not orchestration) | components/AGENTS.md §L3 testing rules | AST (`check_dependency_rules`) | warning | D1 |
