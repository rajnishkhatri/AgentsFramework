---
type: decision-record
title: 'ADR-0024: Round-robin skill rotation in the quiz scheduler'
status: accepted
created: 2026-07-08
updated: 2026-07-08
owner: Rajnish Khatri
related: preact-quiz-skill-rotation.spec.md, 0023-quiz-bounded-session-target-count.md, 0021-bank-backed-practice-scheduler.md, 0006-subject-coach-component-protocols.md
tags: [decision-record]
---

# ADR-0024: Round-robin skill rotation in the quiz scheduler

**Status:** Accepted — 2026-07-08 (implemented at Stage 6; see
[preact-quiz-skill-rotation.spec.md](../plan/preact-quiz-skill-rotation.spec.md) §10). Ratification =
the tasks→implement human gate.
**Related:** [preact-quiz-skill-rotation.spec.md](../plan/preact-quiz-skill-rotation.spec.md) (the *what*),
[ADR-0023](0023-quiz-bounded-session-target-count.md) (the served-ids seam this widens),
[ADR-0021](0021-bank-backed-practice-scheduler.md) (the serve path), [ADR-0006](0006-subject-coach-component-protocols.md)
(Scheduler #5 / AttemptRepo #3).
**Audience:** anyone reconsidering the quiz scheduling order, the `AttemptRepo`/`EngineDb` served
seam, or the FR-13 serve-path purity invariant.

---

## Context

A learner reported: *"after completing/finishing & review any of the skill, the next skill is always
sentence completion."* The behaviour is real and reproducible, but it is **not hardcoded** — it is an
emergent consequence of two correct-in-isolation design facts:

1. **Within-session serving is read-only (S3 / FR-13, FR-A2).** `FsrsScheduler.next()` must not write
   `skill_state` while serving; `review()` is the sole writer. So a skill's **mastery is frozen** for
   the whole session — nothing a serve walk does re-orders the skills within that session.
2. **The pool is sorted weakest-mastery-first**, then `due_at`, then `skill_id`
   (`fsrs_scheduler.ts:101-109`). With frozen mastery this is a **fixed sequence**. The dev seed
   (`_dev_seed.ts:141-146`) gives distinct masteries; once the three *due* skills drain, `s-sent`
   (mastery 0.61) is the perpetual next-weakest, so every fall-through lands on sentence-completion.

The S3 no-repeat seam (ADR-0023) already threads a **caller-owned, session-scoped served set**
(`servedIds`, derived from the append-only `attempt` rows) into `next()`. The natural fix reuses that
exact pattern: derive the served **skills in recency order** from the same `attempt` rows and use them
to **re-order the pool**, so a just-finished skill goes to the back of the line and the session
rotates across buckets.

This is a **frontend-only engine** (no Python mirror), so Rule W2 / `__python_schema_baseline__` do not
apply; there is no wire-shape or DB-column change (the join reads existing `attempt.question_id` +
`question.skill_id`).

Two `⚠️ Ask first` triggers fire, which is why this ADR exists:
- a **new cross-port capability** — `AttemptRepo.servedSkillIds` + `EngineDb.listSessionSkillIds`
  (the same class of change as S3's T-b0 session-scoped read), and
- a **new scheduling-order policy** — round-robin fairness layered over weakest-first, which changes
  real adaptive behaviour for **all** learners, not just the demo seed.

---

## Decision

Ship **strict round-robin rotation** as an opt-in, backward-compatible extension of the S3 served
seam:

- Add `AttemptRepo.servedSkillIds(sessionId)` → `EngineDb.listSessionSkillIds(sessionId)` returning the
  session's **distinct skills, newest-first**, derived by joining `attempt → question` and ordering by
  `created_at` desc (drizzle push-down in `db/`; behavioral filter in the in-memory fake).
- Add an optional 4th param `servedSkillIds?` to `Scheduler.next(subject, learnerId, servedIds?,
  servedSkillIds?)`. When supplied, **least-recently-served becomes the PRIMARY sort key** of the
  candidate pool: a never-served eligible skill sorts first; among served skills, the one whose
  most-recent serve is oldest sorts first; the existing weakest-mastery → `due_at` → `skill_id` order
  breaks ties **only after** rotation.
- `use_quiz.openQuizItem` derives `servedSkillIds` alongside the existing `servedIds` and passes both.

All new params/methods are **optional and additive**: omitting `servedSkillIds` reproduces today's
weakest-first behaviour exactly. Rotation is a **pure read policy** — no `skill_state` write on the
serve path (FR-13 preserved). The within-session no-repeat guarantee (ADR-0023 FR-9/10/11) is
untouched: rotation only changes *which eligible skill is tried first*, never re-serves a question, and
never changes the exhaustion condition.

---

## Options considered & rejected

| Option | What | Why rejected |
|---|---|---|
| **A. Rotation as a mastery tie-break** | Keep mastery primary; rotation only breaks equal-mastery ties. | **Does not fix the bug.** The seed masteries are all distinct (0.28/0.40/0.55/0.61/0.74/0.82) → no ties → tie-break never fires → `s-sent` stays perpetual-next. Preserves adaptivity at the cost of leaving the reported defect in place. |
| **B. No-immediate-repeat only** | Forbid returning the single most-recently-served skill when another eligible skill exists; otherwise weakest-first. | Fixes the *visible* "same skill twice in a row" with minimal deviation, but is not a true rotation — a skill can recur after one gap, so the session still clusters. The user asked to "rotate across skills," which B under-delivers. |
| **C. Make `next()` mutate mastery so weakest-first self-rotates** | Advance `skill_state` during serving so the served skill stops being weakest. | **Violates FR-13 / FR-A2** — serving must be read-only; `review()` is the sole `skill_state` writer. Would corrupt the adaptivity source of truth and couple serving to scoring. |
| **D. Track recency on `skill_state`** | Store a "last served" marker per skill to order rotation. | Same FR-13/FR-A2 violation as C (a write on the serve path), and it would leak an ephemeral, session-scoped concern into the durable, learner-scoped adaptivity store. Recency must be **derived** from `attempt`. |
| **E. Derive recency in the scheduler from `servedIds`** | Scheduler resolves each served question-id → skill itself (no new port method). | Rejected in clarify in favour of a first-class seam: `servedIds` carries no order and re-resolving N questions per pick re-does work the DB can do in one ordered read. The new method is the cleaner, testable boundary (matches S3's T-b0 precedent). |
| **F. Do nothing (seed-only)** | Treat it as a dev-seed artifact; vary the seed for demos. | The ordering is real for any learner whose live `skill_state` happens to have a stable weakest skill, not only the demo. A behaviour users notice deserves a behaviour fix, not just a prettier fixture. |

**Chosen: strict rotation (the "primary sort key" form of the accepted direction).** It is the only
option that both fixes the reported defect and delivers the requested cross-skill variety, while
staying inside the read-only serve-path invariant.

---

## Rationale

Strict rotation wins because it is the **minimal change that actually solves the stated problem**
without touching the invariant that caused it. The frozen-mastery fact (FR-13) is *correct* — serving
should not mutate adaptivity — so the fix cannot come from unfreezing mastery (options C/D). Given
mastery is fixed within a session, the only lever left is the **ordering policy**, and only making
rotation *primary* (not a tie-break) changes the order when masteries are distinct — which they always
are for a real learner mid-session. Reusing the ADR-0023 served-seam pattern (caller-owned, ephemeral,
`attempt`-derived) keeps the new capability consistent with the one already reviewed and shipped, so
the blast radius is one new read method mirrored across the two `EngineDb` implementations plus a pool
re-sort — no wire change, no migration, no new dependency.

---

## Consequences

**Commits us to:**
- A **new served-skill read** on `AttemptRepo` + both `EngineDb` implementations (drizzle + in-memory),
  added to the port-conformance surface — the served seam is now two methods (`servedQuestionIds`,
  `servedSkillIds`), and future `EngineDb` backends must implement both.
- A **rotation-first scheduling policy** whenever the caller passes `servedSkillIds`. The play loop
  (`use_quiz`) opts in, so the live `/learn` surface rotates; any caller that omits the param keeps
  strict weakest-first.

**Accepted risk (stated honestly):** rotation outranks mastery, so within a session `next()` may serve
a *slightly-less-weak* eligible skill before a weaker one that was just served — a deliberate trade of
strict within-session adaptivity for cross-skill variety. Mitigation: (a) within-session mastery is
frozen anyway, so the adaptive-precision loss *within one session* is small; (b) across sessions
`review()` still advances `skill_state`, so the weakest-skill focus reasserts at the next session's
first pick (where `servedSkillIds` is empty → weakest-first, FR-1); (c) the tie-break chain still ends
in weakest-mastery → due → id, so among equally-recently-served skills the weakest is still preferred.

**Follow-on:** the S3 validation harness (`frontend/scripts/validate_s3_bounded_session.{ts,md}`) gains
a rotation check (no skill served twice consecutively while >1 skill is eligible). A future
progress/skill-coverage UI (S4/S5) may want to *surface* the rotation; out of scope here.

---

## Supersedes / related

Refines the serving behaviour established by [ADR-0021](0021-bank-backed-practice-scheduler.md) and
extends the served-ids seam from [ADR-0023](0023-quiz-bounded-session-target-count.md). Supersedes no
prior ADR. Canonical *what*: [preact-quiz-skill-rotation.spec.md](../plan/preact-quiz-skill-rotation.spec.md).
