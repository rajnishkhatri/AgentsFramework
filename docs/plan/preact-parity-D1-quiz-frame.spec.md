---
title: 'Sprint D1 — Quiz session-frame chrome (Q-7 chip + Q-8 End + Q-9 collapsible timer) · Spec'
type: spec
status: Draft — 2026-07-10
date: 2026-07-10
owner: Rajnish Khatri
epic: D
derives_from: docs/plan/preact-parity-sprint-board-D.md
related:
  - docs/plan/preact-parity-sprint-board-D.md              # §Sprint D1 (this spec's origin)
  - docs/plan/preact-parity-epic-D.brainstorm.md           # Stage-1 audit (P3, P8 evidence)
  - docs/plan/preact-parity-D0-correct-record.spec.md      # sibling — corrected framings this spec relies on
  - docs/plan/preact-parity-epics.md                       # §Epic D — Q-7 / Q-8 / Q-9 rows
  - docs/plan/preact-ui-prototype-parity-VISUAL-gap-report.md
  - docs/plan/preact-quiz-progress-surface.spec.md         # precedent — VM + presentational component (S4)
  - docs/plan/preact-quiz-done-state.spec.md               # precedent — reducer + banner (S5)
  - docs/plan/preact-parity-A1-reveal.spec.md              # precedent — reducer dispatch + close+route pattern
  - docs/adr/0025-coach-surface-vm.md                      # precedent — G1 new-abstraction gate (if QuizFrameVM introduced)
governs:
  - frontend/lib/translators/quiz_item_vm.ts
  - frontend/components/quiz/QuizView.tsx
  - frontend/components/quiz/use_quiz.ts
  - frontend/components/quiz/quiz_screen_reducer.ts
  - frontend/app/(coach)/learn/quiz/page.tsx
---

# Sprint D1 — Quiz session-frame chrome

> **What / why split.** This spec is the *what* (EARS-testable acceptance criteria).
> The *why*-ADR is **conditional**: G1 (new-abstraction) fires only if the plan
> introduces a distinct `QuizFrameVM` (a separate translator + view slot) instead of
> extending `QuizItemVM` with two nullable fields. The default posture the plan
> proposes is **extend `QuizItemVM`** — no new abstraction, `decisions.md` line only.
> The plan revisits and locks that call; if the plan flips to `QuizFrameVM`, an ADR
> (numbered next in sequence, following ADR-0025's pattern) is authored in the same
> PR as the code.

---

## 1. Goal

Round out the Quiz screen's *session framing* — the three affordances the prototype
renders around the item body — so a learner on the PreAct `/learn/quiz` route
sees (a) **which skill** the current question is drilling, (b) an **explicit
control to end the session** without waiting for the target, and (c) a **timer
they can reveal on demand**. Bundled as one sprint because all three additions
live in the same frame region (above the item body), share the same
translator + view seam, and are individually so small that three parallel PRs
would double the ceremony without buying independence.

The two data spines already exist: `Skill.name` + `Skill.accent_var` at the
[wire kernel](../../frontend/lib/wire/engine_entities.ts:34), and per-item
timing (`Attempt.elapsed_ms`) captured by the reducer. D1 renders what was
already stored (Q-9) and joins what was already fetched (Q-7); Q-8 is a new
dispatch that reuses the existing idempotent `sessionRepo.close`.

For the learner ("Maya"): the quiz stops feeling like an unlabelled infinite
loop with no exit. For the codebase: no engine, schema, wire, or trust-kernel
change — this is a Frontend-Ring VM + view + reducer sprint.

## 2. Context

**Sprint-board scope:** [board §Sprint D1](preact-parity-sprint-board-D.md#sprint-d1--quiz-session-frame-chrome--one-sprint-three-sub-features)
groups Q-7 / Q-8 / Q-9 as one sprint. D0 corrected the load-bearing framings
for Q-7 (not view-only, needs the wire→VM→view seam — P3) and Q-9 (not
"dismissible" a rendered clock, but *collapsible / off-by-default* since no
clock renders today — P8). D1 inherits those corrected framings on read.

**Frontend Ring shape (F-R1).** The seam is the same one that shipped S4 (the
"Question N of M" progress bar): a **pure translator** owns the join/derivation
math, a **presentational component** renders the VM, and the **page** wires the
port calls. Q-7 slots into the existing item VM (or a new frame VM — plan
decides); Q-8 adds a new reducer action + page callback that runs the existing
`closeSession` orchestration then routes to `/learn`; Q-9 slots into the phase
state as a boolean (starts `false`) with an `elapsed_ms` reading derived from
`session.started_at` at render time.

**Precedents.** Each of the three sub-features follows a shipped pattern:
- Q-7 chip = [S4 QuizProgress](preact-quiz-progress-surface.spec.md) shape (translator
  + presentational component) + hook-side lookup mirroring the way `use_quiz`
  already reads `skillTaxonomy.list` for the focus-param resolution
  ([`quiz/page.tsx:90`](../../frontend/app/(coach)/learn/quiz/page.tsx:90)).
- Q-8 End session = [A1 reveal](preact-parity-A1-reveal.spec.md)'s close+route
  shape and the existing [`onFinish` handler](../../frontend/app/(coach)/learn/quiz/page.tsx:162)
  which already calls `closeSession` with the running tally then routes to the
  Summary — Q-8 is the *same close call*, routed to `/learn` instead of `/learn/summary`.
- Q-9 timer = [S5 QuizDoneBanner](preact-quiz-done-state.spec.md)'s presentational-leaf
  shape, plus the existing `session.started_at` (ISO string) read from the open
  `QuizSession`.

**Why one sprint.** Three internally-independent commits inside one PR is
lighter than three PRs because the three sub-features share (a) the same
`QuizView` header region — they must not race each other for layout, (b) the
same `QuizItemVM` (or its sibling `QuizFrameVM`) — a merge conflict is
guaranteed if authored separately, (c) the same test file
(`QuizView.test.tsx`) — three separate PRs means three re-runs of the same
setup. The sprint stays reversible: any single sub-feature can be reverted with
one commit-revert without touching the other two.

## 3. Functional requirements (EARS)

Failure/edge paths first (TAP-4). "Sub-feature" tags mark which sub-feature each
FR belongs to so a partial revert can identify its FRs; the DoD gates on all
three sub-features.

### Q-7 — Skill chip (sub-feature 1: wire→VM→view seam)

- **FR-Q7-1 (failure: no skill match).** IF the served question's `skill_id`
  does not resolve against the loaded `skillTaxonomy` (a seam defect — should
  not happen with reviewed data) THEN THE SYSTEM SHALL render the frame **with
  no chip at all** (honest absent), MUST NOT render a chip with placeholder or
  stubbed text ("Skill", "—", empty string, the raw id), and MUST NOT throw.
  The item body SHALL still render.
- **FR-Q7-2 (chip renders skill name + accent dot).** WHEN the served question's
  `skill_id` resolves to a known `Skill` THE SYSTEM SHALL render, in the Quiz
  frame region *above* the item body, a chip showing the `Skill.name` string,
  preceded by a dot glyph tinted by the `Skill.accent_var` CSS variable. The
  chip SHALL carry `data-testid="quiz-skill-chip"` and expose the skill name as
  its accessible text.
- **FR-Q7-3 (chip is view-model, not view-derived).** THE SYSTEM SHALL derive
  the chip's `{ skillName, accentVar }` in a **pure translator** joining the
  served `Question` against the loaded `Skill` rows; the presentational
  component SHALL render those two fields blindly and hold no lookup logic
  (F-R1).
- **FR-Q7-4 (chip persists across `answering` and `reviewing`).** THE SYSTEM
  SHALL render the same chip in both the `answering` and `reviewing` phases of
  the current item (the skill did not change) and SHALL NOT flicker or
  re-render between phases.

### Q-8 — End session (sub-feature 2: new dispatch + close + route)

- **FR-Q8-1 (failure: no session yet).** IF the `session` state is still `null`
  (Effect 1 has not resolved) THEN THE SYSTEM SHALL either not render the End
  session control at all OR render it as non-actionable (disabled). Clicking a
  non-actionable control SHALL NOT dispatch and SHALL NOT throw.
- **FR-Q8-2 (failure: session already closed).** IF the phase is `done` (the
  learner already closed via Finish) THEN the End session control SHALL NOT
  fire a second `sessionRepo.close`. `close` is idempotent so a stray second
  call would not corrupt state, but the control SHALL either be hidden or
  non-actionable in `done`.
- **FR-Q8-3 (End control renders in `answering` and `reviewing`).** WHILE the
  phase is `answering` or `reviewing` THE SYSTEM SHALL render an End session
  control in the Quiz frame region carrying
  `data-testid="quiz-end-session"`, with a plain-text label a learner can
  understand ("End session", "Leave session", or equivalent).
- **FR-Q8-4 (End closes the session with the running tally).** WHEN the learner
  clicks End session THE SYSTEM SHALL call `sessionRepo.close(session.id, {
  score_correct, score_total })` with the current
  [`SessionTally`](../../frontend/components/quiz/quiz_screen_reducer.ts:53)
  from the reducer — the same tally `onFinish` uses ([page.tsx:170-172](../../frontend/app/(coach)/learn/quiz/page.tsx:170))
  — and MUST NOT recompute the tally from attempts.
- **FR-Q8-5 (End routes to the dashboard after close).** WHEN
  `sessionRepo.close` resolves THE SYSTEM SHALL navigate to `/learn`
  ([`screen("dashboard").route`](../../frontend/components/shell/nav_model.ts))
  and SHALL NOT navigate to `/learn/summary` (that is the Finish path, D5).
  The route change SHALL be awaited *after* close resolves so a routing race
  does not read the session before the close persists.
- **FR-Q8-6 (End is a distinct reducer transition).** THE SYSTEM SHALL model
  End session as a new phase transition, distinct from `finish`, so a
  future test or Playwright spec can assert the two paths do not collapse.
  The reducer's `finish` action MUST still route to Summary; it MUST NOT
  regress into the End-session route.

### Q-9 — Collapsible timer (sub-feature 3: off-by-default reveal)

- **FR-Q9-1 (failure: no session yet).** IF `session` is still `null` THEN THE
  SYSTEM SHALL NOT render the timer reveal control.
- **FR-Q9-2 (default: collapsed).** WHEN a new item first loads THE SYSTEM
  SHALL render the timer in the **collapsed** state: no clock text is present
  in the DOM; only a small reveal affordance carrying
  `data-testid="quiz-timer-reveal"` renders in the frame region.
- **FR-Q9-3 (reveal toggles expanded).** WHEN the learner clicks the reveal
  affordance THE SYSTEM SHALL transition the timer to the **expanded** state:
  a clock display carrying `data-testid="quiz-timer"` renders showing the
  session's elapsed time.
- **FR-Q9-4 (expanded shows `session.started_at` derived elapsed).** WHILE the
  timer is expanded THE SYSTEM SHALL render the elapsed time as `m:ss` derived
  from `session.started_at`
  ([wire field](../../frontend/lib/wire/engine_entities.ts:209), ISO 8601
  string) and the wall clock, MUST NOT round negatively, and MUST NOT display
  `NaN:NaN` if `started_at` is not-yet-set. If `started_at` parses to a value
  greater than the wall clock (a clock adjustment) THE SYSTEM SHALL clamp
  displayed elapsed to `0:00`.
- **FR-Q9-5 (collapse returns to collapsed).** WHEN the learner clicks a
  collapse affordance in the expanded state THE SYSTEM SHALL return the timer
  to the collapsed state (FR-Q9-2) and remove the clock display from the DOM.
- **FR-Q9-6 (collapsed does NOT capture `elapsed_ms` differently).** THE
  SYSTEM SHALL NOT change per-item `Attempt.elapsed_ms` capture based on
  whether the timer is revealed. The existing D0 elapsed-timing path
  ([reducer :40](../../frontend/components/quiz/quiz_screen_reducer.ts:40))
  is unaffected; the timer is a *display* of session-elapsed, not a
  replacement for the per-item measurement.
- **FR-Q9-7 (timer state resets on new item).** WHEN a new item loads (the
  reducer transitions to `answering` via `item_loaded`) THE SYSTEM SHALL keep
  the *session-level* elapsed clock running (`session.started_at` is
  session-scoped) but SHALL reset the per-item reveal state to *collapsed* —
  a learner who revealed the timer on Q1 does NOT automatically see it
  revealed on Q2.
- **FR-Q9-8 (accessible reveal).** THE SYSTEM SHALL expose the reveal
  affordance as a `<button>` (not `<div onClick>`) with an accessible label
  ("Show timer" / "Hide timer" or equivalent). The clock, when expanded,
  SHALL be readable text (not conveyed by color alone; WCAG 2.2 AA, per
  frontend §13).

### Cross-sub-feature (structural)

- **FR-X1 (pure translator owns the derivation — F-R1).** THE SYSTEM SHALL
  compute the chip's `{ skillName, accentVar }` and (if the plan flips to
  `QuizFrameVM`) any other frame-level derived fields in a **pure, React-free
  translator** imported by the page/hook; the components (`QuizView` and any
  new leaf) SHALL render blindly and hold no lookup / no join / no clamp
  logic.
- **FR-X2 (read-only — no engine write).** THE SYSTEM SHALL derive Q-7's join
  from `skillTaxonomy.list` (read-only), Q-8's close from the existing
  idempotent `sessionRepo.close`, and Q-9's elapsed from `session.started_at`
  (read of the open session). It SHALL NOT introduce a new port, a new
  `skill_state` write, or a new attempt row.
- **FR-X3 (backward-compatible; no behavior regressions).** THE SYSTEM SHALL
  leave the S3 serving / S3.1 rotation / S4 progress bar / S5 done-state
  behavior unchanged. Existing e2e / L1 selectors (`quiz-context`,
  `quiz-hint-toggle`, `quiz-submit`, `quiz-reveal`, `quiz-next`,
  `quiz-finish`, `quiz-progress`) SHALL NOT be renamed or moved. New
  test-ids (`quiz-skill-chip`, `quiz-end-session`, `quiz-timer-reveal`,
  `quiz-timer`) SHALL be added, not repurposed from existing ones.
- **FR-X4 (iPad split preserved).** THE SYSTEM SHALL keep the iPad-surface
  Quiz split ([page.tsx:316-333](../../frontend/app/(coach)/learn/quiz/page.tsx:316))
  working: the new chip / End / timer render in the item column (left of the
  CoachPanel), never inside the coach column. The `useSurface` gate is not
  re-flowed; D1 is purely additive within the item column.

## 4. Data model / contracts

**No wire / schema / DB / trust-kernel change.** Every field D1 needs already
exists on the wire kernel:

| Signal (already exists) | Type | Consumed by |
|---|---|---|
| [`Skill.name`](../../frontend/lib/wire/engine_entities.ts:34) | `string` | Q-7 chip label |
| [`Skill.accent_var`](../../frontend/lib/wire/engine_entities.ts:34) | `string` (CSS var name, e.g. `"--color-bucket-punctuation"`) | Q-7 chip dot color |
| [`Question.skill_id`](../../frontend/lib/wire/engine_entities.ts:61) | `string` | Q-7 join key |
| [`QuizSession.started_at`](../../frontend/lib/wire/engine_entities.ts:209) | `string` (ISO 8601) | Q-9 elapsed derivation |
| [`SessionTally`](../../frontend/components/quiz/quiz_screen_reducer.ts:53) | `{ correct, total }` | Q-8 close-with-tally |
| [`SessionRepo.close`](../../frontend/lib/adapters/engine/repos/drizzle_session_repo.ts:113) | idempotent | Q-8 dispatch target |

**New (frontend-only) view-model additions.** Two nullable optional fields on
`QuizItemVM` (default posture — no ADR):

```ts
interface QuizItemVM {
  // ... existing fields (questionId, skillId, contextHtml, stem, choices) ...
  /** Q-7: joined skill display name; `null` if the join failed (FR-Q7-1). */
  readonly skillName: string | null;
  /** Q-7: `Skill.accent_var` (a CSS custom-property name); `null` if the join failed. */
  readonly accentVar: string | null;
}
```

**Alternate posture (only if plan flips):** a separate `QuizFrameVM` interface
+ translator. That flip triggers G1 (new-abstraction gate) and an ADR
(following ADR-0025's coach-surface-VM pattern). The plan proposes the
default; the human gates the flip at plan review time.

**No new wire schema.** `Skill.name` / `Skill.accent_var` do not cross the
Python boundary (the engine is Frontend-Ring-local — [ADR-0005](../adr/0005-subject-coach-engine-home-and-substrate.md));
the `__python_schema_baseline__.json` gate has no surface for D1.

## 5. Invariants & security boundaries

- **F-R1 (no domain logic in components).** The `Skill` join happens in the
  hook (`use_quiz` extension — same layer that already reads
  `skillTaxonomy.list` for focus-param resolution) or a translator, never in
  `QuizView`. The elapsed clamp/format for Q-9 is a pure helper next to
  `elapsedMsFrom`, not inline in the component.
- **F-R2 (SDK imports only in adapters).** N/A — no SDK touched.
- **F-R6 (`trust-view/` read-only).** N/A — no trust-view touched.
- **F-R7 (`trace_id` propagation).** N/A — no wire event emitted.
- **F-R8 (no SDK type past adapter).** N/A — no SDK type surfaces.
- **Root [`AGENTS.md`] Architecture Invariants #1–#8:** none touched. This is
  Frontend-Ring-only; the four-layer backend (`trust/`, `services/`,
  `components/`, `orchestration/`) is not edited.
- **Trust-adjacent honesty (Epic A class).** Q-8's End session control MUST
  route to `/learn` (dashboard) — not a 404 stub — mirroring the Epic-A rule
  that a rendered control must do what it says. FR-Q8-5 is the enforcement.
- **G1 new-abstraction gate.** Fires **only if** the plan flips to a separate
  `QuizFrameVM`. Default posture (extend `QuizItemVM`) is not a new
  abstraction; it is a two-field extension of an existing VM (same shape as
  every prior VM extension in this program). The plan re-visits and locks
  the call in one paragraph.
- **No security boundary touched** — no secrets, no auth, no sandbox, no live
  LLM, no CI hot-path change. `sessionRepo.close` was already idempotent and
  already the only writer to `ended_at` (FR-D3).

## 6. Edge cases

- **`Skill` list arrives after the first `Question`.** Both are fetched via
  the same engine bag — `listSkillIds` for the focus-param resolution runs in
  Effect 1 *before* the first item is loaded, so by the time Effect 2 fires
  the taxonomy is warm. Still: if the join for the current `skill_id` misses
  (FR-Q7-1), the frame renders without a chip; it does not stall.
- **Two items in a row for the same skill.** The chip must not flicker or
  animate a "change" between two identical values — it renders the same
  markup and React's diffing handles it. Assert with an L1 test that reloads
  an item with the same `skill_id` and checks the chip is unchanged.
- **`session.started_at` in the future.** A wall-clock adjustment during play
  can make `Date.now() - Date.parse(started_at) < 0`. The elapsed helper
  clamps to 0 (mirrors [`elapsedMsFrom`](../../frontend/components/quiz/quiz_screen_reducer.ts:40)
  which already clamps non-negative). FR-Q9-4.
- **`session.started_at` unparseable.** Should not happen (the wire schema is
  `z.string()`; the repo writes `new Date().toISOString()`). Defensive: if
  `Date.parse` returns `NaN` treat as "no reading" and render `0:00`, do
  not throw and do not render `NaN:NaN`. FR-Q9-4.
- **Reveal-then-navigate-away.** No lingering timer state — React unmounts
  the component on route change, the elapsed loop (setInterval) cleans up
  via effect cleanup. Assert via an L1 test that dismounts the component.
- **End session double-click.** `sessionRepo.close` is idempotent (FR-Q8-2
  guards double-dispatch anyway); a second dispatch simply re-issues the
  same PATCH which the repo applies as a no-op.
- **End session while a submit is in flight.** The submit's `runQuizSubmit`
  path writes an attempt row and calls `scheduler.review` — those must
  complete or be abandoned safely. Simplest posture: End session is only
  actionable in `answering` and `reviewing`, both of which have no in-flight
  effect at click time (the `.then()` chain from `onSubmit` completes before
  the phase changes). If a race is discovered, the plan proposes a small
  `isSubmitting` gate; the spec's FR-Q8-1 already covers the general "not
  actionable" case.
- **Chip absent on `loading` / `done`.** The frame region only exists while
  the reducer is in `answering` or `reviewing`
  ([page.tsx:189-195](../../frontend/app/(coach)/learn/quiz/page.tsx:189));
  `loading`/`done` render a status text and no frame. So Q-7 / Q-8 / Q-9 do
  not need to worry about those phases beyond what the reducer already does.

## 7. Non-functional requirements

- **Determinism:** every translator addition is a pure function → L1 exact
  table tests. The Q-9 elapsed helper is pure (takes `startedAt: string` and
  `now: number`, returns `"m:ss"`) and needs no fake clock in tests.
- **Latency / cost:** no new network call. The `Skill` list is already
  loaded in Effect 1 (S3 flow); Q-7 reuses that read. Q-8 fires exactly one
  `sessionRepo.close` PATCH — the same call `onFinish` already makes. Q-9
  reads `session.started_at` off React state (no network).
- **No live LLM anywhere** — stays off the CI hot path by construction.
- **Reversibility:** additive UI + one new reducer action + one new page
  callback. Reverting the sprint restores today's behavior exactly (FR-X3).
- **Bundle:** two nullable fields on `QuizItemVM`, one new pure elapsed
  helper, at most one new presentational leaf (`QuizFrame` — plan decides
  vs. inlining in `QuizView`). No new dep.
- **Timer render loop:** the expanded timer updates via `setInterval` (or
  `requestAnimationFrame`) at 1s cadence; the plan pins the choice. This is
  a browser-side effect isolated to the presentational leaf; the reducer is
  clock-free (FR-X1).

## 8. Test plan

Failure-path tests first. L1 (Vitest + JSDoc SSR) for the translator + the
components; the reducer's new `end_session` action is a plain transition
test; one L4 Playwright e2e for the End-session-to-dashboard path.

| FR | Test | Layer | In `make check`? |
|----|------|-------|------------------|
| FR-Q7-1 | `quiz_item_vm.test.ts::skill_id with no match → skillName null, accentVar null` | L1 | yes |
| FR-Q7-2 | `QuizView.test.tsx::renders quiz-skill-chip with skill name and accent style` | L1 (SSR) | yes |
| FR-Q7-3 | (structural) translator imports no adapter/hook — frontend layering test | arch | yes |
| FR-Q7-4 | `QuizView.test.tsx::chip present in both answering and reviewing phases` | L1 (SSR) | yes |
| FR-Q8-1 | `QuizView.test.tsx::End session disabled or absent when session null` | L1 (SSR) | yes |
| FR-Q8-2 | `quiz_screen_reducer.test.ts::end_session in done phase is a no-op` | L1 | yes |
| FR-Q8-3 | `QuizView.test.tsx::quiz-end-session renders in answering and reviewing` | L1 (SSR) | yes |
| FR-Q8-4 | `quiz_page.test.tsx::End session calls closeSession with current tally` | L1 | yes |
| FR-Q8-5 | `e2e/learn/quiz-end-session.spec.ts::click End → sessionRepo.close + navigate to /learn` | L4 | on-demand |
| FR-Q8-6 | `quiz_screen_reducer.test.ts::end_session action transitions to done (or terminal); finish still routes to Summary` | L1 | yes |
| FR-Q9-1 | `QuizView.test.tsx::timer reveal absent when session null` | L1 (SSR) | yes |
| FR-Q9-2 | `QuizView.test.tsx::default is collapsed (no quiz-timer in DOM, quiz-timer-reveal present)` | L1 (SSR) | yes |
| FR-Q9-3 | `QuizView.test.tsx::click quiz-timer-reveal → quiz-timer renders` | L1 | yes |
| FR-Q9-4 | `quiz_frame_timer.test.ts::formatElapsed(startedAt, now) table — 0:00 / 0:59 / 1:00 / 10:00 / future-clock → 0:00 / NaN → 0:00` | L1 | yes |
| FR-Q9-5 | `QuizView.test.tsx::click collapse from expanded → quiz-timer removed` | L1 | yes |
| FR-Q9-6 | (structural) `quiz_screen_reducer` untouched around `presentedAt` / `elapsedMsFrom` — reducer test suite green | L1 | yes |
| FR-Q9-7 | `QuizView.test.tsx::item_loaded resets reveal to collapsed` | L1 | yes |
| FR-Q9-8 | `QuizView.test.tsx::reveal is a <button> with accessible label` | L1 (SSR) | yes |
| FR-X1 | (structural) frontend layering test — translator imports no React/adapter | arch | yes |
| FR-X2 | (structural) grep — no new port surface, no `skill_state` write | grep | manual review |
| FR-X3 | existing `QuizView` / `quiz_screen_reducer` / progress / done suites stay green | L1 | yes |
| FR-X4 | `e2e/learn/quiz-ipad-split.spec.ts` (existing) stays green | L4 | on-demand |

## 9. Definition of Done

- [ ] All FRs implemented; each has a passing test that was **seen to fail
      first** (red/green — paste the failing output, not a summary — per root
      [`AGENTS.md`](../../AGENTS.md) "Always" rule "Red/green TDD").
- [ ] `frontend` `tsc --noEmit` → 0 errors; touched vitest suites green;
      **command output pasted, not summarized**.
- [ ] Frontend layering / port-conformance arch tests green (F-R1 holds:
      translator pure; components hold no domain logic).
- [ ] `pytest tests/architecture/ -q` green (no Python touched — but the
      constitution gate must stay green).
- [ ] `python scripts/okf_lint.py` → exit 0 (docs plane still extractable).
- [ ] `make check` green — command output pasted.
- [ ] ADR appended **iff** the plan flipped to a separate `QuizFrameVM` (G1
      new-abstraction gate). Default posture (extend `QuizItemVM` with two
      nullable fields) requires only a `docs/adr/decisions.md` line
      recording the choice.
- [ ] Live `/learn/quiz` shows: skill chip above item on first load; End
      session control present; timer collapsed by default; reveal → clock
      shows a plausible `m:ss` reading; End session → land on `/learn`.
      Screenshot / Playwright evidence pasted.
- [ ] Sprint board status flipped to **Implemented** with a Stage-6 evidence
      section (§ pattern mirrors S4/S5 specs).
- [ ] Log explicitly in the PR body: **D1 shipped Q-7 + Q-8 + Q-9. The
      framings for these findings were corrected by D0 (2026-07-10) —
      inheriting P3 / P8 corrections. D1 did NOT ship D2 (taxonomy) or D3
      (Q-1b decision) — those remain independent.**

---

## Premise audit (Stage 1 discipline — verified against the working tree)

D1 inherits the [Epic-D Stage-1 audit](preact-parity-epic-D.brainstorm.md#1--premise-audit-grounded-against-the-working-tree)
(P1–P16) and re-verifies the load-bearing seams *this spec* references. All
line anchors verified 2026-07-10 against `main` at commit
[`86f5f2d`](preact-parity-D0-correct-record.plan.md).

| Premise (this spec relies on) | Status | Evidence (`file:line`) |
|---|---|---|
| `Skill.name` + `Skill.accent_var` exist on the wire | **verified** | [engine_entities.ts:34-44](../../frontend/lib/wire/engine_entities.ts:34) |
| `Question.skill_id` exists but does NOT carry name/accent | **verified** | [engine_entities.ts:61](../../frontend/lib/wire/engine_entities.ts:61) — join required (P3 seam) |
| `QuizItemVM` today has `skillId` only, no name/accent | **verified** | [quiz_item_vm.ts:24-32](../../frontend/lib/translators/quiz_item_vm.ts:24) |
| `QuizView` today renders no chip / no End / no timer | **verified** | [QuizView.tsx](../../frontend/components/quiz/QuizView.tsx) full 145-line read — 0 hits for chip/end/timer/clock/elapsed in the UI region (P4/P8) |
| `use_quiz.openQuizItem` already reads `skillTaxonomy.list` (indirect, via `listQuizSkillIds`) | **verified** | [use_quiz.ts:105-111](../../frontend/components/quiz/use_quiz.ts:105); page consumer at [quiz/page.tsx:90](../../frontend/app/(coach)/learn/quiz/page.tsx:90) — the same read D1's translator/hook extension will reuse |
| `SessionRepo.close` is idempotent and re-usable for End session | **verified** | [drizzle_session_repo.ts:113-128](../../frontend/lib/adapters/engine/repos/drizzle_session_repo.ts:113); `patchSessionClose` returns `null` for a missing row (throws `EngineNotFoundError`) — a genuinely-idempotent re-close of an already-closed row applies the same patch |
| `SessionTally` on the reducer already rides every phase | **verified** | [quiz_screen_reducer.ts:53-95](../../frontend/components/quiz/quiz_screen_reducer.ts:53); `SessionTally` = `{ correct, total }` carried on `LoadingPhase`/`AnsweringPhase`/`ReviewingPhase`/`DonePhase` |
| `session.started_at` exists as ISO 8601 string | **verified** | [engine_entities.ts:209](../../frontend/lib/wire/engine_entities.ts:209) + [drizzle_session_repo.ts:78](../../frontend/lib/adapters/engine/repos/drizzle_session_repo.ts:78) — written on `open()` |
| `onFinish` already uses the exact close-with-tally pattern | **verified** | [quiz/page.tsx:162-179](../../frontend/app/(coach)/learn/quiz/page.tsx:162) — the pattern Q-8 mirrors, differing only in the route target |
| Dashboard route `/learn` exists | **verified** | [app/(coach)/learn/page.tsx](../../frontend/app/(coach)/learn/page.tsx) via [nav_model.ts:65](../../frontend/components/shell/nav_model.ts:65) |
| `elapsed_ms` capture is separate from the timer display | **verified** | [quiz_screen_reducer.ts:40](../../frontend/components/quiz/quiz_screen_reducer.ts:40) `elapsedMsFrom` — per-item, monotonic, unaffected by Q-9 (P7) |
| iPad split lives in `page.tsx`, not in `QuizView` | **verified** | [quiz/page.tsx:316-333](../../frontend/app/(coach)/learn/quiz/page.tsx:316) — chip/End/timer render inside the item column, not the coach column (FR-X4) |

**No refuted premises.** The three nuances the plan must lock (§10 below): the
`QuizItemVM`-vs-`QuizFrameVM` shape (§4 default posture); whether the timer
tick uses `setInterval` or `requestAnimationFrame` (§7); and whether End
session and Finish converge at the reducer's `done` phase or D1 introduces a
separate terminal state (§FR-Q8-6). All three are plan decisions, not spec
refutations.

## §10 Clarify — decisions to lock at plan time

Three questions the plan resolves before implementation fires; the spec
holds room for either resolution.

1. **VM shape — extend `QuizItemVM` (default) or introduce `QuizFrameVM`?**
   Recommended: **extend**, on the basis that (a) the three sub-features
   share the same *item's* skill (Q-7), same *session's* clock (Q-9), and
   same *session's* tally (Q-8) — the natural home is beside the item VM;
   (b) two nullable fields is not a new abstraction; (c) a separate frame
   VM would introduce a G1-gate ADR for zero additional testability (the
   two-field extension is already fully tested). Flip if — and only if —
   the plan finds the item VM crossing 8+ fields, in which case ADR-0026
   follows ADR-0025's pattern.

2. **Timer tick cadence — `setInterval(1000)` or `requestAnimationFrame`?**
   Recommended: **`setInterval(1000)`**. The clock only needs 1s resolution
   (`m:ss` display); rAF would over-tick and waste frames. Simple useEffect
   with cleanup on unmount. Reducer stays clock-free (FR-X1).

3. **Reducer terminal state — End session and Finish converge on `done`, or
   split?** Recommended: **converge on `done` with a distinguishing tag**
   (`endedVia: "finish" | "end_session"`) OR **stay converged with no tag,
   distinguishing at the page callback** (route by which handler fired).
   FR-Q8-6 requires the transitions be distinct; the plan picks the tag
   posture. Either way, `finish` MUST still route to Summary — non-negotiable
   regression guard.
