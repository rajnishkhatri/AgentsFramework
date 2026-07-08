# Spec — D4: two-level topic taxonomy with FSRS StandardState + unlock progression

> EARS criteria; failure paths first. This change fires ⚠️ Ask-first triggers
> (wire-kernel additions, new persistent entity in both DB seams, new product
> abstraction) → a full ADR (`docs/adr/0000-template.md`) accompanies
> implementation; this spec is the *what*.

**Status:** Draft — 2026-07-07
**Owner:** Rajnish Khatri
**Related:** `docs/plan/act-english-full-bank.brainstorm.md` (D4 direction +
gate reframing: topic-by-topic mastery, step-by-step unlock, composite unlock
at full coverage), `docs/plan/act-english-syllabus-substrate.spec.md` (D3 —
supplies the syllabus TS plane + `standard_id` tags), STYLE_GUIDE_FRONTEND
rules W1/W6/W7 (wire), A2/A4/F3/P7 (seams), T1–T4 (translators), U-family
(dashboard), checklist C.

**Clarified at the human gate (2026-07-07):** full FSRS `StandardState` (NOT
computed read-side — rejected) and unlock/progression gating IN scope (NOT
deferred — rejected). Both rejections recorded for the ADR's Options section.

---

## 1. Goal

Topic-by-topic mastery in the product: each of the 32 syllabus standards gets
its own FSRS-scheduled mastery state; practice serves the weakest unlocked
standard within the weakest skill; standards unlock step-by-step in
curriculum order; the composite surfaces (timed test, composite practice)
unlock when every standard is unlocked.

## 2. Context

- Today the engine is skill-granular only: `FsrsScheduler.next()` picks the
  weakest+due skill (`fsrs_scheduler.ts:73-101`), `nextReviewedQuestion`
  picks lowest-difficulty-first within it (fake `:109-123`, Drizzle twin
  `:275-293`); mastery = FSRS retrievability written ONLY by
  `Scheduler.review()` (FR-A2 single-writer, `:149,254`); dashboard = one
  BucketCard per skill. No topic concept exists anywhere (explore sweep,
  2026-07-07).
- Wire kernel is frontend-local (no Python mirror — ADR-0005 exemption from
  W2); Zod objects default-strip, so taxonomy fields must be explicit schema
  additions.
- D3 supplies the canonical standard list (32, with bands + app_skill) as an
  emitted TS plane, and `standard_id` on bank items.
- **Non-goals:** backfilling per-standard FSRS state from historical attempts
  (fresh-init chosen; rejected alternative recorded in the ADR), Test-01
  `Question` rows (test-only rows stay untagged; D2 governs them), Python
  backend involvement (frontend-ring change only), authoring/content (Phase B).

## 3. Functional requirements (EARS)

Failure paths first.

- **FR-1 (untagged item fallback).** IF an item lacks `standard_id` THEN
  scheduling SHALL fall back to the existing skill-level
  difficulty-then-id order for that item pool — never an error, never a dead
  control.
- **FR-2 (missing state lazy-init).** IF a learner has no `StandardState` for
  a standard THEN state SHALL lazy-initialize per the unlock policy
  (first-in-curriculum-order standards unlocked, the rest locked); historical
  attempts SHALL NOT fabricate FSRS state (fresh-init; AP-6 posture).
- **FR-3 (starvation fallback).** IF no unlocked standard in the picked skill
  has a servable item THEN the pick SHALL fall back to untagged items of that
  skill, and IF nothing is servable THEN existing empty-pool behavior applies
  unchanged.
- **FR-4 (locked = not served).** WHILE a standard is locked THE practice
  scheduler SHALL NOT serve its tagged items (the step-by-step promise).
- **FR-5 (no re-lock).** IF a standard's mastery later decays below the
  unlock threshold THEN it SHALL remain unlocked (unlock is monotone — a
  ratchet, not a thermostat).
- **FR-6 (single writer, widened).** THE `Scheduler.review()` path SHALL be
  the sole writer of `StandardState` (FR-A2 extended): on review of a tagged
  item it updates BOTH the skill's FSRS card AND the standard's FSRS card;
  standard mastery = FSRS retrievability of the standard card.
- **FR-7 (two-level pick).** WHEN the scheduler picks within a skill THE pick
  SHALL prefer the weakest unlocked standard (unseen-first, then lowest
  mastery), tie-broken by `standard_id` asc, then the existing
  difficulty-then-id order within the standard — fully deterministic.
- **FR-8 (unlock rule).** WHEN a standard's mastery reaches the unlock
  threshold (named config constant, default 0.7 — numeric knob in scheduler
  config, not prose) THE next standard in curriculum order (band asc,
  `standard_id` asc) within that skill SHALL unlock.
- **FR-9 (composite unlock).** WHEN every standard of every skill is
  unlocked THE composite surfaces (timed-test route, composite practice
  entry) SHALL unlock; WHILE any standard remains locked those surfaces SHALL
  render a disabled/locked state with progress shown — disabled, never dead
  (FR-B5 posture), never a 404.
- **FR-10 (wire kernel).** THE wire kernel SHALL gain: `Standard`
  (`standard_id`, `name`, `app_skill`, `bands`), `StandardState`
  (`standard_id`, FSRS card fields mirroring `SkillState`, `mastery`,
  `unlocked`), and `TestItem.standard_id` (optional int 1–32 during
  migration). W1 purity, W6 snake_case, W7 Schema+Type co-export,
  checklist C in the PR.
- **FR-11 (both seams + parity).** BOTH `InMemoryEngineDb` AND
  `DrizzleEngineDb` SHALL implement `StandardState` persistence and the
  two-level pick, with table-driven behavioral tests on the fake seam, an
  ordering assertion on the Drizzle twin, and port-conformance coverage (P7);
  the live seam adds a Drizzle migration for the new table.
- **FR-12 (dashboard drill-down).** WHEN a learner opens a skill's card THE
  dashboard SHALL show per-standard rows (name from the D3 TS plane; mastery
  % / unseen / locked badge) via a new pure translator with table-driven
  tests (T1/T4); standard names/order come ONLY from the D3 plane (no
  duplicated lists).
- **FR-13 (determinism).** THE pick SHALL be deterministic: identical state →
  identical question (extends the existing determinism guarantees).

## 4. Data model / contracts

- Wire (`frontend/lib/wire/engine_entities.ts`): `Standard`, `StandardState`,
  `TestItem.standard_id?`. Frontend-local (ADR-0005); no Python mirror.
- DB: new `standard_states` table (Drizzle migration) + in-memory twin map.
- Config: `unlock_threshold` named constant with the scheduler's numeric
  knobs (config split rule — number in config, policy in prose).
- Unlock/curriculum order derivation: per skill, standards sorted band-asc
  then id-asc from the D3 plane.
- **Emitter seam (cross-spec):** D3 keeps `standard_id` corpus-side (Zod
  default-strip would silently drop it from served rows anyway). At D4 time,
  `scripts/emit_test_item_bank.py` (Phase B FR-12) adds `standard_id` to its
  row-field allowlist and the bank is re-emitted from the frozen corpus — the
  tag becomes wire-visible only once the schema declares it. One field, one
  re-emit; no re-promotion.

## 5. Invariants & security boundaries

- Frontend Ring only — Python layers untouched; architecture invariants #1–8
  unaffected. Frontend rules stressed: W1/W6/W7, A2 (adapters don't import
  each other), F3 (substrate swap discipline: adapters + composition root
  only), P7 (conformance), FR-A2 single-writer (widened, not broken: still
  exactly one writer).
- No live LLM anywhere; all new tests deterministic.
- ADR REQUIRED before implementation (wire kernel + new persistent entity +
  new product abstraction): Options must include the two gate-rejected
  alternatives (computed read-side; defer-unlock) and fresh-init vs backfill.

## 6. Edge cases

- **Single-standard skills** (s-org): unlock chain is trivial; composite
  unlock still requires its one standard unlocked.
- **Mid-session unlock:** unlock state is read at pick time; a flip during an
  active quiz applies from the NEXT pick (no mid-session reshuffle).
- **Bands non-contiguous** (standard 13: bands 1,3): curriculum order uses
  min(band) for ordering; a standard is one unlock unit regardless of bands.
- **Learner with legacy attempts:** fresh-init means their per-standard
  mastery starts unseen even where they've practiced — acceptable,
  documented; the alternative (backfill) is the ADR's rejected option.
- **All standards mastered but items missing for one** (coverage gap):
  unlock progression must not deadlock — FR-8's trigger is mastery, and
  mastery requires served items; a standard with zero tagged items is
  auto-unlocked (vacuous) and flagged by the D3 coverage report instead.
- **Untagged-only bank** (pre-D3 data): FR-1 fallback makes D4 a no-op
  functionally; drill-down shows all-unseen.

## 7. Non-functional requirements

Deterministic; zero LLM; pick complexity O(pool) unchanged in spirit;
reversible: new table + optional wire fields (revert = drop migration +
fields; monotone unlock state is discardable). Calendar-heavy: both seams +
wire + scheduler + dashboard + e2e — the initiative's longest track.

## 8. Test plan

| FR | Test | Layer | In CI? |
|----|------|-------|--------|
| FR-1/3 | fake-seam table-driven pick tests (untagged, starvation) | L1 vitest | yes |
| FR-2 | lazy-init unit tests (first unlocked, no fabricated FSRS) | L1 | yes |
| FR-4/5/7/8/13 | scheduler behavioral tables (locked-excluded, monotone unlock, weakest-pick order, threshold flip, determinism) | L1 | yes |
| FR-6 | single-writer test: only review() mutates StandardState (arch-style scan + behavioral) | L1 | yes |
| FR-9 | route/entry gating component tests (locked state renders disabled; unlock flips) + T2 e2e | L1 + e2e | yes / tiered |
| FR-10 | wire schema tests (parse/strip/shape, W7 exports) | L1 | yes |
| FR-11 | port conformance + Drizzle ordering assertion + migration smoke | L1/static | yes |
| FR-12 | translator table-driven tests (mastery %, unseen, locked) | L1 | yes |

## 9. Definition of Done

- [ ] ADR appended with Options: computed-read-side (rejected at gate),
      defer-unlock (rejected at gate), backfill (rejected), chosen design.
- [ ] All FRs red→green; frontend vitest + arch tests + `make check` green.
- [ ] Drizzle migration applied + documented; parity evidence for both seams.
- [ ] T2-tier e2e: a learner journey crossing an unlock boundary and seeing
      the composite surface unlock at full coverage.
- [ ] Checklist C (wire change) pasted in the PR.
