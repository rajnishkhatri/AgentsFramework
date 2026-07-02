---
name: sdd-lifecycle
type: skill
description: >-
  Route a production-grade, durable change through this repo's 10-stage
  spec-driven-development (SDD) lifecycle. Use whenever the user asks to "run
  the SDD lifecycle", "do this the spec-driven way", "what stage are we in",
  "kick off a production-grade change", or starts a non-trivial feature without
  naming a stage. This is the index/router: it names which sibling skill owns
  each stage (sdd-brainstorm → sdd-spec → sdd-replan → sdd-implement →
  sdd-converge) and which existing gates own review/test. Do NOT use for a
  single stage the user already named (invoke that sdd-* sibling directly), for
  trivial/throwaway edits (vibe-coding carve-out), or for reviewing a diff
  (code-review skill).
---

# SDD Lifecycle — the 10-stage router

Full methodology: `docs/research/agenticengineeringplaybook/sdd_lifecycle_runbook.md`.
Every stage is a **human↔agent micro-loop**: human initiates → agent does the
work → human gatekeeps → re-enter or advance. Never collapse this into "take
the spec and free-run."

## Which skill owns which stage

| Stage | Owner |
|---|---|
| 1 brainstorm | **sdd-brainstorm** |
| 2 plan · 3 task · 4 design | **sdd-spec** (specify → clarify → plan → tasks → analyze) |
| 5 replan / sprint board | **sdd-replan** (the loop-back hub) |
| 6 implementation | **sdd-implement** |
| 7 review | existing **code-review** skill (+ `security-review` for security seams) — do not re-author |
| 8 test | `make check` + `pytest tests/architecture/ -q` — the executable constitution |
| 9 issue fixes · 10 refine/sign-off | **sdd-converge** |

## The constitution rule

The constitution is **not** a new document: it is `AGENTS.md` (8 Architecture
Invariants + ✅/⚠️/🚫 Boundaries) enforced by `tests/architecture/`. Any
stage's "constitution check" = run those tests + walk the ⚠️ Ask-first list.
If a Spec Kit trial ever lands, its constitution must be *generated from*
these sources (runbook §2), never rewritten.

## When to skip the lifecycle

Trivial changes (typo, one-liner, throwaway spike) skip the runbook — but the
constitution stays on (`make check`, arch-tests, hooks). Anything touching an
ADR seam (`trust/models.py`, a new `orchestration/react_loop.py` node, a new
horizontal service, a new abstraction, a `pyproject.toml` dep) is by
definition non-trivial: full lifecycle + ADR (`docs/adr/0000-template.md`).

## Harness instrumentation (fires automatically today)

- `scripts/hooks/pre_bash_guard.py` (PreToolUse) · `post_edit_ruff.py`
  (PostToolUse) · `stop_adr_reminder.py` (Stop, ADR.1 advisory) ·
  `subagent_stop_review.py` (SubagentStop) · `sessionstart_reinject.py`
  (SessionStart, `source == "compact"` — re-injects the active subtree's nested
  `AGENTS.md` after compaction).
- Merge-time ratchets: `tests/architecture/test_adr_ratchet.py` (missing ADR),
  `test_no_test_weakening.py` (deleted/skipped tests).
- Comprehension gates G1/G3/G4/G7/G8: preamble + rotating wording in
  `docs/adr/GATES.md`; small decisions → `docs/adr/decisions.md`.
