# scripts/hooks/ — Reviewer Enforcement Map

> Thin enforcement map for the unified reviewer. Cites rule IDs from
> [`scripts/hooks/AGENTS.md`](AGENTS.md); never restates prose. These encode the
> Track A invariants as reviewer-checkable rules (WI-5).

| rule_id | source | detection | severity | reviewer dimension |
|---|---|---|---|---|
| HOOK-1 (PostToolUse never blocks the edit) | scripts/hooks/AGENTS.md §HOOK-1 | LLM | critical | D5 |
| HOOK-2 (PreToolUse safety-only and thin) | scripts/hooks/AGENTS.md §HOOK-2 | LLM | warning | D5 |
| HOOK-3 (fail safe on malformed input) | scripts/hooks/AGENTS.md §HOOK-3 | LLM | warning | D5 |
