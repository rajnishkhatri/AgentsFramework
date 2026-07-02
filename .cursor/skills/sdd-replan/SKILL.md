---
name: sdd-replan
type: skill
description: >-
  Run SDD Stage 5 (replan / sprint board) — the mid-flight loop-back hub for a
  change already in progress in THIS repository. Use whenever the user says
  "replan", "reprioritize", "this task is blocked", "scope changed", "update
  the sprint board / task list", or a review/test finding invalidates a
  planned task. Routes the fallout: scope change → back to the spec
  (sdd-spec), re-ordering → tasks only, re-prioritization → straight back to
  implementation (sdd-implement). Do NOT use for planning a NEW change from
  scratch (sdd-spec, or the harness's built-in plan mode), for gap
  classification after implementation "finished" (sdd-converge), or for pure
  status reporting.
---

# SDD Stage 5 — Replan / sprint board (the loop-back hub)

Runbook: `docs/research/agenticengineeringplaybook/sdd_lifecycle_runbook.md` §3
Stage 5 — the deliberate gap: Spec Kit has no command for mid-flight
replanning; this repo treats it as first-class.

## Triggers (initiation)

(a) a blocked task discovered during implementation · (b) a human scope
change · (c) a review finding that invalidates a task · (d) the Stage-10
refine gate sending the loop back.

## Agent work

1. Read the current externalized state — the change's `tasks.md` /
   `docs/plan/<name>.plan.md`. **State lives in the plan doc, not in-context
   only**: update the doc so the replan survives `/compact` and session ends.
2. Propose the re-prioritization: which tasks stay / slip / split / drop —
   with the reason per task.
3. **If scope changed, propagate backwards first**: update the spec before
   touching code (the spec is the source of truth; code follows).

## Human gate + routing

The human approves the replan (this is the steering nudge). Then route:

- Scope/spec changed → **sdd-spec** (Stage 2).
- Only ordering/decomposition changed → rewrite the task list (Stage 3 rules).
- Only priorities changed → **sdd-implement** (Stage 6) with the new order.

## Harness instrumentation (today)

`sessionstart_reinject.py` (SessionStart, `source == "compact"`) re-injects the
active subtree's nested `AGENTS.md` after a compaction, so the replan doesn't silently lose the folder
rules; the plan doc itself is the durable state. Small non-obvious replan
decisions → 2–4 lines in `docs/adr/decisions.md`.
