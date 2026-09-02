# Spec — Exam module: official-rules full-length test suite (durable, section-at-a-time, timed, flagged, analysed)

> The spec captures the *what* (testable acceptance criteria). This change fires two
> `⚠️ Ask first` triggers — a **new horizontal repo seam** (exam run persistence: new
> tables, new `EngineDb` methods, new BFF handlers) and a **new abstraction** (the
> exam-analytics read model) — so the plan raises **one ADR** covering both. Stage-2
> human gate: the five clarify answers of 2026-09-01 are folded in (§2.2).

**Status:** Draft — 2026-09-01
**Owner:** Rajnish Khatri
**Related:** [quiz-attempt-elapsed-timing.spec.md](quiz-attempt-elapsed-timing.spec.md) (§2.1 consent gate "Test mode persists nothing" — **this spec is that consent, exercised for a NEW module, not for Test Mode**); [test01-practice-split.spec.md](test01-practice-split.spec.md) (FR-1 practice/test exclusivity — inherited); [ADR-0038](../adr/0038-durable-engine-seam.md) (the `HttpEngineDb → /api/engine/* → pgEngineDb` seam every new persistence path rides); private ingestion `docs/preact9secure/README.md` (form JSON, step 1 — not tracked); existing Test Mode [test/page.tsx](../../frontend/app/(coach)/learn/test/page.tsx), [test_runner_reducer.ts](../../frontend/components/test/test_runner_reducer.ts), [test_scoring.ts](../../frontend/components/test/test_scoring.ts).

---

## 1. Goal

Give a learner a **full-length practice exam that behaves like the official test**: a
form with timed sections taken **one section at a time**, official navigation and
timing rules, per-question **time tracking** and **mark-for-review flags**, results
that **persist across sittings and devices**, and a **strength/weakness analysis**
(by subject, reporting category, skill/topic, pacing) that tells the learner what to
improve next. Today's Test Mode is a throwaway English-only timer that persists
nothing (§2); this spec introduces a **new `exam` module** beside it rather than
mutating it.

## 2. Context

- **What exists.** `/learn/test` reads 24 test-only Test-01 English rows, keeps
  `intro → in_section → results` + an `answers` map in a `useReducer`, grades once with
  the pure engine `Grader`, shows raw score + a hardcoded scale *band*, and writes
  nothing — no session, attempt, or localStorage
  ([test_runner_reducer.ts:29](../../frontend/components/test/test_runner_reducer.ts#L29),
  [test_scoring.ts:15](../../frontend/components/test/test_scoring.ts#L15)). It
  deliberately shares nothing with the adaptive quiz and does not feed
  `/learn/progress`, whose strength view is FSRS `skill_state.mastery`
  ([bucket_card_vm.ts:42](../../frontend/lib/translators/bucket_card_vm.ts#L42)).
- **Schema that exists and is reusable.** `Attempt.elapsed_ms` (quiz only), the
  `Question` wire shape, the durable engine seam (`EngineDb` 31 methods, `HttpEngineDb`,
  BFF `/api/engine/*`, `pgEngineDb`, dual-dialect `schema.pg.ts`/`schema.sqlite.ts`,
  migrations `0000–0004`). **No timed-test run table, no flag/bookmark field
  anywhere.** `test_item`/`test_blueprint` are practice-bank content tables, not runs —
  hence the `exam_*` namespace here to avoid collision.
- **Corpus.** Step 1 of the private ingestion produced three official forms as JSON
  (all four sections, keys, reporting categories, conversion tables) that the app
  cannot load yet; only English renders (A–D, text). The only app-loadable exam
  content today is the Test-01 English test-only slice.
- **Official rules being mimicked** (from the booklets' directions + ACT test-day
  policy): fixed section order English → Math → Reading → Science for a full sitting;
  each section is one continuous timed block — no pausing, and once a section's time
  is up or it is submitted you cannot return to it; free navigation *within* a
  section; answers may be changed any time before submit; mark-for-review (TestNav
  "flag") within the section; no penalty for guessing (blank = 0, no negative);
  5-minute remaining warning; time expiry auto-submits; raw score = count of correct
  **scored** items; scale score from the form's conversion table; composite = rounded
  mean of the form's composite sections (all four on legacy PreACT Secure; English +
  Math + Reading on the Enhanced ACT, Science reported separately).

### 2.1 Non-goals (each is its own later spec)

- **Loading the real official forms** (private JSON → app) and **rendering Math /
  Reading / Science** (figures as images, 5-choice Math — the wire `Choice.letter` is
  a free string but every renderer is A–D). The exam module is **section-agnostic by
  data model**; phase 1 ships with the Test-01 English section as its only form.
- **Writing exam results into FSRS `skill_state`** or the practice scheduler. Timed
  tests measure; practice teaches. Exam analytics is a separate read model (§4.4).
- **LLM-authored improvement narratives.** Phase-1 recommendations are deterministic
  rules over the analytics (demand-side lens); an LLM narrative is a later, gated add.
- **Modifying Test Mode.** `/learn/test` stays as-is until the exam module supersedes
  it (removal is a separate decision).
- **Proctoring / anti-cheat** (tab-switch detection beyond dwell pausing, lockdown).

### 2.2 Clarified at the human gate (2026-09-01)

1. **New module** (`exam`) mimicking official rules; section-agnostic data model;
   Test-01 English is the phase-1 form.
2. **Durable** persistence via the ADR-0038 seam (new `exam_run` / `exam_run_item`
   tables), learner-scoped.
3. **Time per question = accumulated active dwell** (sum of visits, paused while the
   tab is hidden) **plus first-answer timestamp**.
4. **Flag = in-section mark-for-review** (navigator jump-back) that **persists after
   submit** as the revision list; **plus** a post-hoc bookmark on any question from
   results. Flags never reach the practice scheduler.
5. **Separate exam-analytics model**: strengths/weaknesses per subject, reporting
   category, skill/topic, pacing → deterministic improvement recommendations.

## 3. Functional requirements (EARS)

Failure paths first. "Run" = one learner's sitting of one form; "section attempt" =
one section inside a run; "item" = one question inside a section attempt.

### 3.1 Integrity & failure paths

- **FR-1.** IF a section attempt's deadline (`started_at + minutes`) has passed when
  the learner loads or interacts with it THEN THE SYSTEM SHALL submit it as
  `expired` with whatever answers were saved, and SHALL NOT accept further answers
  for it.
- **FR-2.** IF the learner requests a section attempt that is already `submitted` or
  `expired` THEN THE SYSTEM SHALL show its review view and SHALL NOT reopen it for
  answering (official rule: no returning to a finished section).
- **FR-3.** IF an item write (answer, flag, dwell) arrives for a run/section that
  does not belong to the authenticated learner THEN THE SYSTEM SHALL reject it
  (cross-learner isolation, ADR-0038 FR-A2a precedent).
- **FR-4.** IF the same item write is delivered twice (retry, double-tap, reconnect)
  THEN THE SYSTEM SHALL apply it once: item writes are idempotent upserts keyed by
  `(run_id, section_code, question_id)` with dwell **monotonic-max**, never summed on
  replay.
- **FR-5.** IF the client cannot reach the BFF while a section is in progress THEN THE
  SYSTEM SHALL keep the section running on the local clock, buffer item writes, and
  flush them on reconnect or submit; a flush that still fails at submit SHALL surface
  a visible "not saved" state, never a silent success.
- **FR-6.** IF a form has zero sections, or a section has zero questions, THEN THE
  SYSTEM SHALL fail at module load (build/test time), not render an empty exam.
- **FR-7.** IF a form's scale-conversion table is absent (Form 805 style) THEN THE
  SYSTEM SHALL report raw score and percent and show scale score as *not available*
  (honest `null`, never a fabricated scale; AP-6).
- **FR-8.** IF composite is requested before every composite section of the run is
  submitted/expired THEN THE SYSTEM SHALL return `null` for composite, never a partial
  average.

### 3.2 Form model & selection

- **FR-9.** THE SYSTEM SHALL describe a form as `ExamForm { id, title, blueprint,
  sections[] }` and a section as `{ code, title, minutes, choice_count, directions,
  composite: boolean, scale_table: (raw→scale) | null, questions[] }`, where each
  question is the existing wire `Question` plus optional `reporting_category` and
  `scored: boolean` (§4).
- **FR-10.** WHEN the learner opens the exam module THE SYSTEM SHALL list available
  forms and, per form, each section's status for that learner: `not_started`,
  `in_progress` (with remaining time), `submitted`, `expired`.
- **FR-11.** THE SYSTEM SHALL let the learner start **any not-started section of a run
  independently** (one section per sitting), while showing the official order as the
  recommended order; a full sitting is not required.
- **FR-12.** WHILE a section attempt is `in_progress` THE SYSTEM SHALL refuse to start
  another section of the same run (one section at a time, officially).

### 3.3 Section rules & timing

- **FR-13.** WHEN the learner opens a not-started section THE SYSTEM SHALL show the
  official directions and the time allowed, and SHALL start the clock only on an
  explicit "Begin" (`started_at` recorded server-side on begin).
- **FR-14.** WHILE a section is `in_progress` THE SYSTEM SHALL show a countdown
  derived from the server-recorded `started_at` and the section minutes (wall-clock
  anchored, so reloads and device switches show the same remaining time).
- **FR-15.** WHEN 5 minutes remain THE SYSTEM SHALL show a persistent time warning
  once (official proctor call).
- **FR-16.** WHEN the countdown reaches zero THE SYSTEM SHALL auto-submit the section
  (`expired`) without a learner tap (Test Mode precedent, `?dur=` non-prod override
  retained for e2e).
- **FR-17.** WHILE a section is `in_progress` THE SYSTEM SHALL allow free navigation
  to any question (next/prev/navigator), answer changes, and clearing an answer.
- **FR-18.** WHEN the learner submits with unanswered items THE SYSTEM SHALL warn with
  the unanswered count and require confirmation; unanswered items score 0 and are
  recorded as `unanswered` (no guessing penalty, official rule).

### 3.4 Per-question timing

- **FR-19.** WHEN a question becomes the current question THE SYSTEM SHALL start
  accumulating its dwell from a monotonic clock, and SHALL stop when the learner
  navigates away, submits, or the tab becomes hidden (`visibilitychange`), resuming on
  return; `dwell_ms` is the sum over all visits.
- **FR-20.** WHEN the learner first selects any answer for a question THE SYSTEM SHALL
  record `first_answered_at` (wall clock) and `dwell_at_first_answer_ms`; later
  changes update `chosen_letter` and increment `answer_changes` but never overwrite the
  first-answer fields.
- **FR-21.** THE SYSTEM SHALL persist item timing on every navigation away from a
  question and on submit (debounced), so a reload mid-section loses at most the
  current question's un-flushed dwell.
- **FR-22.** THE SYSTEM SHALL record `visits` (count of times the question became
  current) per item.

### 3.5 Flags & bookmarks

- **FR-23.** WHILE a section is `in_progress` THE SYSTEM SHALL let the learner toggle
  **mark-for-review** on the current question; the navigator SHALL show flagged,
  answered, unanswered, and current states distinctly and allow jumping to any.
- **FR-24.** WHEN a section is submitted or expires THE SYSTEM SHALL keep its
  mark-for-review flags immutable as part of the record (`flagged_in_section`).
- **FR-25.** WHEN the learner views a finished section THE SYSTEM SHALL let them toggle
  a **bookmark** on any question (`bookmarked`, independent of the in-section flag),
  and SHALL list "to revise" = flagged ∪ bookmarked ∪ wrong, filterable by each.
- **FR-26.** THE SYSTEM SHALL NOT expose flags/bookmarks to the practice scheduler or
  fold exam items into the practice bank (test exclusivity, inherited FR-1 of the
  split spec; guarded by an architecture test).

### 3.6 Scoring & review

- **FR-27.** WHEN a section attempt finishes THE SYSTEM SHALL grade it once with the
  pure engine `Grader` and persist per item `correct: boolean | null` (`null` =
  unanswered) and per section `raw_correct`, `raw_scored_total`, `percent`,
  `scale_score | null` (from the form's table over **scored** items only).
- **FR-28.** WHEN every composite section of a run is finished THE SYSTEM SHALL compute
  `composite = round(mean(scale_score of composite sections))` (official rounding:
  .5 up) and persist it on the run; non-composite sections (Enhanced Science) are
  reported separately.
- **FR-29.** WHEN the learner reviews a finished section THE SYSTEM SHALL show each
  question with the learner's answer, the correct answer, per-choice rationale where
  the item has one, dwell time, visits, answer changes, flag, and bookmark.

### 3.7 Strength / weakness analytics

- **FR-30.** THE SYSTEM SHALL compute, for a finished section and across all of the
  learner's finished runs, an `ExamAnalytics` read model with facets **subject
  (section)**, **reporting category**, **skill_id** (where the question carries one),
  **passage** (where applicable), and **difficulty**, each with: items, correct,
  accuracy, unanswered, mean dwell, and time-vs-accuracy quadrant counts
  (`fast_right`, `fast_wrong`, `slow_right`, `slow_wrong`; "fast/slow" = below/above
  the section's median dwell of the same run).
- **FR-31.** THE SYSTEM SHALL compute pacing signals per section attempt: unanswered
  count, unanswered run at the end (last-N-blank ⇒ ran out of time), time remaining at
  submit, and percent of items over 2× median dwell.
- **FR-32.** THE SYSTEM SHALL classify each facet as `strength` (accuracy ≥ 0.80 and
  ≥ 5 items), `weakness` (accuracy ≤ 0.60 and ≥ 5 items) or `insufficient_data`
  (fewer than 5 items → **never** a label from one or two questions).
- **FR-33.** THE SYSTEM SHALL emit ordered, deterministic **recommendations**, each
  tied to a rule and the facet evidence that fired it (e.g. `pacing`: ≥ 3 trailing
  unanswered; `careless`: `fast_wrong` ≥ 30 % of wrong; `knowledge_gap`: a `weakness`
  facet with `slow_wrong` majority; `revise_flagged`: flagged ∧ wrong ≥ 1), and SHALL
  emit none when no rule fires (no filler advice).
- **FR-34.** WHEN a run has at least one finished section THE SYSTEM SHALL show the
  analytics on the run's results page; `/learn/progress` SHALL show a distinct
  "Exam performance" panel sourced **only** from `ExamAnalytics`, never mixed into the
  FSRS mastery cards.

## 4. Data model / contracts

All new; nothing existing changes shape. Dual-dialect (pg + sqlite) like every engine
table. Timestamps are ISO strings on the wire, `bigint`/`integer` ms in the DB per
the existing convention.

### 4.1 Wire (`lib/wire/exam_entities.ts`, zod)

```
ExamForm        { id, title, blueprint: "test01" | "preact-secure-legacy" | "act-enhanced",
                  composite_sections: SectionCode[], sections: ExamSection[] }
ExamSection     { code: "english"|"math"|"reading"|"science", title, minutes,
                  choice_count: 4|5, directions, composite: boolean,
                  scale_table: Record<rawScored, scale> | null,
                  questions: ExamQuestion[] }
ExamQuestion    = Question & { reporting_category: string | null, scored: boolean,
                  passage: string | null }
ExamRun         { id, learner_id, form_id, created_at, composite: number | null }
ExamSectionAttempt
                { run_id, section_code, status: "not_started"|"in_progress"|"submitted"|"expired",
                  started_at | null, finished_at | null, deadline_at | null,
                  raw_correct | null, raw_scored_total | null, scale_score | null,
                  time_remaining_ms_at_submit | null }
ExamRunItem     { run_id, section_code, question_id, ordinal,
                  chosen_letter | null, correct: boolean | null,
                  dwell_ms, visits, answer_changes,
                  first_answered_at | null, dwell_at_first_answer_ms | null,
                  flagged_in_section: boolean, bookmarked: boolean, updated_at }
ExamAnalytics   { scope: {learner_id, run_id | null}, facets: Facet[], pacing: Pacing[],
                  recommendations: Recommendation[] }
Facet           { kind: "subject"|"category"|"skill"|"passage"|"difficulty", key,
                  items, correct, unanswered, accuracy | null, mean_dwell_ms | null,
                  quadrants: {fast_right, fast_wrong, slow_right, slow_wrong},
                  label: "strength"|"weakness"|"insufficient_data" }
Recommendation  { rule: "pacing"|"careless"|"knowledge_gap"|"revise_flagged"|…,
                  facet_ref, evidence: string, priority: number }
```

### 4.2 Tables (migration `0005_exam_runs`)

`exam_run` (id pk, learner_id, form_id, created_at, composite nullable) ·
`exam_section_attempt` (pk (run_id, section_code), status, started_at, finished_at,
deadline_at, raw_correct, raw_scored_total, scale_score, time_remaining_ms_at_submit) ·
`exam_run_item` (pk (run_id, section_code, question_id), ordinal, chosen_letter,
correct, dwell_ms, visits, answer_changes, first_answered_at,
dwell_at_first_answer_ms, flagged_in_section, bookmarked, updated_at).
Indexes: `(learner_id, form_id)` on `exam_run`; `(run_id, section_code)` on items.
Analytics is **computed, not stored** (a read model over items; §7 determinism).

### 4.3 Ports / seam

New port `lib/ports/engine/exam_run_repo.ts` (one interface: `startRun`,
`beginSection`, `upsertItem`, `upsertItems`, `finishSection`, `getRun`,
`listRunsByLearner`, `listItems`, `setBookmark`), implemented by the Drizzle adapter
and exposed browser-side through `HttpEngineDb` → the generic BFF dispatcher
`POST /api/engine/db/<method>` → `pgEngineDb` exactly as ADR-0038 prescribes
(per-method disposition: all fine-grained, learner-scoped, `learnerId`-first so the
dispatcher's `LEARNER_ARG` override enforces FR-3; **no** server-only content
writes). `EngineDb` grows by the same method set (32 → 41; the plan lists them). Form content is a **static registry**
(`lib/adapters/engine/exam_forms/`), phase 1 = Test-01 English via the existing
`TEST01_SERVED_QUESTIONS`; the registry shape is the step-2 landing zone for the
private form JSON.

### 4.4 Analytics

Pure module `components/exam/exam_analytics.ts` (`ExamRunItem[] + ExamSection[] →
ExamAnalytics`), node-testable, no React, no I/O. Recommendation rules are a data
table (rule id → predicate → message template) so adding a rule is a row, not a
branch.

## 5. Invariants & security boundaries

- **Frontend Ring layering (F-R1…F-R9, A2/A3, P1).** Reducer + analytics are pure
  modules under `components/exam/`; pages are thin `'use client'` glue (B1 comment);
  one port per file; the Drizzle adapter imports only ports/wire/SDK; `HttpEngineDb`
  conformance test extended for the new methods.
- **ADR-0038 seam respected.** No new network shape; new BFF handlers follow the
  existing `/api/engine/*` family (auth, learner scoping, opaque error wrapping,
  `.onConflictDoNothing`/upsert idempotency in the adapter).
- **Test exclusivity (split-spec FR-1).** Exam items are never inserted into
  `test_item`/practice bank; the analytics never writes `skill_state`; an
  architecture test asserts no import from `components/exam/**` or `exam_run_repo`
  into the scheduler/quiz modules and vice-versa.
- **Root invariants #1–#8 untouched** (frontend-only; no Python, no `trust/`, no
  graph node). No new `pyproject.toml` or `package.json` dependency.
- **⚠️ Ask first fired:** new horizontal repo seam + new abstraction (analytics read
  model) → **one ADR** at plan stage (`docs/adr/0040-exam-module.md`): what the module
  buys, and the rejected alternatives (extend Test Mode in place; reuse
  `quiz_session`/`attempt` with a `mode` discriminator; store analytics rows).
- **Privacy.** Timing and flags are learner-scoped behavioral data, read only by the
  learner's own views; no new logging of answers.

## 6. Edge cases

- **Reload mid-section** → server `started_at` restores the countdown; items restore
  answers/flags; only the current question's un-flushed dwell (≤ debounce window) is
  lost (FR-14, FR-21).
- **Return after the deadline** → `expired`, saved answers graded (FR-1).
- **Two tabs / two devices on one in-progress section** → both write idempotent
  upserts; dwell monotonic-max (FR-4); last `chosen_letter` wins by `updated_at`.
- **Clock skew** → countdown uses server `started_at` + client offset sampled at
  begin; dwell uses `performance.now()` deltas only (never wall-clock subtraction).
- **Tab hidden for the whole section** → dwell ≈ 0 while the section clock still
  expires (official: the clock never pauses).
- **Section with unscored items** (Enhanced ACT) → they render and are answered
  normally, count in `items` for review, but not in `raw_scored_total` or scale.
- **5-choice section in the registry before a renderer exists** → FR-6 load-time
  assertion also rejects `choice_count` unsupported by the renderer (phase 1: only 4).
- **All items unanswered at expiry** → raw 0, analytics facets `insufficient_data`,
  recommendations = [`pacing`] only.
- **Median dwell undefined** (one item, or all dwell 0) → quadrants `null`, no
  `careless`/`knowledge_gap` rule can fire (AP-6: undecidable → `null`).
- **Composite on a form where a composite section is missing entirely** (phase-1
  Test-01 English-only form) → `composite_sections = ["english"]` by the form's own
  declaration, so composite = English scale (or `null` when no table, FR-7).

## 7. Non-functional requirements

- **Determinism.** Injected `now()`/monotonic clock seams; analytics and scoring are
  pure functions with fixture-driven L1 tests; rounding rules stated (composite .5 up).
- **Idempotency & durability.** Item upserts; at-most-one grade per section attempt
  (finishing an already-finished attempt is a no-op returning the stored result).
- **Latency.** Item flush is debounced (≤ 1 write per question navigation); section
  begin/finish are single round-trips; analytics over one learner's items is O(n).
- **Reversibility.** Additive tables + module; Test Mode untouched; feature reachable
  only via its own route/nav entry.
- **No live LLM calls** anywhere in this spec; nothing on the CI hot path beyond
  vitest + architecture tests.

## 8. Test plan

Failure paths first. L1 = vitest pure modules; L2 = BFF handler/adapter tests
against sqlite + `HttpEngineDb` conformance; L4 = Playwright (chromium smoke tier).

| FR | Test | Layer | In gate? |
|----|------|-------|----------|
| FR-1 | `exam_section_reducer.test::deadline passed on load ⇒ expired, writes refused` | L1 | yes |
| FR-2 | `exam_run_repo.test::finished attempt cannot reopen` | L2 | yes |
| FR-3 | `api/engine/exam handler test::foreign learner ⇒ 403/404` | L2 | yes |
| FR-4 | `exam_run_repo.test::duplicate upsert applied once; dwell monotonic-max` | L2 | yes |
| FR-5 | `use_exam_section.test::offline buffer flushes; failed flush ⇒ not-saved state` | L1 | yes |
| FR-6 | `exam_forms.test::empty form/section throws at load` | L1 | yes |
| FR-7 | `exam_scoring.test::no scale table ⇒ scale null` | L1 | yes |
| FR-8 | `exam_scoring.test::composite null until all composite sections finished` | L1 | yes |
| FR-9 | `exam_entities.test::zod round-trip + snapshot` | L1 | yes |
| FR-10–12 | `exam_home.test::status per section; in_progress blocks second start` | L1 | yes |
| FR-13–16 | `exam_section_reducer.test` + `e2e/learn/exam.spec::countdown, 5-min warning, auto-submit (?dur=)` | L1 + L4 | L1 yes / L4 smoke |
| FR-17–18 | `exam_section_reducer.test::navigate/change/clear; submit-with-blanks confirms` | L1 | yes |
| FR-19–22 | `exam_dwell.test::visibility pause, sum over visits, first-answer fields immutable, visits/changes counts` (injected clock) | L1 | yes |
| FR-23–25 | `exam_section_reducer.test::flag toggle + navigator states`; `exam_review.test::bookmark + to-revise filter` | L1 | yes |
| FR-26 | `frontend/tests/architecture/test_exam_isolation.test.ts` (ts-morph; no scheduler/quiz ↔ exam imports; no `skill_state` write) | arch | yes |
| FR-27–29 | `exam_scoring.test::grade once; scored-only raw; review VM fields` | L1 | yes |
| FR-30–33 | `exam_analytics.test::facets, quadrants, labels (≥5 rule), pacing, recommendation rules fire/don't fire` | L1 | yes |
| FR-34 | `progress screen test::Exam panel sourced from ExamAnalytics only` + e2e results page | L1 + L4 | yes / smoke |

Every new test is **seen to fail first** (red) before its implementation.

## 9. Definition of Done

- [ ] All FRs implemented; each has a passing test that was seen to fail first.
- [ ] `make check` green; frontend `vitest run` + `tsc` green; `tests/architecture/`
      green (paste actual counts).
- [ ] ADR-0040 accepted (index + log entries); `decisions.md` lines for the
      ≥5-items label threshold and the median-dwell quadrant definition.
- [ ] Migration `0005` runs on pg + sqlite; `schema.parity.test` green.
- [ ] Test Mode (`/learn/test`) untouched and its e2e still green.
- [ ] §2.1 non-goals untouched: no real-form loading, no FSRS write, no LLM narrative.
- [ ] **§10 arch-sweep criteria (FR-35…FR-41) implemented**; ADR-0041 accepted;
      `test_exam_isolation` + `test_exam_no_client_served_keys` guards green (each red-first).

---

## 10. Architecture-sweep amendments (2026-09-02)

> Folds the ratified [arch-lifecycle sweep](../../.arch/worksheets/exam-module-official-rules/RATIFICATION.md)
> into testable EARS criteria. Cross-refs: [ADR-0040](../adr/0040-exam-module-durable-runs-analytics.md)
> (strengthened — sync/async posture + business value), [ADR-0041](../adr/0041-exam-answer-key-posture.md)
> (answer-key posture, **Accepted** Option A), `decisions.md` (2026-09-02 sweep entry: R4/R5/R6/microkernel).
> These **strengthen or add to** the §3 FRs; nothing above is weakened.

- **FR-35 (answer-key posture — ADR-0041).** WHERE a form is **DB-served**, THE SYSTEM
  SHALL NOT ship the answer-bearing fields (`answer_letter`, `per_choice_rationale`,
  `why_correct_md`, `why_tempted_md`) to the client while the exam key-posture flag =
  `"client"`. The phase-1 **client-bundled** Test-01 slice is the *recorded accepted-risk
  exemption*. Guard: **`frontend/tests/architecture/test_exam_no_client_served_keys.test.ts`**
  (frontend TS/ts-morph — *not* root `tests/architecture/`, which is Python) + a frontend
  const posture flag `components/exam/exam_key_posture.ts`, a real code switch (not
  env-overridable) conceptually mirroring ADR-0013's `coach_test_mode_posture.py`; the flag
  flips to `"server"` on the first DB-served official form.
- **FR-36 (buffer durability — R2, full ladder).** WHILE a section is `in_progress` THE
  SYSTEM SHALL mirror the write buffer to `localStorage` and flush it on
  `pagehide`/`visibilitychange=hidden` via `navigator.sendBeacon`; IF a flush fails THEN
  THE SYSTEM SHALL retry with backoff; and THE SYSTEM SHALL NOT mark a section
  scored-complete while any buffered write is unflushed (strengthens FR-5).
- **FR-37 (begin idempotency — R5).** IF `beginSection` is retried for a
  `(run_id, section_code)` already `in_progress` THEN THE SYSTEM SHALL return the existing
  `started_at` (keep-first) and SHALL NOT reset the deadline (no free time).
- **FR-38 (learner-scoping is connascence of name — R4).** THE SYSTEM SHALL scope every
  exam `EngineDb` method by a **named** learner argument (not positional); an architecture
  test SHALL assert every exam method appears in the dispatcher learner-arg map, and the
  dispatcher default SHALL be **deny**.
- **FR-39 (one dwell-merge rule — R6).** THE SYSTEM SHALL compute dwell `monotonic-max` via
  a single shared pure function referenced by BOTH the client reducer and the server
  upsert; a fixture SHALL replay identical input through both and assert identical output.
- **FR-40 (parity + concurrency fidelity — R8/R15).** THE SYSTEM SHALL run the
  two-device concurrency + `monotonic-max` assertions against **real Postgres** in CI (not
  only sqlite), and `schema.parity.test` SHALL assert constraints/defaults/PK-FK, not only
  column names.
- **FR-41 (isolation guard ordering — R1).** THE isolation guard (FR-26,
  `test_exam_isolation`) SHALL be authored **red-before-green ahead of any
  `components/exam/**` code**, asserting on the **resolved module graph** (incl. type-only
  + dynamic imports) with a **red fixture** proving it fails on a forbidden edge.

### 10.1 Non-goals reaffirmed
- Server-side grading (ADR-0041 Option B) is the **committed evolution**, enabled at the
  DB-served-form trigger — **not** built in phase-1 (FR-35 keeps phase-1 client-grading).
- The C4→Write-Buffer split is a component boundary (plan §6), not a new FR.
