---
type: decision-record
title: 'ADR-0041: Exam module answer-key posture — client-grade phase-1 behind the ADR-0013 tripwire'
status: accepted
created: 2026-09-02
updated: 2026-09-02
owner: Rajnish Khatri
related: exam-module-official-rules.spec.md, exam-module-official-rules.plan.md, 0040-exam-module-durable-runs-analytics.md, 0013-subject-coach-test-mode-blueprint-generation-integrity.md
tags: [decision-record]
---

# ADR-0041: Exam module answer-key posture — client-grade phase-1 behind the ADR-0013 tripwire

**Status:** Accepted — 2026-09-02 (arch-lifecycle stage-5 risk **R3** → arch-decide; **Option A** chosen).
**Related:** [spec](../plan/exam-module-official-rules.spec.md) · [plan](../plan/exam-module-official-rules.plan.md) · [ADR-0040](0040-exam-module-durable-runs-analytics.md) (the exam module this governs) · [ADR-0013 §integrity](0013-subject-coach-test-mode-blueprint-generation-integrity.md) (the client-integrity stance + `COACH_TEST_KEYS_CLIENT_SERVED` tripwire this extends).
**Audience:** anyone building `components/exam/` grading, the form registry, or wiring `finishExamSection` — and anyone who assumes "the exam grades like Test Mode" without checking the triggers.

---

## Context

The exam module ([ADR-0040](0040-exam-module-durable-runs-analytics.md)) grades a timed
section and reuses the pure engine `Grader` (client-side, via `useEngine()`). Phase-1
content is the **already-public Test-01 English slice, client-bundled**. So, as designed,
the correct-answer fields ride the client during an in-progress timed section — exactly the
posture [ADR-0013](0013-subject-coach-test-mode-blueprint-generation-integrity.md) took for
Test Mode, where it was accepted **for-MVP** behind a code-enforced tripwire
(`COACH_TEST_KEYS_CLIENT_SERVED`, `services/governance/coach_test_mode_posture.py`) with
**three independently-sufficient flip triggers**: **delivery** (DB/sync-served rows),
**stake** (placement / mastery-FSRS feedback / reporting), **proctoring**.

Stage-5 risk **R3** flags that the exam module is **not** Test Mode: it adds **durable,
scored results and a strength/weakness analytics read model**. That *feels* like a higher
stake, and the whole purpose of the section-agnostic form registry is to load the
**privately-ingested official forms via the DB** — which would fire ADR-0013's **delivery**
trigger. The posture therefore must be a **recorded decision**, not silent inheritance.

---

## Decision

For **phase-1**, grade the exam
**client-side** exactly as Test Mode does, recorded as an **accepted risk bound to the
ADR-0013 tripwire**, extended to the exam module — because phase-1's only form is the
already-public, client-bundled Test-01 slice: **no** DB-delivery, **no** FSRS/placement/
external-reporting stake (§2.1 non-goals), **no** proctoring — so none of ADR-0013's three
triggers is actually fired yet. Add an exam-specific, **mechanically-detected** tripwire so
the posture flips to **server-side grading with answer-bearing fields stripped from
in-progress sections** the moment (a) the first **DB-served official form** lands (delivery)
or (b) results ever feed **placement / FSRS / external reporting** (stake). The server-grade
path (Option B below) is the **committed evolution**, not a maybe.

---

## Options considered & rejected

| Option | Verdict |
|---|---|
| **A. Client-grade phase-1 + code-enforced tripwire** (**chosen**) | Precedent-consistent with ADR-0013; phase-1 content is public + client-bundled with zero trigger fired; cheap (cost **S**); the tripwire makes the flip a reviewed code diff, not a scramble. Residual risk: a determined learner reads the Test-01 key mid-section — a **no-stakes practice** exposure Test Mode already carries. |
| **B. Server-side grading from the start** (`finishExamSection` grades on the BFF; in-progress sections ship questions **without** the four answer-bearing fields — the ADR-0013 Option-B mode) | Closes R3 up front, but **builds ahead of the trigger**: it adds a server grading path + key-stripping (cost **M**) for a phase-1 whose only form is the already-public Test-01 slice, which §2.1 explicitly scopes as concrete/deferred. The right destination — pre-committed here, enabled at the trigger, not before (last-responsible-moment). |
| **C. Inherit Test Mode's posture silently** (no ADR) | Rejected — the durable+scored+analysed nature is a real change from Test Mode's ephemeral posture; not recording it is precisely the intent-debt this ADR prevents (and R3 would recur unowned). |

---

## Rationale

- **Least-worst for phase-1.** Option A matches the repo's established, code-enforced
  accepted-risk pattern (ADR-0013) and respects that phase-1 content is public and
  client-bundled, so it neither over-builds (B before the trigger) nor hides the exposure
  (C). The tripwire is the honesty mechanism.
- **The trigger is imminent and named, so the flip is pre-decided.** The registry exists to
  load the official forms; the first DB-served form fires **delivery**. Pre-committing to
  Option B and detecting the trigger mechanically means the flip is a planned code diff, not
  a retrofit under stake (the "retrofit ≈ rewrite" trap ADR-0040 used to reject extending
  Test Mode).
- **Honest framing holds either way.** Phase-1 analytics are framed as *practice*
  signals, never certified/official scores (AP-6) — which keeps the "stake" trigger honestly
  un-fired until results actually feed placement/FSRS/reporting.

---

## Consequences

- **Commits us to** a `test_exam_no_client_served_keys`-style guard mirroring ADR-0013's
  `tests/architecture/test_no_client_served_test_keys.py`, extended to the exam module: no
  **DB-served** form may ship answer-bearing fields to the client while the exam posture
  flag is "client". The flag flips on the first DB-served official form or any real-stakes
  use; flipping it is a reviewed code diff paired with re-opening this ADR.
- **Accepted risk (phase-1):** a determined learner can read the client-bundled Test-01 key
  during a no-stakes practice section — the same exposure Test Mode already carries, now
  **explicitly recorded** for the exam module rather than silently inherited.
- **Follow-on (Option B, committed):** server-side `finishExamSection` grading + strip the
  four answer-bearing fields from in-progress sections; enabled at the delivery/stake trigger.
- **If you flip to B now:** R3 closes immediately; the cost is building the server-grade
  path before the phase-1 trigger fires. Mark this ADR's Decision as Option B and the guard
  becomes a "keys never client-served for the exam module, ever" invariant.

---

## Compliance

Automatable: a ts-morph / arch test asserting (1) no DB-served exam form serializes
`answer_letter` / `per_choice_rationale` / `why_correct_md` / `why_tempted_md` to the client
while the exam posture flag = "client"; (2) the exam posture flag is a real code switch (not
env-overridable), mirroring `coach_test_mode_posture.py`. Manual: on the first official form
PR, re-open this ADR and confirm the flip.

---

## Supersedes / related

- Extends [ADR-0013](0013-subject-coach-test-mode-blueprint-generation-integrity.md)'s
  client-integrity stance + tripwire **to the exam module** (does not supersede it).
- Governs the grading path left implicit in [ADR-0040](0040-exam-module-durable-runs-analytics.md).
- Resolves stage-5 risk **R3** (arch-lifecycle sweep, 2026-09-02).
