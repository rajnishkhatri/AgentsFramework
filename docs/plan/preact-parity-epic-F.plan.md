# Plan — Epic F: Progress screen (`/learn/progress`), bundled honest-trend (D3)

> SDD Stage 3 (plan + checklist + atomic tasks). Derives from
> [preact-parity-epic-F.spec.md](preact-parity-epic-F.spec.md) (14 EARS FRs, gated
> 2026-07-13: accuracy series + self-omit score slot + advance).
> Stage 1 brainstorm: [preact-parity-epic-F.brainstorm.md](preact-parity-epic-F.brainstorm.md).

**Status:** Draft — 2026-07-13 · **Owner:** Rajnish Khatri

---

## 1. Architecture — where each piece lands

The epic is **pure composition**: one new translator, one new view, one new inline SVG primitive,
one new page, one new hook, one nav-flip, and their tests. No new wire type, no new port, no new
adapter, no engine write, no migration, no dependency. It mirrors the E1a Skill surface seam exactly.

```
app/(coach)/learn/progress/page.tsx      NEW  'use client' → useProgressScreen({subject,learnerId,range}) → <ProgressView/>
components/learn/use_progress_screen.ts   NEW  useEngine() → loadProgressScreen(ports,…) → ProgressScreenVM   (mirror use_skill_detail.ts)
components/learn/ProgressView.tsx          NEW  renders header (streak + itemsReviewed) · <RangeTabs> · <TrendChart> · 6 bucket bars
components/learn/TrendChart.tsx            NEW  hand-built SVG polyline + div/table a11y fallback (INLINE — G1: one consumer)
lib/translators/progress_screen_vm.ts      NEW  PURE T1: (closedSessions, buckets, nowISO, range) → ProgressScreenVM   (mirror skill_detail_vm honest-null)
components/shell/nav_model.ts              EDIT :76 comingSoon: true → false          (the flip)
```

**Reads (all already wired in `EnginePortBag`, `composition_engine.ts`):**
- `ports.sessionRepo.listByLearner(subject, learnerId, { sinceISO? })` → `QuizSession[]` (trend + items + streak).
- Bucket path — the exact reads `use_dashboard.ts:143-164` already uses: `ports.skillRepo` (skill list)
  + `ports.learnerRead.listSkillState(subject, learnerId)` → build `stateBySkill` Map →
  `skills.map(s => toBucketCardVM(s, stateBySkill.get(s.id) ?? null, nowISO))`. **Reuse this composition
  verbatim; do not re-derive it.** (Factor the shared bucket-build if clean, else duplicate the 3 lines.)
- `ports.progressRepo` is **left unconsumed** (dormant D4 seam).

**Data flow (one pass, all deterministic):**
```
listByLearner(range→sinceISO) ─┐
                               ├─► progress_screen_vm ─► ProgressScreenVM ─► ProgressView
skill list + SkillState ───────┘        (pure T1)         { header, trend, buckets }
      │
toBucketCardVM ×6 (existing) ──────────────────────────────────┘
toStreakVM (existing) ─────────────────► header.streak
```

## 2. Translator design (`progress_screen_vm.ts`) — the one seam that holds the logic

Pure function, imports `wire/` + sibling VMs only (Rules T1/F-R2). Signature:

```ts
export function toProgressScreenVM(inputs: {
  readonly closedSessions: readonly QuizSession[];   // range-pre-filtered by the loader (sinceISO)
  readonly buckets: readonly BucketCardVM[];         // existing toBucketCardVM output ×6
  readonly range: "30d" | "all";
  readonly nowISO: string;
}): ProgressScreenVM
```

Internal reductions (all L1-deterministic):
- **trend points:** map closed sessions → `{ atISO: ended_at, accuracyPct: round(100*score_correct/score_total) }`,
  **drop any session with `score_total === 0`** (div-by-zero guard, FR-6 edge), sort oldest→newest by `ended_at`.
- **empty/single guards:** `points.length === 0` → `trend.points = []` (view shows empty state, FR-1);
  `points.length < 2` → still emit the point(s) but the polyline draws no slope and no "since start" delta (FR-2).
- **itemsReviewed:** `Σ score_total` over the in-range closed sessions (FR-10). *(Uses all sessions, incl.
  the score_total===0 ones — they add 0, harmless.)*
- **streak:** call existing `toStreakVM(closedSessions, nowISO)` and forward `.days` (FR-11).
- **buckets:** pass through the 6 `BucketCardVM` unchanged (FR-12).
- **projectedScore:** **not computed, not a field** — the `ProgressTrendVM` type has no such key (FR-3).

`trend` is `ProgressTrendVM | null`; return `null` only if the whole trend region should vanish
(design choice: with 0 sessions we still render header+buckets, so `trend` is a non-null VM with
`points: []` and the *view* renders the empty state — cleaner than nulling the region. `null` is
reserved for a future "no trend concept on this surface" case). → **encode as `points: []`, not `null`,
for empty history** (keeps the empty-state copy in the view, testable via FR-1).

## 3. Range handling — where the `sinceISO` boundary is computed

`nowISO` is passed in (determinism — no `Date.now()` in the translator). The **loader**
(`loadProgressScreen`, in the hook file, not the translator) computes `sinceISO` for the 30-day tab
as `new Date(now − 30d).toISOString()` and calls `listByLearner(..., { sinceISO })`; the all-time tab
omits `sinceISO`. The translator receives already-filtered sessions + the `range` label (for the
caption only). Tab state is transient UI (`useState` in the page/hook), re-triggering the load — same
`useEffect`-keyed pattern as `use_skill_detail.ts`.

## 4. TrendChart primitive (`TrendChart.tsx`) — inline, G1-compliant

- SVG `<svg viewBox>` with a single `<polyline points="…">` computed from normalized (x,y) over the
  point set; `<circle>` markers optional. Theme-aware stroke via `var(--color-*)` tokens; CSP-safe
  (no inline `style` with dynamic values that trip the nonce — use `className` + CSS vars).
- **a11y fallback** (mirrors `AccuracyBars.tsx`'s per-element-label discipline, adapted to a line):
  a visually-hidden `<table>` or an `aria-label` summarizing the series (e.g. "accuracy trend, N
  sessions, X% to Y%"), so the chart is not an unlabeled graphic (FR-9).
- **Built inline in `components/learn/`** with one consumer (ProgressView). Promotion to a shared
  `components/primitives/` chart is explicitly **out of scope** unless a 2nd consumer lands (G1).

## 5. Constitution check (AGENTS.md invariants + Frontend Ring F-R#)

| Invariant | How this plan holds it |
|-----------|------------------------|
| F-R1 no domain logic in components | math in `progress_screen_vm.ts`; page/hook/view are thin |
| F-R2 / T1 no SDK in translators | translator imports `wire/` + sibling VMs only |
| F-R8 no SDK type escapes adapter | no new adapter; reuse `SessionRepo` (returns wire `QuizSession`) |
| AP-6 no fabricated trust signal | FR-3 self-omit; `progressRepo` unconsumed; no forged score |
| G1 new-abstraction gate | TrendChart inline (1 consumer); promotion deferred |
| ADR ratchet | **no ⚠️ trigger** — no new dep, no new port, no new graph node, no trust-type change → **no ADR**; add a `docs/adr/decisions.md` 2–4 line entry |

**No `docs/adr/*` file required.** (D4 — `insertProgress` write seam + ACT score model — is the future
ADR-bearing epic; nothing in this plan touches that seam.)

## 6. Branch base (correction to brainstorm frontmatter)

Epic F depends on E1b's accuracy read (`6fcb9e9`) + ADR-0029, which are on the **Epic-E tip, not yet on
main** (8 commits ahead). Branch `feat/preact-parity-epic-F` from the **current Epic-E tip** (or from
main *after* Epic E merges) — **not** from main directly, or the mastery signal + accuracy plumbing
this epic re-composes will be absent.

---

## 6.5 Design tasks (visual / UX layer)

The data-composition tasks (§7 T1–T5) say *what data* renders; the design tasks say *what it looks
like*. The **central design fact:** the prototype (`proto/07-progress.png`) is dominated by the
projected-score treatment — a big "26 · ▲ +2 since start · Goal 28 · on track by mid-March" left column,
a dashed **goal-28 guide line**, a "goal 28" label, and a rising line pointed at that goal. **FR-3 deletes
all of that.** So the design work is NOT "reproduce the prototype" — it is **"design the honest trend card
that remains once the projected-score scaffolding is removed."** That is a real redesign, decided here.

**Design source-of-truth:** `PreAct/UI-Design/design-spec.md` §5.7 + §6 Component Inventory (Mastery card
/ Range tabs / Trend chart rows) + §7 interactions (Range tabs row) + `proto/07-progress.png`. Base palette:
cream/charcoal/terracotta; **6 derived bucket accents** `--b-rhetoric #d87758 · --b-usage #c0863a ·
--b-punct #4f9d8b · --b-org #7a9450 · --b-struct #5b7fa6 · --b-concise #a06a93` (light) with dark variants;
footer rule: **"color never the only signal"** (WCAG-AA).

### What the prototype shows (verbatim, for the honest subset decision)
- **Header:** "Your progress" · subline `147 items reviewed · 9-day streak` · **range tabs** (30 days /
  All time) top-right, pill segmented control (DS `.tabs-list`/`.tabs-trigger`).
- **Trend card** (grey rounded panel): left = projected-score column *(→ FR-3 removed)*; right = an orange
  polyline with a dashed **goal-28** guide *(guide → removed with the goal)* and an endpoint dot.
- **"Mastery by bucket":** 6 rows — bucket dot + name (left), a track+fill **horizontal** bar (center),
  **% value** in the bucket accent + a `DUE` tag (right) on Rhetoric & Punctuation. *(This is the
  horizontal `.progress` idiom, distinct from the existing vertical `AccuracyBars`.)*

### DT — design task list

- **DT-1 — Trend-card honest redesign (the core design decision).** Define the card layout *without*
  the projected-score column, dashed guide, and goal label (FR-3). Options → §Design forks Q-D1. The
  card retains: a title/caption reflecting the honest series (spec §5.7 subtitle is literally
  *"Mastery over time · accuracy trend · due schedule"* — use **"Accuracy trend"**, NOT "projected
  score"), the line/series, and range-driven redraw. Specify: card padding, panel token
  (`--color-surface`/grey), line stroke = `--color-accent` (terracotta) or neutral, endpoint marker,
  axis/gridline treatment (the prototype has a faint baseline only — keep minimal).
- **DT-2 — Chart idiom fork (line vs. reuse existing bars).** The prototype shows a **line**; but
  `AccuracyBars.tsx` already renders "accuracy trend" as ≤6 vertical bars (E1b-D1, accessible, built).
  Decide: new SVG **polyline/sparkline** (matches prototype, arbitrary session count) vs. **reuse/extend
  `AccuracyBars`** (zero-net-new, but bars≠line and it caps at 6). → §Design forks Q-D2. Whichever wins
  becomes the T2 primitive's visual spec. Must be theme-aware (`var(--color-*)`), CSP-safe (no dynamic
  inline `style` values that need a nonce — the existing `AccuracyBars` uses inline `style` height %,
  acceptable pattern), and carry a non-color signal (markers/labels, per the footer rule).
- **DT-3 — Mastery-bar visual (horizontal `.progress` idiom).** The Progress screen bars are
  **horizontal** (track + accent fill + trailing %), unlike the Dashboard `BucketCard` layout. Decide:
  reuse `BucketCard` as-is (vertical card grid) vs. a horizontal **bar-row** variant matching the
  prototype's "Mastery by bucket" list. → §Design forks Q-D3. Each row: `--b-*` accent fill, % in the
  same accent, `DUE` badge (warning token) when `due`, name always present (color-independent).
- **DT-4 — Range tabs (segmented control).** DS `.tabs-list`/`.tabs-trigger` pill, 30 days / All time,
  active = filled white/surface pill on grey track (per prototype). Real `<button>`s, `role="tablist"`,
  44px targets, keyboard-navigable, focus ring. Drives line + caption (FR-8).
- **DT-5 — Empty / sparse states (design the honest-zero surface).** The prototype only shows the
  full-data state; FR-1/FR-2 need a *designed* empty state: 0 sessions → trend card shows
  "Not enough history yet — complete a few sessions to see your accuracy trend" (copy TBD), bars show
  their honest no-data form, header reads `0 items reviewed · 0-day streak`. 1 session → a single
  marker, no slope, no delta. This is a brand-new-learner's first honest screen, not an error.
- **DT-6 — Responsive (`@container`, per [[frontend-responsive-layout-container-queries]]).** Desktop/iPad:
  sidebar + range tabs + full chart. **iPhone: compact — sparkline + bucket bars, NO tabs** (design §5.7).
  The tab control is *removed by layout* on the narrow container (not a disabled dead control); the series
  defaults to all-time. Bars stack full-width. Use `@container` breakpoints, not `useSurface`.
- **DT-7 — Theme + a11y pass.** Light + dark for every token (the prototype header shows a Dark toggle);
  bucket accents re-resolve via `data-theme` (existing behavior). WCAG-AA contrast on the line, %, and
  DUE tag; **color never the only signal** (line has markers + an accessible text/table summary — the
  FR-9 fallback; DUE is a text badge, not just a color; % is a number). Verify with `@axe` (T6).

### Design forks — DECIDED AT GATE (human, 2026-07-13)

All three resolved to the faithful-to-prototype lean:

- **Q-D1 → (a) full-width line.** The trend card is a single full-width line spanning the panel, caption
  **"Accuracy trend"** top-left, range-scoped. **No left column** — nothing that could read as a stand-in
  for the deleted projected score. The projected-score column, dashed goal guide, "goal 28" label, and
  "since start" delta are all absent (FR-3).
- **Q-D2 → (a) new SVG polyline.** A hand-built SVG sparkline with per-point markers (the non-color
  signal), theme-aware stroke `var(--color-accent)`, arbitrary session count. Net-new `TrendChart.tsx`
  (T2). `AccuracyBars` is NOT reused (bars ≠ line; caps at 6) — but it remains the a11y-labeling template.
- **Q-D3 → (a) new horizontal bar-rows.** A "Mastery by bucket" list matching the prototype: each row =
  bucket dot + name (left) · track+accent fill (center) · **% in bucket accent** + `DUE` text badge
  (right). New horizontal bar-row component (or a horizontal variant), fed by the existing 6 `BucketCardVM`
  (data is free; only the row layout is new). NOT the vertical Dashboard `BucketCard` grid.

**Net:** the honest screen reproduces the prototype's subset faithfully — same rising accuracy story, same
6-bucket list — with only the (D4-deferred) projected-score furniture removed. T2 builds the SVG polyline;
T4 builds the header + range tabs + horizontal bar-rows + empty state.

---

## 7. Atomic task decomposition

Dependency-ordered. `[P]` = parallelizable with siblings at the same level. Each task names its files
and its 1:1 verification. **Red→green per task** (write the test, watch it fail, implement).

### T0 — Branch + baseline (do first)
- **T0.1** Branch `feat/preact-parity-epic-F` from the Epic-E tip (§6). Verify `.venv` symlink / repo
  interpreter per [[repo-venv-is-only-working-interpreter]] if a worktree.
- **T0.2** Baseline green: full frontend `pnpm vitest run` + `test_frontend_layering.ts` + `make check`.
  Record the counts — this is the "was green before" evidence for the nav-flip landmine.

### T1 — Translator (the core; no UI) — depends on T0
- **T1.1** Add types (`TrendPoint`, `ProgressTrendVM`, `ProgressHeaderVM`, `ProgressScreenVM`) +
  `toProgressScreenVM` skeleton in `lib/translators/progress_screen_vm.ts`. **No `projectedScore` key.**
- **T1.2** Write `lib/translators/progress_screen_vm.test.ts` **failure/empty first** — table-driven,
  one row per FR below; **watch them fail**, then implement §2 reductions to green.

  | Test | FR | Asserts |
  |------|----|---------|
  | `empty_history_renders_empty_state_no_line` | FR-1 | 0 sessions → `trend.points === []` |
  | `single_session_no_synthetic_slope` | FR-2 | 1 session → 1 point, no delta fabricated |
  | `vm_has_no_projected_score_field` | FR-3 | no `projected*`/`goal`/`score` key on `trend` (type + `Object.keys`) |
  | `score_total_zero_excluded_from_series` | FR-6 edge | session w/ `score_total=0` → not a trend point |
  | `trend_points_oldest_first_accuracy` | FR-6/7 | ordered by `ended_at` asc; y = `round(100*correct/total)` |
  | `range_label_forwarded` | FR-8 | `range` passed through to VM caption |
  | `items_reviewed_sums_score_total_in_range` | FR-10 | `Σ score_total` (incl. the 0-total rows) |
  | `streak_forwarded_from_toStreakVM` | FR-11 | `header.streak` === `toStreakVM(...)` |
  | `six_bucket_bars_passthrough` | FR-12 | `buckets` unchanged, length 6 |

### T2 — TrendChart primitive `[P]` (independent of T3/T4) — depends on T1 types
- **T2.1** `components/learn/TrendChart.tsx` — **SVG polyline** from `TrendPoint[]` (Q-D2 decided:
  new sparkline, not AccuracyBars). Per-point `<circle>` markers (non-color signal), theme-aware stroke
  `var(--color-accent)`, faint baseline only (no gridlines/goal-guide — Q-D1 decided). Full-width, no
  left column. a11y fallback (§4, mirrors AccuracyBars' per-element-label discipline). CSP-safe.
- **T2.2** `components/learn/TrendChart.test.tsx` (RTL): renders the series for ≥2 points; renders
  **no** line/slope (empty-state hook) for 0/1 points; a11y fallback present; theme tokens used.
  **(FR-9, FR-2 UI side.)**

### T3 — Hook + loader `[P]` — depends on T1
- **T3.1** `components/learn/use_progress_screen.ts` — `useProgressScreen({subject, learnerId, range})`
  → `useEngine()` → `loadProgressScreen(ports, {…, sinceISO computed from range, nowISO})` →
  `toProgressScreenVM(...)`. Mirror `use_skill_detail.ts` (cancel-on-unmount, loading flag).
- **T3.2** `components/learn/use_progress_screen.test.ts` (or fold into an integration test): 30d passes
  `sinceISO`; all-time omits it. **(FR-8 loader side.)**

### T4 — View — depends on T2 + T3
- **T4.1** `components/learn/ProgressView.tsx` — header (title "Your progress" + `N items reviewed ·
  M-day streak`), `RangeTabs` (DT-4; desktop/ipad only via `@container` per DT-6; iPhone hides tabs,
  not a dead control), the honest full-width trend card w/ caption "Accuracy trend" (DT-1, Q-D1),
  `<TrendChart>` (DT-2), **new horizontal bucket bar-rows** (Q-D3 decided: dot + name + track/fill +
  %-in-accent + DUE text badge; fed by the 6 existing `BucketCardVM`), empty-state copy (DT-5) when
  `points===[]`. Theme + a11y (DT-7).
- **T4.2** RTL test: renders header stat + streak; shows the DT-5 empty state on 0 sessions; hides tabs
  on the narrow container; DUE badge present when a bucket is due; % is a number (not color-only).
  **(FR-1/10/11/12 view side + iPhone edge + DT-3/5/6/7.)**

### T5 — Page + nav flip (the landmine) — depends on T4
- **T5.1** `app/(coach)/learn/progress/page.tsx` — `'use client'`, `LEARNER_ID="Garvit"`,
  `DEFAULT_SUBJECT`, range `useState`, calls `useProgressScreen`, renders `<ProgressView>` + loading state.
- **T5.2** Flip `nav_model.ts:76` `comingSoon: true → false` **in this same task** (never a separate
  commit — FR-5 dead-control ban).
- **T5.3** Reconcile the two tests the flip inverts (spec §8 landmine):
  - `components/shell/AppNav.test.tsx:27` — rewrite the iPhone "Progress is a disabled non-link" case to
    assert Progress is now a live `<a href="/learn/progress">` (mirror the E1a `skill` conversion).
  - `components/shell/nav_model.test.ts:82` — add `/learn/progress` to the wired-routes snapshot.
  - **G8 note:** these are the *only* test edits that weaken/flip an assertion; each is justified by the
    intended behavior change (Progress is now live). No other test assertions are touched.

### T6 — E2E smoke + full-suite gate — depends on T5
- **T6.1** `e2e/learn/validate_epic_f_progress.spec.ts` — nav → `/learn/progress` renders (200, no 404);
  range toggle updates the line/caption; `@axe` clean; iPhone surface has no Progress dead control.
- **T6.2** **Full** `pnpm vitest run` (not per-suite) + `test_frontend_layering.ts` + `make check` green.
  Diff the T0.2 baseline counts — new tests added, nav tests reconciled, nothing else red.
- **T6.3** **FR-3 verification:** grep the built VM + rendered DOM for `projected|goal|on track|score` →
  none present. Confirm `progressRepo` has still zero product consumers.
- **T6.4** `docs/adr/decisions.md` — add the 2–4 line entry (no ADR). Cross-link brainstorm + spec + plan.

---

## 8. Checklist — "unit tests for English" (every criterion measurable?)

- ✔ Every FR-1…FR-14 maps to a named test in T1–T6 (see spec §8 table + T1.2 table). Measurable.
- ✔ FR-3 (the honesty invariant) has **two** independent checks: a translator-level `no-score-key` test
  (T1.2) **and** an e2e DOM grep (T6.3). Not just an assertion — verified twice.
- ✔ FR-5 (dead-control ban) is enforced by task *coupling* (T5.2 in the same task as T5.1) + the e2e
  route-200 (T6.1), not by hope.
- ⚠ "Honest empty state" copy (FR-1) — confirm the exact string at implementation (it's UI copy, not a
  measurable engine behavior; the *presence* of the empty state is tested, the wording is a design call).

## 9. Definition of Done (from spec §9, restated as the merge gate)
- [ ] T0–T6 complete; every FR test seen red→green.
- [ ] Full frontend vitest + layering arch test + `make check` green (output pasted, not summarized).
- [ ] E2E smoke green + `@axe` clean; iPhone has no Progress dead control.
- [ ] FR-3 double-verified (translator test + DOM grep); `progressRepo` unconsumed.
- [ ] Nav flip landed WITH the page; the 2 inverted nav tests reconciled; no other test weakened.
- [ ] `decisions.md` line added (no ADR); brainstorm ↔ spec ↔ plan cross-linked.
