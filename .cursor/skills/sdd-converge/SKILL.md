---
name: sdd-converge
type: skill
description: >-
  Run SDD Stages 9–10 (issue fixes + refine/sign-off) — classify every gap
  between what was built and what the spec required, spawn append-only fix
  tasks, and run the production sign-off checklist for THIS repository. Use
  whenever the user asks "did this converge", "what's missing vs the spec",
  "classify the gaps / findings", "is this acceptable / ready for
  production", or after review/test gates come back red. Bounded iteration:
  append Phase-N tasks, never rewrite history; a hard max-iterations ceiling
  forces human review. Do NOT use for finding defects in a diff (code-review
  skill runs Stage 7 first), for mid-flight re-prioritization before
  implementation "finished" (sdd-replan), or for writing the fixes themselves
  (sdd-implement executes the spawned tasks).
---

# SDD Stages 9–10 — Converge · Refine · Sign-off

> **Workspace binding.** Resolve each `{{placeholder}}` from the workspace binding:
> `.sdd/binding.toml` at the repo root, else the committed reference
> (`docs/skills/_sdd/binding.reference.toml` in this repo), else first-run
> auto-adapt (inspect ecosystem → propose → human-confirm → persist). See
> `docs/skills/_sdd/binding.schema.md`.

Runbook: `{{methodology_source}}`
§3 Stages 9–10 + §4 (the converge-loop mechanics).

## Stage 9 — classify, then spawn (never fix in place)

Classify every red gate / review finding / test failure:

| Class | Meaning | Route |
|---|---|---|
| `missing` | planned, not implemented | fix task → sdd-implement |
| `partial` | implemented, criterion unmet | fix task → sdd-implement |
| `contradicts` | conflicts with spec/plan | **sdd-replan** — spec problem, not code |
| `unrequested` | built but not in the spec (drift) | **sdd-replan** — de-scope or spec it |

**Append-only**: add a `## Phase N — Convergence` section to the change's task
list with each new task tagged `source-ref` + `gap-type`. Never rewrite
existing tasks or touch code in this stage. Deferred items go in the
iteration's plan doc (or, if the workspace keeps a tech-debt ledger, there).

## Stage 10 — the sign-off gate (all five, human-answered)

1. Converged: every EARS acceptance criterion has a passing test; no
   `missing`/`partial`/`contradicts` gaps remain.
2. `{{check_gate}}` green AND `{{test_gate}}` green — paste the
   actual output, not a summary.
3. Every ADR trigger hit during the change has a filed `{{adr_home}}` decision record (+
   `index.md`/`log.md` entries) — the workspace's merge-time decision-record ratchet
   ({{examples.hook_instrumentation}}) is the mechanical backstop.
4. Every comprehension gate that fired (G1/G3/G4/G7/G8/G9 — wordings in
   `{{gate_catalog}}`) was answered by the human in their own words.
5. {{examples.eval_capture_rule}}
6. **Blast-radius cleanup (scoped to THIS change).** Ask: *what did THIS change
   add that can now be deleted* — a scaffold, a dead branch, a defensive path the
   final shape no longer needs, a helper with one caller? Delete it before
   sign-off. Scope is the change's own diff, **not** a repo-wide delete-code pass
   (that is a separate initiative). *(This is where Runbook VI's A5 "delete code"
   lands for a change — folded into the A3 blast-radius sweep as
   "delete-what-this-change-added," not a standalone repo-wide pass.)*

**Bounded**: if convergence isn't reached within the agreed `max_iterations`,
stop and force human review — the loop never calls itself done. Not converged
→ re-enter sdd-implement with the Phase-N tasks; converged + green + signed →
production (commit only when the user asks).
