---
name: sdd-implement
type: skill
description: >-
  Run SDD Stage 6 (implementation) — execute an approved task list for THIS
  repository task-by-task with red/green TDD and per-task EARS verification.
  Use whenever the user says "implement the plan/tasks", "work through the
  task list", "start building it", or hands over an approved spec+tasks pair.
  Each task ends by checking its own pass/fail criteria; blocked tasks route
  to sdd-replan, never free-run around the plan. Do NOT use without an
  approved task list (sdd-spec first), for trivial one-liners (vibe-coding
  carve-out — hooks and gates still apply), for reviewing the finished
  diff (code-review skill), or for post-implementation gap classification
  (sdd-converge).
---

# SDD Stage 6 — Implementation (maker, bounded by the spec)

> **Workspace binding.** Resolve each `{{placeholder}}` from the workspace binding:
> `.sdd/binding.toml` at the repo root, else the committed reference
> (`docs/skills/_sdd/binding.reference.toml` in this repo), else first-run
> auto-adapt (inspect ecosystem → propose → human-confirm → persist). See
> `docs/skills/_sdd/binding.schema.md`.

Runbook: `{{methodology_source}}` §3
Stage 6. The discipline is already codified — this skill *applies* the root
`{{constitution}}` ✅ Always rules (red/green TDD, demand evidence, prompt/eval-capture
rules); it does not restate them. Read that section before starting.

## Per-task loop

1. Take the first unblocked task; respect dependency/parallelization markers.
2. **Red first**: write the test for the task's EARS criterion, run it,
   *paste the failing output*. Then implement; paste the passing output.
   (A test that never failed proves nothing — root `{{constitution}}`.)
3. Verify the task's own pass/fail criteria from the task list — iterate
   *bounded by the spec*, not free-running.
4. Checkpoint: `{{check_gate}}` after changes; `{{test_gate}}`
   must stay green (the executable constitution).
5. Blocked by something outside the plan → stop, route to **sdd-replan**.
   All tasks green → route to Stage 7 review (**code-review** skill, fresh
   thread).

**Backpressure while making** (Runbook VI §B3/§B4/§A2 in
`{{methodology_source}}`):
- **B3 — three strikes → re-plan.** Three failed attempts at the same task is the
  circuit-breaker: stop, route to **sdd-replan** (step 5), don't emit a fourth
  variation of the same broken code.
- **B4 — small diffs.** Keep each task's diff small enough to read every line; a
  task whose change balloons past that is a signal to split it, not to push harder.
- **A2 — defensive coding is not free.** When implementing, a `try/except` /
  `return None` / `or <default>` you add to make a test pass is the **G9** case —
  name the failure it catches or delete it; never fabricate a value to paper over
  an undecidable case.

## Harness instrumentation (fires automatically today)

The concrete hook set for this repo is `{{examples.hook_instrumentation}}`; the
conceptual roles below are what any binding must supply.

- Write-time: an advisory format/lint hook, never blocking an edit (HOOK-1).
- Command-time: a deterministic deny-list backstop before a shell command runs
  (HOOK-2).
- Turn-end: an advisory ADR.1 reminder if an ⚠️ Ask-first seam was touched with
  no new decision record under `{{adr_home}}`.
- Merge-time ratchets: a test-weakening ratchet (a deleted `def test_*` or an
  unjustified skip/xfail fails CI — waiver tokens
  `{{test_waiver_token}}`/`flaky-tracked:`/`env-gated:`) and a missing-decision-record
  ratchet (waiver `{{adr_waiver_token}} <reason>`). Don't fight the ratchets —
  justify or fix.
- After `/compact`: a post-compaction re-injection hook (SessionStart,
  `source == "compact"`) re-injects the active subtree's nested `{{constitution}}` —
  re-read it before continuing in that folder.
