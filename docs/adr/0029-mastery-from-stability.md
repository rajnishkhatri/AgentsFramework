---
type: decision-record
title: 'ADR-0029: Dashboard mastery is derived from FSRS stability, not retrievability-at-review'
status: proposed
created: 2026-07-12
updated: 2026-07-12
owner: Rajnish Khatri
related: docs/plan/preact-parity-E1b-D0-mastery-write-path.spec.md, docs/plan/preact-parity-E1b-D0-mastery-write-path.plan.md, docs/plan/preact-learn-followups.notes.md, docs/adr/0023-quiz-bounded-session-target-count.md
tags: [decision-record, epic-e, e1b, scheduler, fsrs, mastery]
---

# ADR-0029: Dashboard mastery is derived from FSRS stability, not retrievability-at-review

**Status:** Proposed — 2026-07-12.
**Related:** [E1b-D0 spec](../plan/preact-parity-E1b-D0-mastery-write-path.spec.md) · [F1 root-cause trace](../plan/preact-learn-followups.notes.md)
**Audience:** anyone touching `FsrsScheduler`, the dashboard mastery grid, or the weakest-skill focus pick.

---

## Context

The dashboard shows a per-skill "mastery %". A learner reported completing a skill with **30
wrong answers** and seeing **100% mastery**. The trace (F1) proved this is not a display bug: the
dashboard renders `SkillState.mastery` faithfully. The bug is in the **sole `skill_state` writer**,
`FsrsScheduler.review()` → `fromCard()`, which stores:

```
mastery = get_retrievability(card, reviewedAt)   // fsrs_scheduler.ts:299
```

`get_retrievability` on the forgetting curve evaluated at the **review instant itself** (elapsed
time ≈ 0) is **~1.0 by definition**, regardless of how far `stability` has collapsed. A wrong answer
is `Rating.Again`, which *correctly* collapses `stability` (reproduced: 5 wrong → 0.212 → 0.083 →
0.035 → 0.015 → 0.007) — but `retrievability_at_review` re-pins to ~1.0 on every grade, masking the
collapse. So every grade, right or wrong, overwrites `mastery ≈ 1.0`.

The same `mastery` field also drives the weakest-skill pick (`focus_pick.ts:31` sorts by
`a.mastery - b.mastery`), so a skill you are failing looks mastered and drops out of "today's focus."

This surfaced while planning E1b, whose `accuracyStat` block exists *specifically* to keep the
mastery≠accuracy conflation out of the lesson (`DATA-ACC-1`/`GUARD-ACC-1`). Fixing the live dashboard
instance (D0) is the do-regardless hygiene ahead of that work.

---

## Decision

Replace the `mastery` projection in `FsrsScheduler.fromCard()` with a **monotone function of
`fsrs_stability`**, not instantaneous retrievability:

```
masteryFromStability(s) = s / (s + K),  K = 21   // 0↦0, s→∞↦1, strictly increasing, clock-free
```

`K` is the "half-mastery interval" in days (stability at which mastery reads 0.5); `K = 21` ≈ a
three-week retention interval as the competence midpoint. The stored field, its `[0,1]` range, the
wire type, and every downstream reader are unchanged — only the *value written* changes. This fixes
the dashboard card and the focus pick in one write-path change.

---

## Options considered & rejected

| Option | What it does | Why rejected |
|--------|--------------|--------------|
| **Keep retrievability-at-review** (status quo) | `R(card, reviewedAt)` | The bug itself — ~1.0 at elapsed≈0 masks all wrongness. |
| **Label/footnote only** (original D0 in the brainstorm) | Leave the value; relabel so "mastery" isn't read as accuracy | Treats the symptom: the dashboard still shows ~100% after all-wrong; the focus pick stays broken. Refuted by the root-cause trace. |
| **Rolling answer-correctness window** | Derive displayed mastery from recent `attempt.correct` | That *is* E1b-D1's accuracy read. Collapses the mastery↔accuracy distinction D7 deliberately keeps (two different numbers with two different labels on the lesson). Wrong layer for a scheduler-owned durable signal. |
| **Retrievability at a FIXED horizon** | `R(card, due_at)` or R at a standard elapsed | Better than review-instant, but still a re-derived forgetting-curve value; re-pins toward high right after any grade for short intervals; less transparent than a direct stability map. |
| **FSRS stability via `s/(s+K)` (chosen)** | Monotone squash of the quantity that already collapses on wrong | Uses the signal FSRS already computes correctly; bounded, deterministic, tunable; no new read; honors the header comment's stated intent. |

---

## Rationale

`fsrs_stability` is the FSRS state variable that **already** tracks durable competence — it collapses
on `Rating.Again` and grows on correct streaks. The bug was reading the *wrong* projection of the card,
not a missing signal. A monotone squash `s/(s+K)` is the minimal, transparent map: it needs no clock
(so the fix is L1-deterministic and testable without faking time — the exact property whose absence let
the bug ship), sends `0↦0` and saturates at 1, and keeps the field in `[0,1]` for all finite `s ≥ 0`.
Because acceptance asserts **direction + monotonicity + bounds**, the constant `K` is tunable later
without touching tests. Fixing the writer (not the readers) fixes every consumer at once.

---

## Consequences

- **Commits us to** a scheduler-owned `mastery` that means "stability-derived durable competence,"
  distinct from E1b-D1's answer-accuracy — the two are now cleanly separated across the app (dashboard
  = competence; lesson `accuracyStat` = accuracy).
- **`retrievability()` becomes dead code** and is removed (sole caller was `:299`); the stale header
  comment is corrected.
- **Forward-only migration.** Stale pre-fix `skill_state` rows keep their old (wrong) `mastery` until
  the next `review()` per skill rewrites them; they read fine meanwhile. A one-time backfill is **out
  of scope** (would be its own ADR) — accepted risk: a dormant skill shows a stale-high mastery until
  next practiced. Mitigation: the number self-heals on the next grade, and the focus pick's `due`
  preference still surfaces due skills.
- **`K` is a product-tunable constant**, not a law; changing it shifts the curve but not the invariant.
- **Does not change scheduling** (`next`, `due_at`, stability, difficulty) — S3 bounded-session and
  no-repeat behavior are unaffected (guarded by FR-6).

---

## Supersedes / related

Makes canonical the D0 spec + plan. Related: ADR-0023 (bounded session — the other `skill_state`
consumer whose behavior must not regress). Does not supersede any prior ADR.
