# Root — Reviewer Enforcement Map (fallback)

> **The universal fallback enforcement map.** The unified reviewer
> (`prompts/codeReviewer/v3/`) loads this for any changed path whose owning
> folder has no nearer `REVIEW.md`. Per-folder maps (`*/REVIEW.md`) override it.
> Cites rule IDs from the root [`AGENTS.md`](AGENTS.md); never restates prose. A
> cite that names a rule absent from `AGENTS.md` is a lint failure
> (`tests/code_reviewer/test_review_md_cites.py`).

## Always-on (every routed file)

| rule_id | source | detection | severity | reviewer dimension |
|---|---|---|---|---|
| Invariant #1 (dependencies flow downward only) | AGENTS.md §Architecture Invariants | AST (`check_dependency_rules`) | critical | D1 |
| Invariant #6 (orchestration nodes are thin wrappers) | AGENTS.md §Architecture Invariants | LLM | warning | D5 |
| `make check` clean (lint/format/typecheck/test) | AGENTS.md §Key Commands | LLM | note | D3 |

## ADR ratchet (Track C, made executable — WI-5)

| rule_id | source | detection | severity | reviewer dimension |
|---|---|---|---|---|
| ADR.1 (`⚠️ Ask first` diff with no new `docs/adr/` file) | AGENTS.md §Decision records | AST (`detect_adr1_missing` file-list scan) | warning | D2 |
| G1 (new-abstraction gate states what it buys) | AGENTS.md §Decision records | LLM | warning | D2 |
| G8 (test-mass-rewrite gate justifies weakened assertions) | AGENTS.md §Decision records | LLM | warning | D3 |

> **ADR.1 detection (mechanical).** An `⚠️ Ask first` trigger is detectable from
> the changed file list: a new `pyproject.toml` dependency, a `trust/models.py`
> change, a new node in `orchestration/react_loop.py`, or a new horizontal
> service. If any is present and **no** new file under `docs/adr/` is in the same
> diff, flag ADR.1. This makes the Track C convention reviewer-checkable.
