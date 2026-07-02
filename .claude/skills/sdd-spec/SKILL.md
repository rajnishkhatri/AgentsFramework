---
name: sdd-spec
type: skill
description: >-
  Run SDD Stages 2–4 for a chosen direction in THIS repository: write the EARS
  spec, run the clarify pass, derive the plan and task list, then cross-check
  spec↔plan↔tasks against the constitution before any code. Use whenever the
  user says "write a spec", "spec this out", "EARS acceptance criteria", "plan
  this feature", "break this into tasks", or hands over a brainstormed
  direction. The keystone rule: never skip from spec to code. Do NOT use for
  ideation with no chosen direction (sdd-brainstorm), mid-flight task
  reshuffling (sdd-replan), writing the code (sdd-implement), post-hoc docs
  curation (agentsframework-okf-curator), or an ADR alone (copy
  docs/adr/0000-template.md directly).
---

# SDD Stages 2–4 — Specify · Clarify · Plan · Tasks · Analyze

Runbook: `docs/research/agenticengineeringplaybook/sdd_lifecycle_runbook.md` §3
Stages 2–4. Two hard gates: spec → (human) → plan → (human) → tasks.

## Stage 2 — Specify + clarify + plan

- **Specify:** copy `docs/plan/_spec_template.md` → `docs/plan/<name>.spec.md`.
  Acceptance criteria in EARS notation (Ubiquitous / WHEN / WHILE / IF-THEN /
  WHERE) — each collapses to one testable claim. Failure paths FIRST.
- **Clarify:** structured ambiguity pass *before* planning — scan functional
  scope, data model, edge cases, NFRs; ask ≤5 targeted questions, one at a
  time, each with a recommended answer. The first draft is never final.
- **Plan:** architecture, file-level touchpoints, migration steps — derived
  from the clarified spec AND the constitution (`AGENTS.md` 8 invariants). A
  plan that needs an ⚠️ Ask-first item raises an ADR
  (`docs/adr/0000-template.md` + index/log); spec = the *what*, ADR = the *why*.

## Stage 3 — Checklist + tasks

- Checklist = "unit tests for English": is every criterion measurable? Flag
  unmeasurable ones back to the spec.
- Decompose into atomic tasks: file-level specificity, dependency +
  parallelization markers, explicit pass/fail verification mapped 1:1 from the
  EARS criteria.

## Stage 4 — Analyze (the last cheap correction point)

- Cross-artifact read-only check: spec ↔ plan ↔ tasks ↔ constitution.
  CRITICAL = invariant violations, zero-coverage requirements, references to
  non-existent files/APIs.
- **Grounding pass:** probe every file path/API the plan references (glob/grep
  — use the `explore` subagent for breadth); confirm every new dependency is
  in `pyproject.toml` or flagged as an ADR trigger.
- Baseline: `make check` + `pytest tests/architecture/ -q` must be green
  *before* implementation starts.

## Harness instrumentation (today)

`stop_adr_reminder.py` fires on Stop if an ADR seam was touched with no new
`docs/adr/*`; `tests/architecture/test_adr_ratchet.py` is the merge-time gate
(waiver: `ADR-OK: <reason>` in a commit message). Verifier-checkable criteria
can reuse `components/answer_verifiers.py`. Advance → **sdd-implement**.
