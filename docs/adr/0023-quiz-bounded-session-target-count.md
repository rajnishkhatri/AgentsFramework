---
type: decision-record
title: 'ADR-0023: Bounded no-repeat quiz session — target_count field + within-session served-ids uniqueness seam'
status: accepted
created: 2026-07-08
updated: 2026-07-08
owner: Rajnish Khatri
related: preact-quiz-target-count.spec.md, 0006-subject-coach-component-protocols.md, 0005-subject-coach-engine-home-and-substrate.md, 0021-bank-backed-practice-scheduler.md, 0022-act-english-syllabus-substrate.md
tags: [decision-record]
---

# ADR-0023: Bounded no-repeat quiz session

**Status:** Accepted — 2026-07-08. Implemented (Stage 6) the same day: the field (a) + uniqueness
seam (b) are landed and green; the gated-on-data S3-pre bank growth is **deferred** to a credentialed
generation run (forging the cascade provenance stamp is refused — see the spec §Status note). FR-11
(end-early-on-exhaustion) keeps the runtime correct at the current 171-item bank.
**Related:** [preact-quiz-target-count.spec.md](../plan/preact-quiz-target-count.spec.md) (the *what*),
[ADR-0006](0006-subject-coach-component-protocols.md) (SessionRepo/Scheduler/QuestionRepo protocols),
[ADR-0021](0021-bank-backed-practice-scheduler.md) (the bank-backed serve path this constrains),
[ADR-0022](0022-act-english-syllabus-substrate.md) (the coverage-ratchet + generation pipeline S3-pre reuses),
[ADR-0005](0005-subject-coach-engine-home-and-substrate.md) (dual-dialect substrate).
**Audience:** anyone touching the `/learn` quiz serve loop, the FSRS scheduler, the engine
`QuestionRepo`/`SessionRepo` ports, or the ACT-English item bank size.

---

## Context

The PreAct English Coach `/learn` quiz loop is **infinite by design**: `FsrsScheduler.next()`
picks the weakest-due skill and asks `QuestionRepo.nextReviewed(subject, skillId)` for a
question — a call that takes **no exclusion set** — so the same question can (and does) recur
within a session, and `QuizSession` has no length field. The prototype (all three device
specs) runs **bounded, distinct** sessions with a first and last question. This is gap-matrix
row Q-6, the head of the "bounded-session spine" (S3 → S4 progress bar → S5 done-state).

Sprint S3 was originally scoped as a small "add a nullable `target_count` field + per-mode
default." The clarify pass changed that: the human requirement is **30 unique questions per
session, no question repeated within a session** ("we must not review the same question more
than once per session"). Auditing that against the code refuted the "just a field" premise —
uniqueness is a **new scheduler capability**, not a property the field unlocks (evidence:
`fsrs_scheduler.ts:108` → `question_repo.ts:27`, no exclusion parameter anywhere). And the
"30 unique" target is **gated on data**: the reviewed `test_item` bank is unevenly sized
(s-gram 39, s-punc 31, s-rhet 28, s-style 26, s-org 24, s-sent 23), so a 30-unique *drill* on a
thin skill is impossible today.

A decision is needed now because S3 blocks S4 and S5, and because the change touches a
persisted wire type and adds a cross-port capability — both ⚠️ Ask-first triggers that require
an ADR before implementation (root `AGENTS.md`; ADR.1 ratchet).

---

## Decision

Ship S3 as a **bounded no-repeat session**, in one spec + this ADR:

1. **`target_count`** — a nullable positive-integer column on `QuizSession` (wire + both DB
   dialects + `SessionRepo.open`). `null` = endless (backward-compatible). Default when a caller
   omits it = **30 for every mode**, sourced from `content_string` rows (policy-as-data), read
   via the existing `ContentRepo` at open.
2. **Within-session uniqueness** — a **served-ids exclusion seam**: `excludeIds?: readonly
   string[]` on `QuestionRepo.nextReviewed` + `EngineDb.nextReviewedQuestion` (a `NOT IN`
   push-down on the live drizzle seam; a filter on the `InMemoryEngineDb` fake; forwarded by
   `TestItemQuestionRepo`), and `servedIds?: readonly string[]` on `Scheduler.next`. All new
   params are **optional**, so every existing caller/test compiles unchanged and omitting them is
   exactly today's behaviour. The served set is **ephemeral and caller-owned** — derived from
   the session's append-only `attempt` rows and passed per `next()` call — **never** persisted on
   `skill_state` (which stays the sole adaptivity source of truth, FR-A2).
3. **Gate on data (S3-pre, blocking):** before the flat-30 uniqueness guarantee can hold,
   generate + cascade-promote **+19** reviewed `test_item`s via the ADR-0021/0022 pipeline
   (rhet +2, style +4, org +6, sent +7 → every skill ≥ 30) and raise the ADR-0022 per-skill
   coverage floor to 30. This is a prerequisite of the S3 implement phase.

The **visible** "review is finished" done-state + retake stay **S5**; S3 makes serving bounded +
non-repeating and stores the number. When a skill's unserved items run out mid-session the
scheduler falls through to the next-weakest with unserved items; when all are exhausted before
`target_count`, `next()` returns the existing `null`/not-found signal so the caller ends early —
never a repeat to pad the count.

---

## Options considered & rejected

### Scope

| Option | Verdict |
|---|---|
| **Enlarge S3 = field + uniqueness (chosen)** | One coherent unit: a session that is bounded AND never repeats. The visible terminal stays S5. |
| S3 = field only; separate S3b for uniqueness | Rejected (human gate): cleaner two-sprint split, but a bounded session would still repeat questions until S3b lands — the user wanted the no-repeat behaviour shipped with the field. |
| Field + uniqueness + terminal state (fold in S5) | Rejected: largest single sprint, collapses S3+S5, delays any review gate; the visible done-state is genuinely separable and belongs with the progress-bar work. |

### Thin-skill drill vs a flat 30

| Option | Verdict |
|---|---|
| **Grow the bank to ≥30/skill first, flat 30 (chosen)** | Rejected the shortfall instead of the requirement: +19 items via an existing, cascade-verified pipeline; keeps a single "30" everywhere (simple to explain, faithful to the prototype). Cost = a bounded generation task + a floor raise. |
| Cap drill at `min(30, items available)` | Rejected (human gate): honors no-repeat with zero bank dependency, but makes drill length vary per skill; the user preferred a flat 30. Retained only as the FR-11 *safety net* if a bank ever dips below 30. |
| Adaptive 30 / drill 10 (smaller drill) | Rejected: fits every thin bank uniquely without growth, but puts 30-unique-drill off the table by design — contrary to the requirement. |

### Where the served-ids set lives

| Option | Verdict |
|---|---|
| **Caller-owned, passed per `next()`, derived from attempts (chosen)** | Session-scoped ephemeral state stays out of the durable adaptivity row; a page reload reconstructs it from `attempt` (append-only). Keeps `skill_state` pure (FR-A2). |
| Persist served-ids on `skill_state` | Rejected: pollutes the sole adaptivity source of truth with session-ephemeral data; the Scheduler is the only `skill_state` writer and `next()` must stay read-only w.r.t. it. |
| A new `session_served_item` table | Rejected: `attempt` already records exactly what was served — a second store is redundant and an F-R3/abstraction-introduction violation (no second consumer). |

### Where the per-mode default lives

| Option | Verdict |
|---|---|
| **`content_string` rows (chosen)** | Policy-as-data on the existing ADR-0022 objective plane; editable without code, no new table. The default is not a scheduling *decision* (which would belong in `components/`), just a stored number. |
| A pure TS const module | Considered; a reasonable lighter option, but the answer explicitly chose the data plane so the length is content-editable alongside the other objective-plane strings. |
| Caller always supplies it (no engine default) | Rejected: pushes "which N" up toward the component (F-R1 tension) and forces every caller to know the number. |

### Uniqueness mechanism

- **`excludeIds` param on the existing reviewed read (chosen)** over a new "session-aware
  QuestionRepo" port — the reviewed gate is unchanged, the filter lives at the same seam, and an
  optional param keeps every caller/test compiling. A new port would fail F-R3 (no second
  implementation earns it).

---

## Rationale

- **The refuted premise forces the scope.** A field alone cannot deliver "no repeat" — the
  serving path re-asks. Shipping the field without the exclusion seam would look done but leave
  the user's actual requirement unmet, so the two must ship together.
- **Optional params = zero-risk widening.** `excludeIds?`/`servedIds?`/`targetCount?` default to
  today's behaviour; the change is additive at every seam (wire nullable column, optional port
  params) and fully reversible.
- **Purity holds.** Served-ids are read-only input to `next()` and derived from the engine's own
  attempt records; `skill_state` stays the sole adaptivity truth and the Scheduler stays its sole
  writer. The reviewed gate is filtered *within*, never bypassed.
- **Honesty about data.** "30 unique everywhere" is only true once the bank supports it; making
  S3-pre a *blocking* prerequisite (with a rises-only coverage floor) turns "the bank is big
  enough" into a measured, ratcheted property instead of an assumption — exactly the ADR-0022
  posture. FR-11 keeps the system correct (end early, never repeat) even if a bank later dips.

---

## Consequences

- **Commits us to** a served-ids exclusion parameter across three seams (`QuestionRepo`,
  `EngineDb`, `Scheduler`) + the `TestItemQuestionRepo` forward; a `target_count` nullable column
  on both DB dialects (a drizzle migration per dialect — nullable add, no backfill); three new
  `content_string` rows; and a **bank-growth task (S3-pre)** of +19 cascade-verified items plus a
  coverage-floor raise to 30.
- **S3-pre is gated-on-data and offline.** Generation runs the creds-gated
  `scripts/generate_test_items.py` → verifier cascade → `promote_test_item_seed.py` →
  `emit_test_item_bank.py`; **no live LLM in CI** (the emitted bank is committed and replayed;
  the provenance + emit-drift + coverage-ratchet tests are the gates). Accepted risk: generation
  may need more than one run to clear the cascade for the thin skills — a recorded honest cost,
  not a floor relaxation.
- **The coverage floor raise (→30) is deliberately hard to revert** — the ADR-0022 ratchet
  mechanically blocks lowering it. That is the point: the bank cannot silently shrink below the
  size the uniqueness guarantee depends on.
- **Determinism preserved.** `next()` with an exclusion set stays deterministic given
  (skill_state, served-ids, injected clock); the exclusion is a pure filter before the existing
  most-due/weakest sort (whose `localeCompare` tie-break already removes store-order nondeterminism).
- **Does NOT ship** the visible "Question N / M" bar (S4) or the visible done-state + retake
  (S5). S3's early "no more items" signal is what S5 will render.
- **No new dependency**, no new graph node, no Python trust-kernel change → **no re-signing**.
  The engine wire family is frontend-only (no Python mirror), so Rule W2 / `__python_schema_baseline__`
  do not apply to `target_count`.
- **Two ⚠️ Ask-first triggers** (persisted wire-type change + the cross-port uniqueness
  abstraction) are covered by this single ADR; the S3-pre bank growth reuses the ADR-0022
  pipeline (no new abstraction) and is recorded here rather than in a separate ADR.

---

## Supersedes / related

Realizes [preact-quiz-target-count.spec.md](../plan/preact-quiz-target-count.spec.md). Constrains
the [ADR-0021](0021-bank-backed-practice-scheduler.md) bank-backed serve path (the exclusion set
applies to the `TestItemQuestionRepo` read). Reuses the [ADR-0022](0022-act-english-syllabus-substrate.md)
generation pipeline + coverage ratchet for S3-pre. Unblocks S4 (progress bar) and S5 (done-state
+ retake). No prior ADR superseded.
