---
type: decision-record
title: 'ADR-0030: Lesson→coach seed contract — a discriminated coach pin (item | lesson), no fabricated question'
status: accepted
created: 2026-07-12
updated: 2026-07-12
owner: Rajnish Khatri
related: docs/plan/preact-parity-E1b-D2-coach-seed.spec.md, docs/plan/preact-parity-E1b-D2-coach-seed.plan.md, docs/adr/0025-coach-surface-vm.md, docs/adr/0028-lesson-content-read-path.md
tags: [decision-record, epic-e, e1b, coach, wire, security]
---

# ADR-0030: Lesson→coach seed contract — a discriminated coach pin (item | lesson)

**Status:** Accepted — 2026-07-12.
**Related:** [E1b-D2 spec](../plan/preact-parity-E1b-D2-coach-seed.spec.md) · [ADR-0025 coach-surface-vm](0025-coach-surface-vm.md)
**Audience:** anyone touching the coach pin, `assembleCoachContext`, the coach thread store, or the BFF coach-context sanitizer.

---

## Context

The `/learn/skill` lesson shows a `coachEntry` block — a skill-pinned entry point to the Socratic
coach (design `FR-BLK-20`). E1a shipped it as a **button-only seam**: a bare `<Link>` to the coach
route that carries **no seed** (`SkillDetailView.tsx:381`). The design spec's `OQ-3`/`D4c` explicitly
deferred the **lesson→coach seed contract**: *how a skill-pinned, lesson-context coach entry is
expressed when there is no active `question_id`.*

Today the coach can only be seeded from an **item pin** with a required `questionId`
(`CoachSurfacePin.questionId: string`, `coach_surface_vm.ts:25`), and `assembleCoachContext` returns
**null** unless a full `Question` matching `pin.questionId` loads (`assemble_coach_context.ts:47-48`).
So the lesson's "Open coach" button lands the learner on whatever **stale or null pin** sits in the
`coach_thread_store` singleton — a real latent bug (cold-open against a prior quiz's question).

The coach display chrome already runs on `skillId` alone (miss count, skill label), and the BFF
sanitizer already fails **closed** to `pre_submit` on an absent `question_id`. So the gap is narrow:
express a skill-only pin + a skill-only `coach_context`.

---

## Decision

Make `CoachSurfacePin` a **discriminated union**:

```
type CoachSurfacePin =
  | { kind: 'item';   questionId: string; skillId: string; label: string }
  | { kind: 'lesson';                     skillId: string; label: string }
```

Add a **lesson branch** to `assembleCoachContext` that emits a `coach_context` with `skill_id` set and
`question_id`/`question` **omitted** (honest-null, not fabricated), mode `pre_submit`. Replace the
lesson's bare `<Link>` with a **store-write-then-navigate** (`setCoachPin({kind:'lesson', …})` then
navigate), mirroring the quiz pin-write. **No middleware/BFF change** — the sanitizer's existing
fail-closed default is correct for a lesson entry.

---

## Options considered & rejected

| Option | Why rejected |
|--------|--------------|
| **Keep the bare `<Link>`** (status quo) | Cold-opens the coach on a stale/null pin — the latent bug. Never seeds the skill. |
| **Make `CoachSurfacePin.questionId` nullable** (`string \| null`) | Silent hazard: fresh-thread/transcript-reset logic keys on `questionId` **equality** (`use_coach.ts`, `coach_thread_store.ts`); a null would mis-reset or fail to reset. Nothing forces consumers to handle the lesson case — the compiler stays quiet. |
| **Fabricate a placeholder `Question`** for the lesson pin | Manufactures data the learner never saw; risks the answer-leakage lint surface; violates the honest-null discipline (AP-6). |
| **A separate `LessonCoachPin` type + parallel path** | Duplicates the pin plumbing and the context assembly; two code paths drift. The union reuses one path with an explicit branch. |
| **Discriminated union + honest-null question (chosen)** | Forces exhaustive handling at every consumer (typecheck-enforced), keeps one assembly path, and carries no fabricated data. |

---

## Rationale

A discriminated union turns "the coach might have no question here" from a runtime hazard into a
**compile-time obligation**: every `pin.questionId` read must first narrow on `kind`, so no consumer
can silently mishandle a lesson pin (the reset logic especially). Omitting `question_id`/`question`
(rather than nulling or faking them) keeps the honest-null discipline and lets the BFF sanitizer route
the entry to `pre_submit` by its **existing** fail-closed rule — the security property is *reused*, not
re-implemented. Confining everything to the frontend ring (pins, translators, view) keeps the blast
radius small and needs no middleware coordination.

---

## Consequences

- **Commits us to** a coach pin that is explicitly one of two kinds; future pin sources (e.g. a
  dashboard "coach this skill" entry) reuse the `lesson` branch for free.
- **Every pin consumer** must handle both `kind`s — a one-time exhaustiveness sweep (the compiler lists
  them). Item behavior is unchanged.
- **Security:** a lesson context cannot assert `post_feedback` (it has no `question_id`), so it cannot
  trigger an answer reveal — the sanitizer's fail-closed default guarantees this; a test asserts a
  spoofed lesson-context-with-marker still fails closed.
- **Closes the cold-open-against-stale-pin bug** as a side effect of the store-write-then-navigate.
- **No persisted change** — pins are ephemeral; revert restores the bare link (and the bug).
- **The live conversation surface is unchanged** — this ADR governs only the *seed*, not the coach's
  Socratic behavior.

---

## Supersedes / related

Extends ADR-0025 (coach-surface-vm) with the lesson pin kind. Related: ADR-0028 (E1a shipped the
coachEntry seam inert). Supersedes no prior ADR.
