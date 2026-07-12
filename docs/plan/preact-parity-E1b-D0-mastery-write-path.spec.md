---
title: 'E1b-D0 — Dashboard mastery write-path fix (wrong answers must not raise mastery)'
type: spec
sub_epic: E1b
direction: D0
status: Approved — 2026-07-12
owner: Rajnish Khatri
derives_from: docs/plan/preact-parity-epic-E1b.brainstorm.md
related:
  - docs/plan/preact-learn-followups.notes.md   # §F1 root-cause trace
  - frontend/lib/adapters/engine/scheduler/fsrs_scheduler.ts  # the write path
  - frontend/lib/translators/bucket_card_vm.ts   # the passive display VM
  - frontend/lib/translators/focus_pick.ts        # co-inheritor of the same field
governs:
  - docs/plan/preact-parity-E1b-D0-mastery-write-path.plan.md
  - docs/plan/preact-parity-E1b-D0-mastery-write-path.tasks.md
adr_trigger: 'YES — changes what a durable stored signal (SkillState.mastery) MEANS. New ADR (write-path semantics) or a decisions.md entry if judged minor. Ratchet: scheduler path change needs docs/adr/* or ADR-OK: waiver.'
---

# E1b-D0 — Dashboard mastery write-path fix

> **Clarify correction (2026-07-12).** The E1b brainstorm framed D0 as a *label/footnote
> guard* on `bucket_card_vm`. The clarify pass **refuted** that framing: the F1 root-cause
> trace + code prove the "100% mastery after all-wrong answers" report is a **write-path
> bug**, not a display bug. The dashboard renders faithfully. Human gate 2026-07-12:
> **fix the write-path**, deriving displayed mastery from **`fsrs_stability`** (which
> correctly collapses on a wrong answer), not instantaneous retrievability-at-review.

## 1. Goal

A learner who answers a skill's items **wrong** must never see their displayed **mastery
go up**. Fix the FSRS write path so the durable `SkillState.mastery` signal reflects
*competence* (stability-derived), not the forgetting-curve retrievability evaluated at the
review instant (which is ~1.0 at elapsed≈0 regardless of correctness). For every learner
on `/learn` and the today-focus/summary pick that reads the same field.

## 2. Context

**The bug (verified + reproduced, F1 note lines 29–60):**
- `Scheduler.review(attempt)` is the **sole** `skill_state` writer, called live on **every**
  grade — right or wrong ([`fsrs_scheduler.ts:194`](../../frontend/lib/adapters/engine/scheduler/fsrs_scheduler.ts:194)).
- It stores `mastery = this.retrievability(card, reviewedAt)`
  ([`fsrs_scheduler.ts:299`](../../frontend/lib/adapters/engine/scheduler/fsrs_scheduler.ts:299)).
  `get_retrievability` on the forgetting curve at **elapsed ≈ 0** is **~1.0** no matter how
  far `stability` has collapsed — so every grade overwrites `mastery ≈ 1.0`.
- A wrong answer is `Rating.Again` ([`fsrs_scheduler.ts:185`](../../frontend/lib/adapters/engine/scheduler/fsrs_scheduler.ts:185)),
  which **correctly collapses `stability`** (reproduced: 5 wrong → 0.212 → 0.083 → 0.035 →
  0.015 → 0.007) — the wrongness *is* tracked in `fsrs_stability`, just not surfaced in `mastery`.
- The header comment ([`fsrs_scheduler.ts:27-29`](../../frontend/lib/adapters/engine/scheduler/fsrs_scheduler.ts:27))
  already claims the *intended* behavior ("a freshly-failed card has low stability → low
  mastery") — the code diverges from its own contract.
- Passive, correct display: [`bucket_card_vm.ts:42`](../../frontend/lib/translators/bucket_card_vm.ts:42)
  `masteryPct: Math.round(mastery * 100)` → [`BucketCard.tsx:85`](../../frontend/components/dashboard/BucketCard.tsx:85).

**Blast radius — the same field is read by the weakest-skill pick:**
[`focus_pick.ts:31`](../../frontend/lib/translators/focus_pick.ts:31) sorts by
`a.mastery - b.mastery`. A skill you are failing looks mastered → drops OUT of "today's
focus." Fixing the stored `mastery` fixes the dashboard card AND the focus/summary pick in
one write-path change (class-over-instance).

**Test gap that let it ship:** [`fsrs_scheduler.test.ts:151`](../../frontend/lib/adapters/engine/scheduler/fsrs_scheduler.test.ts:151)
only asserts `mastery ∈ [0,1]` after a **single** review — never *direction*, never the
"many consecutive wrong in one session" scenario. A red-first direction test is the entry point.

**Constraint:** `fsrs_stability` is an **unbounded positive** quantity ("interval in days
when R=90%", ts-fsrs `index.d.ts:198`). Mapping it to a 0..1 mastery needs a **monotone
squash** (e.g. `s/(s+k)`), not a clamp — the map choice is a §clarify decision below.

## Clarify resolutions (2026-07-12, pre-plan)

- **Signal source = FSRS stability (human gate).** Displayed mastery is derived from
  `fsrs_stability`, not `retrievability(card, reviewedAt)`. Stays inside the scheduler; adds
  no new read (contrast D1's accuracy read). Rejected: rolling-correctness (that IS D1's
  accuracy read — would collapse the mastery/accuracy distinction D7 deliberately keeps).
- **OPEN → resolve in this spec's plan gate: the exact stability→mastery map.** Candidates:
  (i) `m = s/(s+k)` for a tuned half-life `k` (days), monotone, smooth, bounded; (ii) a
  capped linear `min(1, s/S_max)`; (iii) reuse `get_retrievability` but evaluated at a **fixed
  horizon** (e.g. R at `due_at`/at a standard elapsed) rather than at review instant. The
  acceptance test asserts **direction + monotonicity**, so it holds for any monotone map;
  the plan picks the map + constant with a one-line rationale (small enough for `decisions.md`).
- **Scope = the stored `mastery` field only.** `fsrs_stability`, `fsrs_difficulty`, `due_at`,
  scheduling behavior, and question selection (`Scheduler.next`, FR-13 purity) are **unchanged**.
- **Migration of existing rows:** the fix is forward-only — the next `review()` per skill
  rewrites `mastery` correctly. Stale pre-fix rows self-heal on next grade. No backfill migration
  (a backfill would be a separate ADR; called out, not in scope).

## 3. Functional requirements (EARS)

Failure paths first.

- **FR-1 (unwanted).** IF a learner submits **N consecutive wrong answers** for a skill in one
  session THEN THE SYSTEM SHALL NOT let the skill's displayed `mastery` **increase** across
  those grades (each wrong grade leaves mastery ≤ its prior value). *(The core bug.)*
- **FR-2 (unwanted).** IF `fsrs_stability` has collapsed toward 0 (repeated `Rating.Again`)
  THEN THE SYSTEM SHALL store a `mastery` that trends **toward 0**, never pinned near 1.0.
- **FR-3 (event-driven).** WHEN `Scheduler.review(attempt)` writes `SkillState` THE SYSTEM
  SHALL compute `mastery` as a **monotone-increasing function of `fsrs_stability`** (higher
  stability ⇒ higher-or-equal mastery), evaluated deterministically (no dependence on the
  wall-clock review instant).
- **FR-4 (event-driven).** WHEN a learner answers a skill's items **correctly** over a session
  THE SYSTEM SHALL let displayed `mastery` **rise** (a correct-streak increases stability ⇒
  increases mastery) — the fix must not invert the signal.
- **FR-5 (ubiquitous).** THE SYSTEM SHALL keep `mastery` in the closed range **[0, 1]** for all
  finite `fsrs_stability ≥ 0` (the `bucket_card_vm` × 100 render and `focus_pick` sort assume it).
- **FR-6 (ubiquitous).** THE SYSTEM SHALL leave `Scheduler.next()` question selection, `due_at`,
  `fsrs_stability`, and `fsrs_difficulty` **byte-for-byte unchanged** (only the `mastery`
  projection changes) — no regression to FR-13 serving purity or the S3 bounded-session behavior.
- **FR-7 (state-driven).** WHILE a skill has **no `SkillState`** (brand-new learner) THE SYSTEM
  SHALL continue to report `masteryPct = 0` and not-due (the existing `bucket_card_vm.ts:34`
  placeholder path is preserved).

## 4. Data model / contracts

- **No schema change.** `SkillState.mastery` stays `z.number() // 0..1`
  ([`engine_entities.ts:259`](../../frontend/lib/wire/engine_entities.ts:259)). Only the value
  *written* changes. `fsrs_stability` already persisted ([`fsrs_scheduler.ts:301`](../../frontend/lib/adapters/engine/scheduler/fsrs_scheduler.ts:301)).
- **Changed behavior:** `fromCard()` ([`fsrs_scheduler.ts:288-303`](../../frontend/lib/adapters/engine/scheduler/fsrs_scheduler.ts:288))
  sets `mastery` via a new pure `masteryFromStability(stability)` helper instead of
  `retrievability(card, reviewedAt)`. `retrievability()` may remain for internal scheduling use
  if still referenced; if it becomes dead, remove it (no orphan).
- **No wire/BFF/middleware change** — `mastery` is already on `SkillState`; consumers unchanged.

## 5. Invariants & security boundaries

- **Frontend Ring layering** — change is confined to `adapters/engine/scheduler/` (SDK/ts-fsrs
  isolation stays in the adapter, F-R8). `bucket_card_vm`/`focus_pick` (T1 translators, pure) are
  **untouched** — they keep rendering whatever `mastery` holds; correctness moves upstream to the writer.
- **Determinism (T1/L1):** `masteryFromStability` is a pure function of `stability` — no clock, no
  I/O — so the direction/monotonicity tests are L1 deterministic.
- **ADR trigger:** changing the meaning of a durable stored signal is an ⚠️ Ask-first-adjacent
  structural change on the scheduler path → **ADR** (or a `decisions.md` entry if the plan gate
  judges the map choice minor). `test_adr_ratchet.py` requires a `docs/adr/*` or `ADR-OK:` waiver
  for the scheduler-path change.

## 6. Edge cases

- **`stability = 0`** (freshly seeded, [`fsrs_scheduler.ts:211`](../../frontend/lib/adapters/engine/scheduler/fsrs_scheduler.ts:211))
  → `mastery = 0` (map must send 0↦0), not NaN.
- **Very large stability** (long correct streak) → `mastery → 1` asymptotically, never > 1 (FR-5).
- **Alternating right/wrong** → mastery tracks stability's actual trajectory (may rise then fall);
  FR-1 only forbids a *wrong* grade raising it, not monotone-global behavior.
- **Non-finite retrievability guard** (`fsrs_scheduler.ts:311`) → the new helper must keep an
  equivalent finite-guard for stability (defensive `Number.isFinite`).
- **Stale pre-fix `skill_state` rows** → self-heal on next `review()`; no crash reading them.

## 7. Non-functional requirements

- **L1 deterministic** — the whole change is testable without a live LLM or the clock. Nothing
  runs on the CI-forbidden live path.
- **Reversibility:** forward-only; a revert restores the old projection and the next grade rewrites.
- **Perf:** one arithmetic op per grade; negligible.

## 8. Test plan

Failure-path (FR-1/FR-2) before happy-path. All L1, all in `make check` (frontend vitest).

| FR | Test | Layer | In `make check`? |
|----|------|-------|------------------|
| FR-1 | `fsrs_scheduler.test.ts::N consecutive wrong answers never raise mastery` | L1 | yes |
| FR-2 | `fsrs_scheduler.test.ts::collapsed stability → mastery trends to 0 (not ~1)` | L1 | yes |
| FR-3 | `fsrs_scheduler.test.ts::mastery is monotone in stability, clock-independent` | L1 | yes |
| FR-4 | `fsrs_scheduler.test.ts::correct streak raises mastery` | L1 | yes |
| FR-5 | `fsrs_scheduler.test.ts::mastery ∈ [0,1] for stability 0..∞ (boundary)` | L1 | yes |
| FR-6 | `fsrs_scheduler.test.ts::next()/due_at/stability unchanged by the projection swap` | L1 | yes |
| FR-7 | `bucket_card_vm.test.ts::brand-new skill still 0% (existing, must stay green)` | L1 | yes |

> The FR-1 test is the **red-first entry point**: reproduce the F1 scenario (30 wrong grades),
> assert displayed mastery never increases and ends low — watch it **fail on the current
> `retrievability`-at-review code first**, then implement `masteryFromStability`.

## 9. Definition of Done

- [ ] FR-1..FR-7 implemented; FR-1/FR-2 tests **seen to fail first** on the old projection.
- [ ] `make check` green (frontend vitest + arch + typecheck).
- [ ] `focus_pick`/`today_focus` verified to now pick a failed skill as weakest (the inherited-bug fix).
- [ ] Scheduler serving behavior (FR-6) unchanged — S3 bounded-session + no-repeat suites still green.
- [ ] ADR appended (or `decisions.md` entry) for the stability→mastery map + constant; ratchet satisfied.
- [ ] Actual `vitest run` output pasted for the FR-1/FR-2 red→green transition.
