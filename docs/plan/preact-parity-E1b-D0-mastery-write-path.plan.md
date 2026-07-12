---
title: 'E1b-D0 — mastery write-path fix: implementation plan'
type: plan
sub_epic: E1b
direction: D0
status: Draft — 2026-07-12
derives_from: docs/plan/preact-parity-E1b-D0-mastery-write-path.spec.md
adr: docs/adr/0029-mastery-from-stability.md
---

# E1b-D0 — implementation plan

## Architecture

One pure change at the **sole `skill_state` writer**: swap the `mastery` projection in
`FsrsScheduler.fromCard()` from instantaneous retrievability-at-review to a monotone function of
`fsrs_stability`. Everything downstream (`bucket_card_vm`, `focus_pick`, `today_focus_vm`) is a pure
T1 reader of `SkillState.mastery` and is **untouched** — correctness moves upstream to the writer, so
the dashboard card AND the weakest-skill pick are both fixed by one change (class-over-instance).

**The map (ADR-0029 decision).** `masteryFromStability(s) = s / (s + K)`, a bounded monotone squash on
`s ≥ 0`: `0 ↦ 0`, `s → ∞ ↦ 1`, strictly increasing, deterministic (no clock). `K` = the stability (in
days) at which mastery reads 0.5 — the "half-mastery interval." Proposed `K = 21` (a 3-week retention
interval ≈ competent), ratified in ADR-0029; the acceptance tests assert **direction + monotonicity +
bounds**, so they hold for any monotone `K` and the constant is tunable without touching tests.

## File-level touchpoints

| File | Change |
|------|--------|
| `frontend/lib/adapters/engine/scheduler/fsrs_scheduler.ts` | Add `private masteryFromStability(stability: number): number` (pure, finite-guarded). In `fromCard()` (`:299`) replace `mastery: this.retrievability(card, reviewedAt)` → `mastery: this.masteryFromStability(card.stability)`. **Remove** the now-dead `retrievability()` (`:308-314`, sole caller was `:299`) and fix the stale header comment (`:27-29`) to describe the stability projection. |
| `frontend/lib/adapters/engine/scheduler/fsrs_scheduler.test.ts` | Add the direction/monotonicity/bounds tests (FR-1..FR-6). **Strengthen** the weak `mastery ∈ [0,1]`-only assertion (`:151-152`) — but under **G8**: the old assertion stays (bounds = FR-5), we ADD direction, not weaken. |
| `docs/adr/0029-mastery-from-stability.md` | New ADR (map + constant + rejected alternatives). |
| `docs/adr/index.md`, `docs/adr/log.md` | OKF entries (newest-first log line). |

**No change:** `bucket_card_vm.ts`, `BucketCard.tsx`, `focus_pick.ts`, `today_focus_vm.ts`, wire types,
DB schema, middleware. They read `mastery`; the value is now honest.

## Migration

Forward-only. No backfill: the next `review()` per (skill, learner) rewrites `mastery` from stability.
Stale pre-fix rows read fine (still a number in [0,1]); they self-heal on the next grade. A one-time
backfill would be a separate ADR — explicitly **out of scope** (noted in ADR-0029 Consequences).

## Invariants (constitution check)

- **Inv #3/#4 (framework-agnostic):** change is inside `adapters/engine/scheduler/` where ts-fsrs
  isolation already lives (F-R8). `card.stability` is a plain number — no SDK type crosses the boundary.
- **Determinism (T1/L1):** `masteryFromStability` is a pure arithmetic function — the FR-1..FR-6 tests
  need no clock/fixture. This is the *point* of moving off `reviewedAt`.
- **FR-13 serving purity:** `Scheduler.next()`, `due_at`, `fsrs_stability`, `fsrs_difficulty` unchanged
  (FR-6 test guards it) — S3 bounded-session + no-repeat suites must stay green.
- **⚠️ Ask-first → ADR-0029:** changing what a durable stored signal *means* is the trigger.
  `test_adr_ratchet.py` is satisfied by the new `docs/adr/0029-*.md`.

## Build order (red→green)

1. Write ADR-0029 (map + `K` + rejected alternatives) — the *why* before the code (G1/G4-adjacent).
2. **Red:** add the FR-1 test (reproduce F1: 30 wrong grades in one session, assert mastery never
   increases + ends low). Run — watch it **fail** on the current `retrievability` code.
3. **Green:** add `masteryFromStability`, swap the projection at `:299`, delete dead `retrievability()`.
4. Add FR-2..FR-6 tests; strengthen the `:151` assertion (add direction, keep bounds — G8 note).
5. Verify FR-4 (correct streak raises mastery) + `focus_pick`/`today_focus` now pick a failed skill.
6. `pnpm test` (vitest) + `pnpm test:arch` + `pnpm typecheck`; paste the FR-1 red→green output.

## Test → FR map

| FR | Test | Layer |
|----|------|-------|
| FR-1 | `…::N consecutive wrong never raise mastery` | L1 |
| FR-2 | `…::collapsed stability → mastery→0` | L1 |
| FR-3 | `…::monotone in stability, clock-independent` | L1 |
| FR-4 | `…::correct streak raises mastery` | L1 |
| FR-5 | `…::mastery ∈ [0,1] for stability 0..large` | L1 |
| FR-6 | `…::next()/due_at/stability unchanged` | L1 |
| FR-7 | `bucket_card_vm.test.ts::brand-new still 0%` (existing) | L1 |
