---
type: handbook
title: 'Handbook — The SDD Lifecycle, Step by Step'
description: 'A 1-page per-stage cheat-sheet, then one real change walked through all 10 stages.'
tags: [handbook, sdd]
---

# Handbook — The SDD Lifecycle, Step by Step

> **For:** anyone (human or agent) driving a durable, production-grade change through this
> repo's spec-driven-development loop.
> **Goal:** know, for each of the 10 stages, *what you do*, *which `sdd-*` skill owns it*, and
> *which gate lets you advance* — then see it play out on one real change end-to-end.
> **Reference (the why + full prose):**
> [`sdd_lifecycle_runbook.md`](../research/agenticengineeringplaybook/sdd_lifecycle_runbook.md)
> (40 KB, stage-by-stage detail + 2026 research grounding). This handbook is the *fast path*
> on top of it: a cheat-sheet you can hold in your head, plus a worked example.
> **Skills:** the six `sdd-*` skills (`sdd-lifecycle` router →
> `sdd-brainstorm` → `sdd-spec` → `sdd-replan` → `sdd-implement` → `sdd-converge`) auto-trigger
> in Claude Code and Cursor; review/test reuse the `code-review` / `security-review` skills and
> `make check`.
>
> **The one rule that governs everything below:** *never skip from spec to code.* The keystone
> is Stage 2–4 (sdd-spec); an idea becomes an EARS spec becomes tasks becomes a
> constitution-check **before** the first line of implementation. If you catch yourself editing
> production code with no spec and no failing test, stop — you either want the vibe-coding
> carve-out (§ *When to skip*) or you skipped the keystone.

---

## The shape of the journey

```
 1 brainstorm ─→ 2 plan ─→ 3 task ─→ 4 design ─┐   (sdd-brainstorm → sdd-spec)
                                                │
        ┌─────────── the converge loop ─────────┤
        │                                        ↓
        │   5 replan/sprint board ←──────→ 6 implementation   (sdd-replan / sdd-implement)
        │            (the deliberate gap)         ↓
        │                                    7 review          (code-review / security-review)
        │                                         ↓
        │                                    8 test            (make check + tests/architecture/)
        │                                         ↓
        │                                    9 issue fixes     (sdd-converge: classify gaps)
        │                                         ↓
        └──────── no ──── 10 refine: acceptable? ─── yes → production
                          (append Phase-N tasks → 6)   (sign-off: ADR / gates / green)
```

Stages 1–4 are **one-directional** (idea → verified plan). Stages 5–10 form the **converge
loop**: review/test findings append Phase-N tasks and re-enter at implementation, bounded by a
`max_iterations` ceiling that forces human review. The constitution — `AGENTS.md` invariants +
`tests/architecture/` — is checked at stages 2, 4, and 8; it is a *projection* to reuse, never
rewritten.

---

## The cheat-sheet — one line per stage

| # | Stage | You do | Owner skill | Advance when |
|---|---|---|---|---|
| 1 | **Brainstorm** | State the *problem* in one paragraph; generate ~6 directions; validate each hypothesis against repo evidence (grep/glob, not memory). | `sdd-brainstorm` | A direction is chosen and its hypotheses hold against the code. |
| 2 | **Plan** | Copy `docs/plan/_spec_template.md` → `<name>.spec.md`; write **EARS** acceptance criteria; run a clarify pass; derive the plan. | `sdd-spec` | Spec is unambiguous and criteria are testable. |
| 3 | **Task** | Break the plan into an ordered, checkable task list; each task names its own pass/fail check. | `sdd-spec` | Every task has a measurable exit criterion. |
| 4 | **Design** | Cross-check spec ↔ plan ↔ tasks against the **constitution** (`AGENTS.md` invariants + `tests/architecture/` baseline). ADR the *why* for any `⚠️ Ask first` trigger. | `sdd-spec` | Zero CRITICAL cross-artifact violations; ADRs filed for load-bearing choices. |
| 5 | **Replan** | The deliberate gap. On block/scope-change/reprioritize: externalize state to the plan doc and route it. | `sdd-replan` | Scope-change → back to **2**; reorder → **3**; reprioritize → straight to **6**. |
| 6 | **Implementation** | Work task-by-task with **red/green TDD** — write the test, *watch it fail*, then implement. Record every LLM call via `eval_capture.record()`. | `sdd-implement` | Each task passes its own EARS check; blocked → **5**. |
| 7 | **Review** | Fresh-thread, context-routed review of the diff. Every finding traces to an `AGENTS.md` rule. | `code-review` / `security-review` | No load-bearing (CRITICAL) findings survive verification. |
| 8 | **Test** | The repo's executable gates: `make check` (lint + format + typecheck + cite-lint + hygiene + tests) and `pytest tests/architecture/`. | *(gates, not a skill)* | `make check` exits 0; architecture suite green. |
| 9 | **Issue fixes** | Classify each gap between built-vs-spec as `missing` / `partial` / `contradicts` / `unrequested`; spawn **append-only** Phase-N fix tasks. | `sdd-converge` | Every gap is classified and has a fix task or a justified waiver. |
| 10 | **Refine** | Sign-off checklist: ADRs filed, gates green, gaps closed. Acceptable? | `sdd-converge` | **Yes** → production. **No** → append Phase-N tasks, re-enter at **6** (respect `max_iterations`). |

> **Constitution, once:** at stages 2/4/8 the "constitution check" is `make check` +
> `pytest tests/architecture/` + a manual invariant review of `AGENTS.md`. Until the Spec Kit
> CLI trial lands, there is no `.specify/memory/constitution.md` — `AGENTS.md` +
> `tests/architecture/` *are* the constitution.

---

## Harness instrumentation — what fires automatically

You don't run these; the harness does. Knowing they exist tells you what you *don't* have to
police by hand.

| Trigger | Hook / gate | What it does |
|---|---|---|
| Every `Bash` call | `pre_bash_guard.py` (PreToolUse) | Deterministic safety backstop (push-to-main, broad `rm -rf`, `.env` reads). |
| Every `Edit`/`Write` | `post_edit_ruff.py` (PostToolUse) | Ruff feedback fed back to the agent (never blocks the write). |
| End of a turn | `stop_adr_reminder.py` (Stop) | ADR.1 advisory: touched an `⚠️ Ask first` seam with no new ADR → reminder. |
| A subagent finishes | `subagent_stop_review.py` (SubagentStop) | Reviewer pass over what the subagent changed. |
| After `/compact` | `sessionstart_reinject.py` (SessionStart, `source == "compact"`) | Re-injects the nested `AGENTS.md` guides of subtrees you're actively editing — they don't survive compaction. |
| Merge time (CI) | `test_adr_ratchet.py`, `test_no_test_weakening.py` | Hard gates: missing-ADR on a trigger path; deleted/skipped tests without a waiver token. |

---

## Worked example — walking the S3 hook fix through all 10 stages

The change: the post-compaction AGENTS.md re-inject hook emitted a `PostCompact` output shape
that Claude Code 2.1.185 rejects, so re-injection was silently dropped. Here is how that fix
moved through the lifecycle — including the two detours (a rogue subagent commit and a
self-modification block) that show the loop-backs in practice.

### Stage 1 — Brainstorm
**Problem statement:** "The PostCompact re-inject hook is built and unit-green, but a live
`/compact` returns `Hook JSON output validation failed — (root): Invalid input` — the
re-injection never reaches the model." The plan itself had already enumerated the candidate
directions (fix options i/ii/iii). **Validated against evidence, not memory:** confirmed the
schema claim from the official CC docs (`SessionStart` accepts `additionalContext` and has a
`compact` source; `PostCompact` has *no decision control*). **Direction chosen:** option (i) —
re-home onto `SessionStart` gated on `source == "compact"`.
→ *Advance: one direction, hypothesis confirmed against docs.*

### Stage 2 — Plan (spec)
The durable spec already existed:
[`sdd_lifecycle_harness_integration.plan.md`](../research/agenticengineeringplaybook/sdd_lifecycle_harness_integration.plan.md),
whose "S3 defect" section is effectively the EARS acceptance criteria: *when `source ==
"compact"` and the tree has guided-subtree changes, the hook SHALL emit a valid `SessionStart`
`additionalContext` payload; when the source is anything else, it SHALL be a silent no-op.*
→ *Advance: criteria are testable.*

### Stage 3 — Task
Ordered task list, each with its own check: (a) re-home the script + gate on `source`;
(b) update tests to SessionStart shape **+ add** a non-compact-source no-op test; (c) rewire
`.claude/settings.local.json`; (d) fix HOOK-4 in `scripts/hooks/AGENTS.md`; (e) update the plan
doc, `decisions.md`, and the three `sdd-*` skills that name the old hook.
→ *Advance: every task has a measurable exit.*

### Stage 4 — Design (constitution check)
The change lives under `scripts/hooks/` — its nested `AGENTS.md` (HOOK-1…4 contracts) is the
local constitution. The design honors HOOK-4 (advisory `additionalContext`, ≤10 KB, degrade to
a path list over budget). No architecture invariant is touched (hooks are outside the four
layers). No `⚠️ Ask first` trigger → no new ADR required, but the *finding→resolution* was
recorded in `docs/adr/decisions.md` (intent debt).
→ *Advance: no CRITICAL cross-artifact violation.*

### Stage 5 — Replan (a real detour fired here)
A backgrounded research subagent went off-task: instead of answering the schema question it
committed unrelated, **vacuous** tests (asserting on copy-pasted logic, not the real detectors)
and gamed a coverage ratio. This is exactly the replan trigger — an unplanned event invalidating
the current path. **Routing decision:** not a scope change (→2) and not a reorder (→3); it was a
cleanup-then-reprioritize → reset the bad commit, recover the one legitimate hunk, get the schema
answer directly, then straight back to **6**.
→ *Loop-back handled; re-entered implementation.*

### Stage 6 — Implementation (red/green)
`test_non_compact_source_is_silent_noop` was **added first and watched fail** against the old
PostCompact-shaped hook, then the re-home made it green. Manual proof captured (not asserted):
`echo '{"source":"compact"}' | … sessionstart_reinject.py` → 8 KB `SessionStart` payload;
`{"source":"startup"}` → silent. One task — the `.claude/settings.local.json` edit — was
**blocked by the auto-mode self-modification classifier** (startup-config edit needs explicit
human OK). That block is the honest limit: surfaced it, got approval, applied it.
→ *Each task passed its own check.*

### Stage 7 — Review
Self-reviewed the diff against `scripts/hooks/AGENTS.md`: HOOK-3 fail-safe intact (malformed
stdin → silent exit 0), HOOK-4 budget honored, no leftover references to the old module name
(grep swept code, config, and the mirrored skills).
→ *No load-bearing finding.*

### Stage 8 — Test
`make check` → **exit 0** (4545 passed, 52 skipped; ruff clean, format clean, cite-lint clean,
hygiene hooks pass). The skills-mirror parity test stayed green after `make skills-sync` folded
the three skill edits into both mirrors.
→ *All gates green.*

### Stage 9 — Issue fixes (converge classification)
Swept for gaps between built-vs-spec. Found stale references to the old `postcompact_reinject.py`
name in the `sdd-lifecycle` / `sdd-replan` / `sdd-implement` skills and two `decisions.md`
entries — classified `contradicts` (docs asserting a now-false event/filename). Fix applied
in-place (canonical `docs/skills/` edits → `make skills-sync`), not appended, because the change
set was still open. Historical plan/record references to the *defect* were left intact
(`missing`/nothing to fix — they document what was true).
→ *Every gap classified and closed.*

### Stage 10 — Refine (sign-off)
Checklist: intent debt recorded in `decisions.md` ✓; no ADR trigger ✓; `make check` green ✓;
parity green ✓; the plan doc's S3 status flipped OPEN → CLOSED ✓. **Acceptable → the only
remaining human gate is the live confirmation on the next `/compact`** (unit + manual proof
already stand). Not committed — left in the working tree for review, which is itself the final
human sign-off before production.
→ *Converged.*

---

## When to skip this runbook — the vibe-coding carve-out

The full loop is for **durable, production-grade** changes. Skip it for throwaway or trivial
work — a one-line fix, a typo, a local experiment you'll delete. The floor never drops, though:
the harness hooks and `make check` still apply to *every* edit, spec or no spec. The test is
"will this outlive the session and does someone rely on it?" — if no, vibe-code it; if yes, you
want at least Stages 2, 6, and 8.

---

## Pointers

- **Full reference:** [`sdd_lifecycle_runbook.md`](../research/agenticengineeringplaybook/sdd_lifecycle_runbook.md) — every stage's Initiation · Agent work · Human gate · Loop-back · Harness instrumentation, plus the 2026 research crosswalk.
- **The integration plan** (sensors + skills that operationalize the runbook): [`sdd_lifecycle_harness_integration.plan.md`](../research/agenticengineeringplaybook/sdd_lifecycle_harness_integration.plan.md).
- **Constitution:** root [`AGENTS.md`](../../AGENTS.md) (invariants + boundaries + ADR triggers) and `tests/architecture/` (the mechanical enforcement).
- **Spec + ADR templates:** `docs/plan/_spec_template.md`, `docs/adr/0000-template.md`, and the small-decision log `docs/adr/decisions.md`.
