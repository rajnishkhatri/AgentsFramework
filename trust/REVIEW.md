# trust/ — Reviewer Enforcement Map

> **Thin enforcement map, not a rule book.** This file tells the unified
> reviewer (`prompts/codeReviewer/v3/`) *what to flag here and how*. It **cites**
> rule IDs whose content lives in [`trust/AGENTS.md`](AGENTS.md) and the root
> [`AGENTS.md`](../AGENTS.md) — it never restates the rule prose. If a cite below
> does not resolve to a heading/ID in the sibling `AGENTS.md`, that is a lint
> failure (see `tests/code_reviewer/test_review_md_cites.py`).
>
> Detection column: **AST** = a deterministic validator in
> `utils/code_analysis.py` runs first and its finding takes precedence; **LLM**
> = the reviewer judges it (not gate-grade until the judge is validated, WI-8).

| rule_id | source | detection | severity | reviewer dimension |
|---|---|---|---|---|
| Invariant #2 (trust zero outward deps) | root AGENTS.md | AST (`check_dependency_rules`) | critical | D1 |
| Pure — no I/O/storage/network/logging | trust/AGENTS.md §What belongs here | AST (`check_trust_purity` → TRUST_PURITY.io_import) | critical | D4 |
| AP-1 (trust types inside a service) | trust/AGENTS.md §What belongs here | LLM | warning | D4 |
| G4 (complex-algorithm comprehension gate) | trust/AGENTS.md §G4 | LLM | warning | D4 |
| Signed/unsigned field change (re-sign trigger) | trust/AGENTS.md §Signed vs unsigned fields | LLM | warning | D4 |
| TAP-1 (tautological tests) | trust/AGENTS.md §L1 testing rules | LLM | warning | D3 |
| TAP-4 (gap blindness / rejection-first) | trust/AGENTS.md §L1 testing rules | AST (`detect_failure_path_ratio` failure-test ratio) | warning | D3 |
| Test import rule (`tests/trust/` → trust only) | trust/AGENTS.md §L1 testing rules | AST (`check_dependency_rules`) | warning | D1 |
