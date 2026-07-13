---
type: plan
title: "Epic F — Progress screen (/learn/progress): SDD Stage-1 brainstorm"
description: Premise audit + 6 candidate directions for the PreAct parity program's final epic — the long-term analytics screen (P-1…P-5). Central finding — the trend's data (projected_score) has no honest write path, exactly Epic E's Tutorial-content gating risk.
status: Draft — awaiting human direction gate
date: 2026-07-12
branch: feat/preact-parity-epic-F (to branch off main)
---

# Epic F — Progress screen — SDD Stage-1 brainstorm

The final increment of the PreAct prototype↔app parity program (epics A–E released
2026-07-12; see [preact-parity-epics.md](preact-parity-epics.md) and the release-program
memory). Epic F builds `/learn/progress` (design spec §5.7), the "motivating long-term
view" that today 404s. Findings `P-1…P-5`.

**Design source-of-truth:** `PreAct/UI-Design/design-spec.md` §5.7 (lines 200–206) + Component
Inventory rows "Trend chart" / "Mastery card" / "Range tabs" + prototype PNG
`docs/plan/assets/preact-parity-2026-07-09/proto/07-progress.png`. Regions (verbatim, §5.7):
header ("Your progress", `147 items · 9-day streak`) + range tabs · **projected-score trend
(line chart, `26 ▲ since start`, `goal 28`)** · mastery-by-bucket bars (each with % and Due
flag). States: range tabs **30 days / All time** switch the active tab, the trend caption, and
the trend line.

---

## 0. TL;DR — the one decision that matters

The epics-doc premise is **stale**: it lists F0 as "wire `listProgressPoints` + build the
`ProgressRepo`," but **Epic E1a already did that** (ADR-0028 wired `ProgressRepo` +
`TutorialRepo` together). The read seam is built, wired, and typed end-to-end — it just has
**zero product-code consumers** (a `.list()` with no caller).

What is *genuinely* missing splits into two very different risk classes:

- **The mastery-by-bucket half (P-1 streak, P-4 bars) is essentially free** — the data and even
  the translators already exist and already render on the Dashboard (`bucket_card_vm.ts`,
  `streak_vm.ts`). This is a re-composition, not a build.
- **The projected-score trend half (P-3, and P-1's "147 items reviewed") is gated on data that
  has no honest production source.** `ProgressPoint.projected_score` exists as a wire field and a
  DB column, but **nothing computes or writes it** outside test seeds — the exact same gating risk
  as Epic E's Tutorial content ("`getTutorial` returns null until content authored + write path
  built" → we refused to forge the `reviewed` stamp). The design spec even self-labels the number:
  *"projected 26 [is a] placeholder for a single-learner demo"* (`design-spec.md:295`).

So the real Epic-F fork is **not** "how do we draw a line chart." It is: **what is the honest
source of a projected ACT score, and do we build that now, degrade the trend gracefully until it
exists, or split the epic so the free half ships first?** Everything below serves that decision.

---

## 1. Premise-status table (audited against the working tree)

Every load-bearing premise from the epics doc + design spec, checked by a read-only `explore`
sweep (47 tool-uses) plus direct grep. `file:line` citations are verified (files opened).

| # | Premise (as stated in epics doc / spec) | Status | Evidence |
|---|------------------------------------------|--------|----------|
| P-a | "F0 = wire `listProgressPoints`; build `ProgressRepo` port + composition" | **REFUTED (already done)** | `ProgressRepo` port `frontend/lib/ports/engine/progress_repo.ts:18-21`; adapter `drizzle_progress_repo.ts:13-23`; wired `composition_engine.ts:87,151` + `composition_engine_browser.ts:53,130`. ADR-0028 §35-38: E1a's D5 wired **both** repos. |
| P-b | `listProgressPoints` is a real engine read (not a stub) | **VERIFIED** | Interface `engine_db.ts:176`; real impls `in_memory_engine_db.ts:390-398` (filters `this.progress`), `drizzle_engine_db.ts:687-702` (SQL + `toProgressPoint` map `:229-238`). |
| P-c | `ProgressPoint` carries trend data | **VERIFIED** | `engine_entities.ts:371-380`: `{id, subject, learner_id, at:string, projected_score:number, items_reviewed:int}`. Comment: "Sampled progress point for the trend line (UI spec FR-I1)." Timestamp + score both present → structurally sufficient. |
| P-d | The read seam has a UI consumer | **REFUTED (orphaned)** | Grep `progressRepo` across `components/` + `app/` = **0 hits**. Only callers are `composition_engine.test.ts:50-81` and `drizzle_progress_repo.test.ts`. It is wired-but-dead — a `.list()` with no reader. |
| P-e | **A projected-score write path / computation exists** | **REFUTED — the gating risk** | `seedProgress` is test-only (`in_memory_engine_db.ts:11,85`, called only from 2 test files). `insertProgress` **does not exist** on `ProgressRepo` (`drizzle_progress_repo.test.ts:66` `@ts-expect-error — no insertProgress`). No code computes `projected_score` for a real learner. Port JSDoc `:11`: "Progress rows are written by analytics/seed at the composition boundary, never through serving code." |
| P-f | A line-chart / trend primitive exists | **REFUTED (none)** | No charting lib in `frontend/package.json` (grepped recharts/visx/chart.js/d3/victory/nivo = 0). `AccuracyBars.tsx:4` is bars-only ("No external chart lib"). `QuizProgress.tsx` is a counter. No SVG polyline anywhere. |
| P-g | P-4 mastery-by-bucket bars need new data | **REFUTED (data exists)** | `bucket_card_vm.ts` already emits per-bucket `masteryPct` + `accentVar` + `due` for all 6 buckets (`:20-26`), rendered on the Dashboard grid. Design inventory: "Mastery card … dashboard grid + (bars) progress screen" — same component, two surfaces. |
| P-h | P-1 "9-day streak" needs new computation | **REFUTED (already computed)** | `streak_vm.ts:37` `toStreakVM(closedSessions, nowISO)` → `StreakVM`; rendered by `StreakTile.tsx` on the Dashboard rail (Epic C). `listClosedSessionsByLearner` now HAS a consumer (`drizzle_session_repo.ts:144` → `use_dashboard.ts:120,148`). |
| P-i | P-1 "147 items reviewed" (running total) is available | **REFUTED (no total)** | `items_reviewed` exists only **per ProgressPoint** (`engine_entities.ts:378`) and per `QuizSession` column (`schema.pg.ts:316`) — **no aggregate "total items reviewed" counter** in any translator/hook. `use_dashboard.ts:52` has `reviewMissesCount`, not this. |
| P-j | `/learn/progress` route 404s; nav item disabled | **VERIFIED** | Route dir absent (`app/(coach)/learn/` = coach/quiz/skill/summary/test only). `nav_model.ts:76` `progress` `comingSoon:true`; comment `:74` "Progress stays comingSoon until its surface ships." NOTE: `progress` **is already in `NAV_MEMBERSHIP`** for desktop+ipad+iphone (`:104-106`) — so P-5 = flip one boolean + build the page, NOT add membership (unlike Epic D's `skill` deferral). |
| P-k | ACT projected score = a simple average of 6 bucket masteries | **REFUTED (non-trivial)** | `research/act_english_bucket_weights_research.md:18-24`: the 6-bucket weights (`27/21/19/19/8/6`) are a "pedagogical flattening," NOT an ACT scoring taxonomy; official exam = 3 reporting categories on a 1–36 scale. A faithful 1–36 projection is a real modeling choice, not an arithmetic mean. |

**Net:** 3 VERIFIED, 8 REFUTED. The epics doc materially under-counts what Epic E already
delivered and over-counts P-4/P-1's difficulty — while the ONE thing it hedges ("a projection
series … may not exist") is the true blocker. Re-posing the corrected space below.

---

## 2. Corrected framing (what Epic F actually is)

Epic F is **two independently-shippable halves joined only by a shared route shell**:

1. **Half A — "Progress-lite" (mastery + streak).** Route shell + `comingSoon:false` flip + a
   `progress_screen_vm` that RE-COMPOSES existing VMs (`bucket_card_vm` bars for P-4, `streak_vm`
   for P-1's streak) + a mastery-bars view (the design "Mastery card" bars variant). **No new
   engine read, no new data, no charting.** This is the honest, buildable-today core. It even
   fixes a latent correctness win: `bucket_card_vm.masteryPct` now reads the E1b ADR-0029
   mastery-from-stability signal, so the bars show the *corrected* mastery, not the old
   retrievability bug.

2. **Half B — "Score trend" (P-3 + P-1's items-reviewed + P-2 range tabs).** Needs (i) a
   projected-score **write/compute path** (the gating decision), (ii) a NEW hand-built SVG
   line-chart primitive (mirrors how `AccuracyBars.tsx` was hand-built), (iii) an items-reviewed
   total, (iv) the 30d/All-time range toggle driving the series. **Half B is where the whole
   epic's risk and ADR live.**

The `P-5` nav flip is do-regardless hygiene that must land **with Half A's page** (never before —
that's the Q-6/Epic-A dead-control class), and it's cheaper than Epic D's because membership
already includes `progress`.

---

## 3. Directions (3 high-probability + 3 exploratory)

Ranked lenses applied: **demand-side / degrade-gracefully** (D1, D3), **class-over-instance**
(the chart primitive + the "wired-but-orphaned read" pattern), **under-used signal** (the
`ProgressPoint` shape + `listClosedSessionsByLearner` are both built and unused).

### D1 (high-prob) — Two-sprint split: Progress-lite now, score-trend behind a write-path decision
- **Shape:** F1 = Half A (route + flip + re-composition of `bucket_card_vm`/`streak_vm` + mastery-bars
  view). F2 = Half B (projected-score source + SVG line primitive + range tabs + items-reviewed),
  gated on the P-e write-path decision. Mirrors Epic E's **N-2/N-5 "probe-first two-step"** exactly
  (E1a shipped the buildable half; E1b shipped the data-gated half once honest).
- **Follows:** the E1a→E1b release pattern; `bucket_card_vm.ts` re-use; program rule #4
  (independently releasable sprints).
- **Tradeoff:** ships user-visible value fast (the bars + streak are the bulk of the screen) without
  waiting on the score model. **What breaks if chosen:** the screen is "incomplete" vs the prototype
  until F2 — the trend card must self-omit or show an honest empty state (no fabricated line).
- **Invariant stressed:** none new; F-R1 (no domain logic in components — the projection math must
  live in a translator/analytics path, not the page).

### D2 (high-prob) — `progress_screen_vm` single-translator surface (mirror `skill_detail_vm`)
- **Shape:** one pure T1 translator `progress_screen_vm.ts` that takes the already-wired reads
  (`skillRepo.listSkills` + `learnerRead.listSkillState` for bars; `sessionRepo.listByLearner` for
  streak; `progressRepo.list` for the trend) and returns a `ProgressScreenVM` with `bars[]`,
  `header{streak, itemsReviewed|null}`, and `trend: {...} | null`. View renders honest-null per
  region. Directly parallels `skill_detail_vm.ts`'s honest-null block model.
- **Follows:** `skill_detail_vm.ts` (E1a) + `bucket_card_vm.ts` + `coach_surface_vm.ts` honest-null T1.
- **Tradeoff:** one clean composition seam, every region degrades independently; the trend renders
  iff `progressRepo.list()` is non-empty (which today = never, until D4/D5 supplies rows).
- **What breaks:** if the projection source lands later with a different shape, the VM's `trend`
  branch changes — but that's isolated to one translator. **Invariant:** F-R7 n/a (no events); pure
  translator (T1/T4 table tests).

### D3 (high-prob / demand-side) — Degrade-gracefully trend: derive an HONEST series from what exists, defer `projected_score`
- **Shape:** instead of a *projected ACT score* (which needs a model we don't have), draw the trend
  from **already-honest** data: per-session on-skill **accuracy over time** (E1b's `accuracyRowsBySkill`
  / `listClosedSessionsByLearner` both exist) OR **cumulative items-reviewed over time**. The line is
  real, sourced, and needs NO write path. `projected_score` + "goal 28" guide line become a **P2
  reserved slot** (annotated, not fabricated) until the score model is specced.
- **Follows:** the E1b accuracy read; the "reserved-slot, don't fabricate" pattern from E1a's
  accuracyStat self-omit; the demand-side default lens ([[demand-side-reduction-default-lens]] — make
  the expensive thing (a score model) not-needed first).
- **Tradeoff:** ships a *truthful* trend chart NOW with zero new data infra; the chart's semantics
  differ from the prototype ("accuracy trend" vs "projected score") — arguably MORE honest (the spec's
  own subtitle line reads "accuracy trend · mastery over time"). **What breaks:** deviates from the
  prototype's headline number; needs a product call that "accuracy/coverage trend" is an acceptable
  first-cut for "projected score."
- **Invariant:** none; but it's the direction that most respects the honesty discipline the whole
  program enforces (AP-6 no fabricated trust signals).

### D4 (exploratory) — Build the projected-score **analytics write path** now (ADR: `insertProgress` + a score model)
- **Shape:** add the write surface the port JSDoc anticipates ("written by analytics/seed at the
  composition boundary") — an `insertProgress`/`recordProgressPoint` seam + a deterministic
  score-projection function (FSRS mastery per skill × bucket weights → a 1–36 scaled projection,
  sampled at session close). Then the trend renders the real `projected_score`.
- **Follows:** the `Scheduler.review()` write-at-session-boundary precedent; `research/act_english_bucket_weights_research.md` for the weighting.
- **Tradeoff:** delivers the prototype faithfully. **What breaks / why it's exploratory:** this is a
  **⚠️ Ask-first ADR** (new write seam on the engine + a new scoring abstraction) AND a genuine
  psychometric modeling question — P-k shows a naive weighted-average is *not* a valid ACT projection
  (3 official categories, 1–36 curve, "pedagogical flattening"). Risk of shipping a **confidently
  wrong number** with a "goal 28 · on track by mid-March" promise attached — the highest-trust-stakes
  string in the app. Load-bearing cost here is **modeling correctness + calendar time to accumulate
  multi-session history**, not UI code.
- **Invariant stressed:** new abstraction (G1) + write seam; must earn its correctness the way ADR-0021
  made bank items earn `reviewed` (don't forge the projection).

### D5 (exploratory / class-over-instance) — Ship the reusable **`TrendChart` SVG primitive** as the deliverable, data-agnostic
- **Shape:** treat the missing line-chart primitive as the class-level gap (it will be needed again:
  sparklines on Dashboard, accuracy trends on Skill). Build one accessible `TrendChart.tsx`
  (SVG polyline + optional dashed guide line + range-driven data + a11y table fallback, WCAG-AA,
  CSP-safe, theme-aware) with Storybook stories, and feed it whatever series D3/D4 decides. P-3 becomes
  "wire the chosen series into the primitive."
- **Follows:** `AccuracyBars.tsx` as the hand-built-primitive template; the design inventory "Trend
  chart = SVG polyline + goal guide line."
- **Tradeoff:** the reusable win + unblocks any series choice. **What breaks:** a primitive with no
  live data is over-abstraction risk (G1) if D3/D4 stall — must land WITH a real consumer, not ahead
  of one (same lesson as the wired-but-orphaned `ProgressRepo`).
- **Invariant:** G1 (justify the abstraction — it clears the "≥2 consumers" bar only if Dashboard
  sparkline is also in scope; otherwise build it inline in the Progress view first).

### D6 (exploratory) — WON'T-DO-the-trend: Progress screen = mastery + streak only, formally defer the entire trend
- **Shape:** ship Half A as the *complete* Epic F; move P-2/P-3 (range tabs + projected trend) to a
  named follow-up initiative ("score-projection analytics") the way tier-1 taxonomy was deferred out
  of E1b with a readiness verdict. Close the parity program with an honest "trend deferred, data not
  ready" marker rather than a fabricated line.
- **Follows:** the tier-1 taxonomy DEFER precedent (ship the honest half, gate the rest on a real
  signal); [[preact-tier1-taxonomy-brainstorm]].
- **Tradeoff:** the parity program closes cleanly and truthfully today; the flagship "motivating
  long-term view" is only half-there. **What breaks:** the prototype's most emotionally-central screen
  (the rising line to "goal 28") is the part we'd cut — arguably the wrong half to drop for a
  motivation screen. Best only if the score model is judged out-of-reach.
- **Invariant:** none; it's a scope decision.

---

## 4. Dependency structure + do-regardless

- **Do-regardless hygiene (no ADR, ship in F1 with Half A):** route shell `app/(coach)/learn/progress/page.tsx`;
  `nav_model.ts:76` `comingSoon:true→false`; the `progress` nav item already IN `NAV_MEMBERSHIP` so no
  membership edit; reconcile any nav-absence test the flip breaks (the E1a lesson —
  [[preact-epic-e1a-stale-nav-tests]] — run FULL vitest, `AppNav.test.tsx` + any e2e absence guard).
- **Sequenced:** Half B's trend (D3/D4/D5) depends on the **projected-score-source decision** (the
  spec's first job). Half A (D1/D2) depends on nothing new → can ship first and alone.
- **Independent-parallel:** the `TrendChart` primitive (D5) is independent of the *data* choice but must
  not merge without a consumer.
- **Cost axes:** Half A = pure engineering time (small). Half B/D4 = **modeling correctness + calendar
  time** (multi-session history must accumulate before a trend is even visible for a real learner) —
  the load-bearing cost is the wait + the psychometric call, not the code.

---

## 5. Leading recommendation → GATE DECISION (human, 2026-07-12)

**Recommended:** D1 (split) × D2 × D3, defer D4.
**CHOSEN AT GATE:** **BUNDLED (one epic, NOT split) × D2 (`progress_screen_vm`) × D3 (honest-series
trend) NOW; D4 (real projected-score write path + model) DEFERRED to a future epic.**

Reconciliation — bundled + D3 is fully consistent and needs **no ⚠️ Ask-first ADR**:

- Bundled means the **whole D3 screen ships in one pass**: header (streak + a real items-reviewed
  total) + range tabs (30d/All-time) + honest SVG trend line + 6 mastery bars + the P-5 nav flip.
  Because D3 carries no new engine write, there is no data-decision predecessor to gate a second
  sprint on — so the two-sprint split (D1) that the recommendation used to de-risk the write path is
  unnecessary. Bundling is the right call *given D3*.
- The trend line is drawn from **already-honest, already-built** data (per-session accuracy via
  `accuracyRowsBySkill` / `listClosedSessionsByLearner`, and/or cumulative items-reviewed over time) —
  no `projected_score`, no `insertProgress`, no forged number.
- The prototype's **"projected score 26 / goal 28 / on track by mid-March"** headline + guide line
  become a **reserved, annotated-empty slot** (the E1a accuracyStat self-omit pattern), NOT fabricated.
  D4 fills that slot later as a properly-ADR'd, correctness-gated addition (the psychometric P-k call +
  the `insertProgress` write seam live entirely in that future epic).

Net ADR posture: **decisions.md-line weight, no ADR-0031 this epic** (pure T1 translator + hand-built
`TrendChart` SVG primitive + re-composition of existing VMs + one `comingSoon` flip). If review escalates
the chart primitive to a shared/reused abstraction (G1, ≥2 consumers), that becomes a spec-time call — but
default is build-inline-with-its-consumer.

This closes the parity program on its own terms: **one independently-releasable, fully honest surface**,
with the single genuinely-hard part (a defensible ACT-score projection) named as future work, not faked.

**Two sub-decisions the gate left OPEN (dismissed 2026-07-12) — sdd-spec must surface, not silently default:**
(1) exact honest-trend series (per-session **accuracy** over time vs **cumulative items-reviewed** vs both,
range-toggled); (2) whether the reserved projected-score slot renders as a visible "coming soon"-style
placeholder or **self-omits entirely** until D4. Both are safe-default-able (spec leans: accuracy-series +
self-omit) but should be confirmed at the spec gate.

---

## 6. Open questions for the human direction gate

Posed as orthogonal tracks (pick per axis; a bare "yes" is not multi-option consent):

- **HG-1 (split):** D1 two-sprint (Half A now, Half B behind data) vs one bundled epic? *(recommend D1.)*
- **HG-2 (trend data source) — the real fork:** D3 honest-series-now (accuracy/items over time) ·
  D4 build-the-projected-score-write-path-now (ADR + score model) · D6 defer-the-whole-trend. *(recommend D3.)*
- **HG-3 (chart primitive):** build `TrendChart` inline in the Progress view (D5-lite, ships with its
  consumer) vs as a shared primitive now (D5, needs a 2nd consumer to clear G1)? *(recommend inline-first.)*
- **HG-4 (projected_score, if HG-2≠D4):** render the trend card with the P2-reserved "projected score /
  goal" slot annotated-empty, or omit the card entirely until the score model lands? *(recommend reserved slot.)*
- **HG-5 (items-reviewed P-1):** compute a real running total (new small aggregation over sessions) now,
  or self-omit "147 items reviewed" until Half B? *(depends on HG-1; recommend compute-with-Half-A if cheap.)*

**ADR note:** only **D4** trips an ⚠️ Ask-first ADR (write seam + score-projection abstraction). D1/D2/D3
are decisions.md-line weight (re-composition + a pure translator + a hand-built primitive) unless review
escalates. Next free ADR = **0031**.

---

## 7. Cross-references

- Program: [preact-parity-epics.md](preact-parity-epics.md) · release-program memory.
- Epic E precedent (the twin gating pattern): [preact-parity-epic-E.brainstorm.md](preact-parity-epic-E.brainstorm.md),
  ADR-0028 (wired `ProgressRepo`), [[preact-epic-e-readiness]], [[preact-epic-e1b-brainstorm]].
- Honesty discipline: [[preact-tier1-taxonomy-brainstorm]] (defer-on-readiness), [[demand-side-reduction-default-lens]],
  [[preact-dashboard-mastery-retrievability-bug]] (mastery source now = ADR-0029 stability, good for the bars).
- Nav-flip landmine: [[preact-epic-e1a-stale-nav-tests]] (full vitest, not per-suite).
- Score model input: `research/act_english_bucket_weights_research.md` (weights are a flattening, not ACT scoring).
