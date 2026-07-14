# Spec — Epic F: Progress screen (`/learn/progress`), bundled honest-trend (D3)

> SDD Stage 2 spec for the **final** PreAct parity epic. Brainstorm (Stage 1):
> [preact-parity-epic-F.brainstorm.md](preact-parity-epic-F.brainstorm.md).
> Direction gated 2026-07-12: **BUNDLED (one epic) × D2 (`progress_screen_vm`
> single T1 translator) × D3 (honest-series trend from existing data) NOW;
> D4 (real projected-score write path + ACT score model) DEFERRED to a future epic.**

**Status:** Draft — 2026-07-13
**Owner:** Rajnish Khatri
**Related:** brainstorm (above) · design-spec `PreAct/UI-Design/design-spec.md` §5.7 · ADR-0028
(wired `ProgressRepo`/`TutorialRepo`) · ADR-0029 (mastery-from-stability, E1b) · E1b-D1
(accuracy read) · honesty precedent: `skill_detail_vm.ts` `accuracyStat` self-omit (E1a FR-16).

---

## 1. Goal

Ship `/learn/progress` — the prototype's "motivating long-term view" — as **one honest,
independently-releasable surface** for a learner on the ACT-English coach. It shows: a header
(streak + total items reviewed), a range toggle (30 days / All time), a **truthful trend line**
drawn from the learner's own closed-session history, and per-bucket mastery bars. The one part
that has no honest data source today — a **projected ACT score** — is a reserved slot that
**self-omits** until a future epic (D4) supplies a defensible score model. No number is fabricated.

This closes the six-epic parity program (A–E released 2026-07-12).

## 2. Context

- **The route 404s today.** `app/(coach)/learn/` has coach/quiz/skill/summary/test/feedback but
  no `progress/`. The `progress` nav item is `comingSoon: true` (`nav_model.ts:76`) yet already in
  `NAV_MEMBERSHIP` for desktop+ipad+iphone (`:104-106`) — so shipping = flip one boolean + build the page.
- **The read seam is already built (ADR-0028), and orphaned.** Epic E1a wired `ProgressRepo`
  (`ports/engine/progress_repo.ts`) end-to-end, but it has **zero product-code consumers** and its
  `ProgressPoint.projected_score` has **no honest write path** — the same gating risk we honored in
  Epic E (Tutorial content) and the tier-1 taxonomy defer. We will **not** consume `ProgressRepo` this
  epic (it stays dormant for D4); we do **not** forge a `projected_score`.
- **The honest data already exists, learner-wide, with no new read.** The product-facing port
  `SessionRepo.listByLearner(subject, learnerId, { sinceISO? })` (`ports/engine/session_repo.ts:41,80`;
  JSDoc: "returns closed sessions only, newest-first") returns `QuizSession[]`, each carrying `ended_at`
  (ISO ts), `score_correct`, `score_total`. It is already in the `EnginePortBag` (`composition_engine.ts:72`)
  and backed by `EngineDb.listClosedSessionsByLearner`. That single read yields **all three** dynamic
  pieces: the trend x-axis (`ended_at`), the per-session accuracy series (`score_correct/score_total`),
  and the running **items-reviewed total** (`Σ score_total`) — the header stat the brainstorm flagged as
  "no total exists" (P-i). The range toggle is `{ sinceISO }` (30-day, inclusive lower bound on
  `ended_at`) vs. omitted (all-time).
- **The static half is free re-composition.** `bucket_card_vm.ts` already emits per-bucket
  `masteryPct`+`accentVar`+`due` for all 6 buckets (Dashboard grid), now reading the ADR-0029
  corrected mastery signal. `streak_vm.ts` `toStreakVM(closedSessions, nowISO)` already computes the
  streak (StreakTile, Epic C). Both feed the new page unchanged.
- **No charting library exists** (recharts/d3/visx/chart.js/nivo all absent from `package.json`, by
  policy — native Intl + hand-built SVG). The trend line is a **genuinely new hand-built SVG polyline**
  (the brainstorm's P-f confirmed no SVG polyline exists anywhere yet). `AccuracyBars.tsx` is the a11y
  *labeling* template (it is **div-based**: `role="group"` wrapper + per-bar `role="img" aria-label`),
  not an SVG template — the polyline geometry is new, but its accessible fallback follows the same
  per-element-aria-label discipline.
- **Responsive:** design §5.7 — iPhone is "compact, sparkline + bucket bars (**no tabs**)"; iPad/desktop
  get the range tabs + full chart. Layout switches use Tailwind `@container`, not `useSurface`
  (project convention).

## 3. Functional requirements (EARS)

Failure/empty paths first (the honest-null discipline is the point of this epic).

### Honest-null & anti-fabrication (write these first)

- **FR-1 (empty history).** IF the learner has **no closed sessions** in the active range THEN THE
  SYSTEM SHALL render the trend region as an **honest empty state** ("Not enough history yet") and
  SHALL NOT draw any line or invent data points.
- **FR-2 (single session).** IF the learner has **exactly one** closed session in range THEN THE
  SYSTEM SHALL render that single point (or the empty state) and SHALL NOT interpolate a slope,
  a "▲ since start" delta, or a second synthetic point.
- **FR-3 (no projected score — the gating invariant).** THE SYSTEM SHALL NOT display any projected
  ACT score, "goal N", or "on track by <date>" text. The projected-score slot SHALL **self-omit**
  (render nothing) until a future epic supplies a real score model. No placeholder number, no `0`,
  no bucket-average stand-in is emitted. *(This is the AP-6 "don't fabricate a trust signal" rule.)*
- **FR-4 (no mastery data).** IF a bucket has no `SkillState` (mastery unknown) THEN THE SYSTEM SHALL
  render that bucket bar in its honest "no data" form — no `role="progressbar"`, no `aria-valuenow`,
  no fabricated 0% — gated on `BucketCardVM.masteryKnown`. A genuine measured mastery of 0 (a learner
  who has attempted and missed) is distinct and DOES render a real 0% bar. *(Implemented 2026-07-13:
  `bucket_card_vm.ts` carries `masteryKnown`; the guard test is
  `bucket_card_vm.test.ts::bucket_missing_mastery_is_honest_not_zero`. This supersedes the earlier
  "per `bucket_card_vm` today" wording, which described the pre-fix behavior that fabricated 0%.)*
- **FR-5 (dead-control ban).** THE SYSTEM SHALL flip `nav_model.progress.comingSoon` to `false`
  **only in the same change that ships the page** — the nav link SHALL NOT point at a 404 at any
  commit (Q-6/Epic-A dead-control class).

### Trend (the D3 honest series)

- **FR-6.** WHEN the Progress screen loads THE SYSTEM SHALL compute the trend series from
  `listClosedSessionsByLearner` for the active learner+subject, one point per closed session, ordered
  oldest→newest by `ended_at`.
- **FR-7.** THE SYSTEM SHALL plot **per-session accuracy** (`score_correct / score_total`, 0–100%) as
  the trend line's y-value. *(Series choice — see §Clarify Q1; spec default = accuracy.)*
- **FR-8.** WHILE the range tab is **"30 days"** THE SYSTEM SHALL include only sessions with
  `ended_at ≥ now − 30d` (via the read's `sinceISO`); WHILE **"All time"** THE SYSTEM SHALL include all
  closed sessions. Switching the tab SHALL update the line and the caption.
- **FR-9.** THE SYSTEM SHALL render the trend as a hand-built SVG polyline (no charting lib), with a
  visually-hidden accessible fallback (data table or `aria` description), mirroring `AccuracyBars.tsx`.

### Header + mastery (re-composition)

- **FR-10.** THE SYSTEM SHALL display a **total items-reviewed** count = `Σ score_total` over the
  closed sessions in the active range, computed in the translator (no new read; solves P-i).
- **FR-11.** THE SYSTEM SHALL display the learner's **streak** via the existing `toStreakVM`
  (unchanged), rendered in the header.
- **FR-12.** THE SYSTEM SHALL render **6 mastery-by-bucket bars** from the existing `bucket_card_vm`
  outputs (`masteryPct`, `accentVar`, `due`), reading the ADR-0029 corrected mastery signal.

### Composition & layering

- **FR-13.** THE SYSTEM SHALL compose the entire screen through **one pure T1 translator**
  `progress_screen_vm.ts` returning `ProgressScreenVM { header, trend, buckets }`, where each region
  degrades independently (honest-null per region, mirroring `skill_detail_vm.ts`). No I/O, no React,
  no SDK in the translator (Rules T1/F-R2).
- **FR-14.** THE SYSTEM SHALL keep all data reads at the composition boundary and the page/hook thin
  (F-R1 — no domain logic in the component); the projection/aggregation math lives in the translator.
  The seam mirrors the E1a Skill surface exactly: `progress/page.tsx` (`'use client'`) →
  `useProgressScreen({subject, learnerId, range})` → `const ports = useEngine()` →
  `loadProgressScreen(ports, …)` calling `ports.sessionRepo.listByLearner(…)` + the existing bucket
  reads → `progress_screen_vm(…)` → `<ProgressView vm={…}/>`. (`LEARNER_ID = "Garvit"`,
  `DEFAULT_SUBJECT`, per `skill/page.tsx`.)

## 4. Data model / contracts

**No new wire type. No new engine read. No new write path.** The epic is pure composition +
one translator + one view + one hand-built SVG primitive + one nav flip.

New **translator-local** types (in `translators/progress_screen_vm.ts`, not `wire/`):

```ts
export interface TrendPoint { readonly atISO: string; readonly accuracyPct: number; }  // 0..100
export interface ProgressTrendVM {
  readonly points: readonly TrendPoint[];   // oldest→newest; [] → empty state (FR-1)
  readonly range: "30d" | "all";
  // projectedScore is DELIBERATELY ABSENT until D4 (FR-3). No optional field to "fill later".
}
export interface ProgressHeaderVM {
  readonly itemsReviewed: number;            // Σ score_total in range (FR-10)
  readonly streak: StreakVM;                 // existing toStreakVM output (FR-11)
}
export interface ProgressScreenVM {
  readonly header: ProgressHeaderVM;
  readonly trend: ProgressTrendVM | null;    // null → whole trend region self-omits (FR-1 edge)
  readonly buckets: readonly BucketCardVM[]; // existing bucket_card_vm output (FR-12)
}
```

Translator inputs (all already-wired reads): `closedSessions: QuizSession[]`
(`listClosedSessionsByLearner`, range-filtered by `sinceISO`), `buckets: BucketCardVM[]`
(existing), `nowISO: string`. **`ProgressPoint` / `ProgressRepo` are intentionally not inputs** —
they stay dormant for D4.

Existing shapes consumed verbatim: `QuizSession` (`engine_entities.ts:203`, carries `ended_at`,
`score_correct`, `score_total`), `StreakVM` (`streak_vm.ts`), `BucketCardVM` (`bucket_card_vm.ts`).

## 5. Invariants & security boundaries

- **F-R1 (no domain logic in components):** the page is a thin server component → hook → view; the
  accuracy/items-reviewed/range math lives in the pure translator. ✔
- **F-R2 / T1 (no SDK in translators):** `progress_screen_vm.ts` imports only `wire/` + sibling VMs;
  no `langgraph`/SDK/`fetch`/`localStorage`. ✔
- **F-R8 (no SDK type escapes an adapter):** we add no adapter; reuse existing `SessionRepo`
  (returns `wire/` `QuizSession`). ✔
- **Honesty (AP-6, project-wide):** FR-3 is the load-bearing invariant — no fabricated projected
  score. This mirrors ADR-0021 (bank items earn `reviewed`), Epic E (Tutorial content gated), tier-1
  taxonomy defer. ✔
- **G1 (new-abstraction gate):** the SVG `TrendChart` primitive is built **inline in the Progress
  view first** (one consumer). It is promoted to a shared `components/` primitive only if a 2nd
  consumer (e.g. a Dashboard sparkline) lands in-scope — that promotion, if it happens, is a
  spec/PR-time call, not assumed here.
- **ADR posture: no ADR this epic.** Pure T1 translator + re-composition + hand-built primitive + one
  `comingSoon` flip = `decisions.md`-line weight. (D4 — the `insertProgress` write seam + ACT score
  model — is the ADR-bearing future epic; the psychometric P-k correctness question lives entirely there.)

## 6. Edge cases

- **Empty range but non-empty all-time:** 30-day tab empty while all-time has data → per-tab honest
  empty state; switching tabs recovers the line (FR-1 + FR-8).
- **Session with `score_total = 0`:** exclude from the accuracy series (division-by-zero guard) but it
  still can't inflate items-reviewed (adds 0). Do not plot a 0% point for a session nobody answered.
- **`ended_at` present, `started_at` only:** trend keys on `ended_at` (closed-session read already
  excludes `ended_at IS NULL`, ADR-0026) — no open sessions leak in.
- **All buckets mastery-unknown (brand-new learner):** bars render their honest no-data form; trend
  empty; items-reviewed = 0; streak = 0. The page is a truthful "you're just starting" state, not a 404.
- **iPhone surface:** no range tabs (design §5.7) → the series defaults to a single honest range
  (all-time sparkline); the `@container` layout hides the tab control, it is not merely visually
  collapsed into a dead control.
- **Single-point / two-point series:** polyline with <2 points draws no misleading slope (FR-2).

## 7. Non-functional requirements

- **Determinism:** the translator is L1-deterministic (same sessions + `nowISO` → same VM). No live
  LLM, no network in the render path. Range filter is a pure predicate on `ended_at`.
- **Reversibility:** additive route + one boolean flip; no migration, no engine write, no schema
  change. Fully revertible by deleting the route dir + reverting `nav_model.ts:76`.
- **Latency:** one existing indexed read (`listClosedSessionsByLearner`) + pure reduction; no N+1.
- **a11y (WCAG-AA):** SVG trend has a text/table fallback (FR-9); tabs are real `<button>`s; 44px
  targets; light+dark tokens (`on-*`) per the Phase-4 a11y baseline.

## 8. Test plan

Failure/empty-path tests first (they encode the honesty invariants). All L1 deterministic, all in
`make check` (frontend vitest). E2E is the smoke path.

| FR | Test | Layer | In `make check`? |
|----|------|-------|------------------|
| FR-1 | `progress_screen_vm.test.ts::empty_history_renders_empty_state_no_line` | L1 | yes |
| FR-2 | `progress_screen_vm.test.ts::single_session_no_synthetic_slope` | L1 | yes |
| FR-3 | `progress_screen_vm.test.ts::vm_has_no_projected_score_field` (type + runtime: no score/goal keys) | L1 | yes |
| FR-4 | `bucket_card_vm.test.ts::bucket_missing_mastery_is_honest_not_zero` (+ view guards: `BucketCard.test.tsx` / `ProgressView.test.tsx` "no data, not a 0% bar") | L1/L2 | yes |
| FR-5 | `nav_model.test.ts::progress_not_comingSoon` + e2e route-200 (no dead control) | L1+e2e | yes |
| FR-6/7 | `progress_screen_vm.test.ts::trend_points_oldest_first_accuracy` (table-driven) | L1 | yes |
| FR-8 | `progress_screen_vm.test.ts::range_30d_filters_by_sinceISO` / `all_time_includes_all` | L1 | yes |
| FR-9 | `TrendChart.test.tsx::renders_polyline_and_a11y_fallback` | L1 | yes |
| FR-10 | `progress_screen_vm.test.ts::items_reviewed_sums_score_total_in_range` | L1 | yes |
| FR-11 | `progress_screen_vm.test.ts::streak_forwarded_from_toStreakVM` | L1 | yes |
| FR-12 | `progress_screen_vm.test.ts::six_bucket_bars_from_bucket_card_vm` | L1 | yes |
| FR-13 | translator purity asserted by `test_frontend_layering.ts` (no SDK/React import) | arch | yes |
| all | `e2e/learn/validate_epic_f_progress.spec.ts` — nav→/learn/progress renders, tab toggle, axe clean | e2e | smoke |

**Nav-flip landmine — two tests invert the instant the flip lands (from [[preact-epic-e1a-stale-nav-tests]]):**
1. `components/shell/AppNav.test.tsx:27` — `"iPhone: coming-soon Progress renders as a disabled non-link"`
   asserts Progress has `aria-disabled="true"`, is not an `<a>`, no `href`. **Must be rewritten** to assert
   Progress is now a live `<a href="/learn/progress">` (mirror the E1a `skill` conversion at
   `nav_model.test.ts:111` `"skill screen is live (not comingSoon)"`).
2. `components/shell/nav_model.test.ts:82` — the wired-routes snapshot
   (`SCREENS.filter(s => !s.comingSoon).map(s => s.route)`) **gains** `/learn/progress`; update the
   expected list. The generic invariant at `:57-67` (disabled ⇔ comingSoon) stays valid unchanged.

Run the **full** vitest, not just the new suites — "green per-suite ≠ green branch." Reconcile every test
the flip touches in the same change.

## 9. Definition of Done

- [ ] All FRs implemented; each has a test **seen to fail first** (red→green).
- [ ] `progress_screen_vm.ts` is a pure T1 translator (no SDK/React/I-O); `TrendChart` built inline.
- [ ] `nav_model.ts:76` `comingSoon: true→false` **in the same change** as the page; no dead control at any commit.
- [ ] **Full** frontend vitest green (not per-suite) + `test_frontend_layering.ts` green.
- [ ] E2E smoke: `/learn/progress` renders, range toggle works, `@axe` clean, iPhone surface hides tabs (no dead control).
- [ ] **FR-3 verified:** grep the built VM/DOM for any "projected"/"goal"/score number → none. `ProgressRepo` remains unconsumed.
- [ ] `docs/adr/decisions.md` line added (no ADR); brainstorm + this spec cross-linked.
- [ ] Actual command output pasted (not summarized) for the vitest + e2e claims.

---

## Clarify — open sub-decisions (surfaced, not silently defaulted)

The Stage-1 gate left two sub-decisions open (user dismissed them 2026-07-12 as safe-defaultable).
The spec **leans** below; both are confirm-at-spec-gate, not blockers.

- **Q1 — trend series.** Per-session **accuracy** over time (spec default, FR-7) vs. **cumulative
  items-reviewed** over time vs. **both** (accuracy line + items as a range-toggled alternate). All
  three come from the *same* `QuizSession` rows at zero extra read cost. **Lean: accuracy is the
  "trend"; items-reviewed is the header stat (FR-10)** — one line, one number, cleanest first cut.
- **Q2 — reserved projected-score slot.** Visible "coming soon" placeholder card vs. **self-omit
  entirely** until D4. **Lean: self-omit (FR-3)** — matches the `accuracyStat` `return null` precedent
  (`skill_detail_vm.ts:383`); a "coming soon" card on the flagship screen reads as an unfinished
  promise, whereas self-omit reads as a complete, honest surface.

> Both leans are encoded as the default FRs above. Confirming them at the plan gate (or overriding)
> is the only decision needed before decomposition.
