---
name: sdd-lifecycle
type: skill
description: >-
  Route a production-grade, durable change through your workspace's 10-stage
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

> **Workspace binding.** This skill is portable. Resolve each `{{placeholder}}`
> from the workspace binding: `.sdd/binding.toml` at the repo root, else the
> repo's committed reference (this repo: `docs/skills/_sdd/binding.reference.toml`),
> else **first-run auto-adapt** — inspect the ecosystem, propose values, get
> human confirmation, persist to `.sdd/binding.toml` (never run a guessed gate
> command silently). See `docs/skills/_sdd/binding.schema.md`.

Full methodology: `{{methodology_source}}`.
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
| 8 test | `{{check_gate}}` + `{{test_gate}}` — the executable constitution |
| 9 issue fixes · 10 refine/sign-off | **sdd-converge** |

## The constitution rule

The constitution is **not** a new document: it is `{{constitution}}` (the
workspace's binding engineering rules + boundaries) enforced by the
`{{test_gate}}` suite. Any stage's "constitution check" = run those tests + walk
the ⚠️ Ask-first list. If a generated-constitution trial ever lands, it must be
*generated from* these sources, never rewritten.

## When to skip the lifecycle

Trivial changes (typo, one-liner, throwaway spike) skip the runbook — but the
constitution stays on (`{{check_gate}}`, arch-tests, hooks). Anything touching a
decision-record seam (a shared-kernel type change, a new framework node, a new
horizontal service, a new abstraction, a new dependency) is by definition
non-trivial: full lifecycle + a decision record (`{{adr_template}}`).

## Harness instrumentation

Where the workspace wires editor/agent hooks, they run here (write-time
format/lint, command-time deny-list backstop, turn-end decision-record
reminder). This repo's reference set: `{{examples.hook_instrumentation}}`.

- Merge-time ratchets (if present): a missing-decision-record gate and a
  test-weakening gate. Don't fight the ratchets — justify (`{{adr_waiver_token}}`
  / `{{test_waiver_token}}` in the commit message) or fix.
- Comprehension gates: the workspace's gate catalog (`{{gate_catalog}}`); small
  decisions → `{{decision_log}}`.
