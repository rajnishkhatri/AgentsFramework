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
  curation (agentsframework-okf-curator), or an ADR alone (copy the ADR
  template directly).
---

# SDD Stages 2–4 — Specify · Clarify · Plan · Tasks · Analyze

> **Workspace binding.** Resolve each `{{placeholder}}` from the workspace binding:
> `.sdd/binding.toml` at the repo root, else the committed reference
> (`docs/skills/_sdd/binding.reference.toml` in this repo), else first-run
> auto-adapt (inspect ecosystem → propose → human-confirm → persist). See
> `docs/skills/_sdd/binding.schema.md`.

Runbook: `{{methodology_source}}` §3
Stages 2–4. Two hard gates: spec → (human) → plan → (human) → tasks.

## Stage 2 — Specify + clarify + plan

- **Specify:** copy the spec template in {{spec_home}} → `{{spec_home}}<name>.spec.md`.
  Acceptance criteria in EARS notation (Ubiquitous / WHEN / WHILE / IF-THEN /
  WHERE) — each collapses to one testable claim. Failure paths FIRST.
- **Clarify:** structured ambiguity pass *before* planning — scan functional
  scope, data model, edge cases, NFRs; ask ≤5 targeted questions, one at a
  time, each with a recommended answer. The first draft is never final.
- **Plan:** architecture, file-level touchpoints, migration steps — derived
  from the clarified spec AND the constitution (`{{constitution}}` 8 invariants). A
  plan that needs an ⚠️ Ask-first item raises an ADR
  (`{{adr_template}}` + index/log); spec = the *what*, ADR = the *why*.

**Slop-reduction ownership at spec time** (Runbook VI §A1/§A7 in
`{{methodology_source}}`):
this is the stage that owns **A1 — spec the simplest thing that satisfies the
criteria** (the plan proposes the least machinery, not the most impressive) and
**A7 — spec before code** (the acceptance criteria exist before any implementation
here by construction). A plan that introduces a new abstraction is the **G1** case
— state what it buys and the simpler thing rejected, in the plan or its ADR.

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
  — use the workspace's broad read-only exploration tool ({{breadth_read_tool}}) for breadth); confirm every new dependency is
  in `pyproject.toml` or flagged as an ADR trigger.
- Baseline: `{{check_gate}}` + `{{test_gate}}` must be green
  *before* implementation starts.

## Harness instrumentation (today)

The workspace's turn-end decision-record reminder / merge-time ratchet ({{examples.hook_instrumentation}})
fires on Stop if an ADR seam was touched with no new
`{{adr_home}}*`; the merge-time ratchet is the merge-time gate
(waiver: `{{adr_waiver_token}} <reason>` in a commit message). Verifier-checkable criteria
can reuse the workspace's verifier/assertion helpers, if any. Advance → **sdd-implement**.
