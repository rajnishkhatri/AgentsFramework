---
title: 'Sprint D1 — Playwright validation of the Quiz session-frame chrome · Spec'
type: spec
status: Draft — 2026-07-10
date: 2026-07-10
owner: Rajnish Khatri
epic: D
derives_from: docs/plan/preact-parity-D1-quiz-frame.spec.md
related:
  - docs/plan/preact-parity-D1-quiz-frame.spec.md         # the code spec this validates
  - docs/plan/preact-parity-D1-quiz-frame.plan.md         # the code plan whose tasks this covers at L4
  - docs/plan/preact-parity-sprint-board-D.md             # §Sprint D1 gates on this L4 evidence
  - frontend/e2e/learn/quiz-progress.spec.ts              # PATTERN — L4 for S4 progress bar
  - frontend/e2e/learn/quiz-done-state.spec.ts            # PATTERN — L4 for S5 done-state
  - frontend/e2e/learn/quiz-rotation.spec.ts              # PATTERN — data-* hook read + skip
  - frontend/playwright.config.ts                         # `learn-e2e` project (video on)
  - docs/Architectures/PLAYWRIGHT_TESTING_ARCHITECTURE.md # T1/T2/T3 tier model
  - research/tdd_agentic_systems_prompt.md                # L4 Behavioral Validation (Agentic Testing Pyramid)
governs:
  - frontend/e2e/learn/quiz-frame.spec.ts                 # NEW — the file this spec creates
---

# Sprint D1 — Playwright validation of the Quiz session-frame chrome

> **What / why split.** This spec is the *what* for the **L4 (Behavioral
> Validation)** evidence gate on Sprint D1. The **L1 (unit) evidence** the
> code plan already produces (Vitest table tests for the translator + jsdom
> tests for `QuizView`) proves the pieces work. This L4 evidence proves the
> **wired behaviour a learner actually sees** in a real browser on the
> `/learn/quiz` route: chip renders, End session closes-and-routes, timer
> reveals + ticks. No new abstraction, no ADR — this is a fifth spec file in
> the D1 bundle, mirroring how S4 and S5 each pair a code spec with a
> Playwright spec of their own.

---

## 1. Goal

Prove — in a real browser, video on — that the three D1 sub-features work
end-to-end on `/learn/quiz`:

- **Q-7** — the skill chip renders above the item, tinted by the served
  skill's `accent_var`, and persists across the `answering → reviewing` sub-
  states without flicker.
- **Q-8** — the End-session control closes the current session with the
  running tally and routes the learner to the dashboard (`/learn`), NOT to
  the Summary route (`/learn/summary`); Finish continues to route to Summary.
- **Q-9** — the timer starts **collapsed** on every item, reveals on click
  to a `m:ss` reading derived from `session.started_at`, ticks forward, and
  resets to **collapsed** when the learner advances to the next item.

For the learner ("Maya") the DoD is: they can see which skill they're on,
they have an honest exit that lands them home, and they can consult a clock
without being surveilled by one. For the reviewer the DoD is: a video
artifact per test that shows the wired behaviour, plus the four gate
selectors (`quiz-skill-chip`, `quiz-end-session`, `quiz-timer-reveal`,
`quiz-timer`) resolving on the live page.

## 2. Context

**Precedent — one L4 spec per capability.** The D1 sub-features are three
distinct capabilities that share the same header region. The precedent set
by S4 (progress bar → [`quiz-progress.spec.ts`](../../frontend/e2e/learn/quiz-progress.spec.ts))
and S5 (done-state → [`quiz-done-state.spec.ts`](../../frontend/e2e/learn/quiz-done-state.spec.ts))
is: **one Playwright spec file per code-sprint**, grouping its FR-level
`test.describe` blocks. D1 fits that mould: one `quiz-frame.spec.ts` with
three `describe` blocks (chip, End, timer) and a small shared harness. This
matches how the sprint board describes D1 as "one sprint, three sub-features".

**Tier — pure T1 on the `learn-e2e` project.** Per
[`playwright.config.ts:141-155`](../../frontend/playwright.config.ts:141)
the `learn-e2e` project runs on `Desktop Chrome` with **video on**, is
scoped to `e2e/learn/`, and requires **no auth / no backend / no LLM** — the
`/learn` engine is Frontend-Ring-local (ADR-0005). This is where D1's L4
evidence belongs. The chat/full-stack projects `testIgnore: "learn/**"`, so
adding this file does not inflate any other tier's runtime.

**Skip pattern.** Every sibling learn spec uses the discipline "read a
sentinel, skip if the page didn't render (auth / env)"
([quiz-progress.spec.ts:69](../../frontend/e2e/learn/quiz-progress.spec.ts:69),
[quiz-done-state.spec.ts:68](../../frontend/e2e/learn/quiz-done-state.spec.ts:68))
— this is what keeps the L4 tier honest as a *behaviour* check, not an
environment stand-up. This spec inherits the same rule and reuses the
`counterText()` sentinel (the `[data-testid="quiz-progress"]` region shipped
in S4 is always present on a rendered quiz item).

**Cost budget.** All three sub-features exercise on the **first item** of a
freshly opened session. No spec needs to walk the full 30-item bounded
session to prove D1 — Q-9's tick is verified over ~2s of wall-clock; Q-8's
route is verified by one click on item 1. This keeps the whole file's
runtime under the 60s per-test default with no `test.setTimeout` bumps
required. (Contrast: the S5 done-state walk needs 180s to reach the boundary.)

**What the L1 layer already proves — and what this spec does NOT re-prove.**
The code plan's Vitest tests already cover: the translator's `null` join
path (FR-Q7-1), the reducer's `end_session` transition table (FR-Q8-6), the
`formatElapsedFromStartedAt` clamp cases (FR-Q9-4 edges). This L4 spec
covers only the **wired path** — the fraction of the FRs that a JSDOM /
node harness cannot observe: chip rendering with a real `accent_var` var
resolving, real route change on End, real 1s tick over real wall-clock. The
test plan §8 tags the L4 FRs against their L1 partners so a reviewer can
see the coverage split explicitly, no silent skip.

## 3. Functional requirements (EARS)

Failure paths / skip discipline first. Every FR here maps to one `test(...)`
in `e2e/learn/quiz-frame.spec.ts`, phrased as a binary outcome the video +
selectors prove.

### Harness / skip (structural)

- **FR-L1 (behavioural, not environment).** IF the quiz item did not render
  on `/learn/quiz` (auth / env / dev-server gap) THEN the test SHALL be
  skipped via `test.skip(sentinel === "", "…")` — MUST NOT fail the run.
  Same sentinel as siblings: `[data-testid="quiz-progress"]` text (already
  a stable S4 hook).
- **FR-L2 (no auth required — `learn-e2e` project only).** THE SYSTEM SHALL
  place this spec file at `e2e/learn/quiz-frame.spec.ts` so `playwright.config.ts`'s
  `learn-e2e` project picks it up (video on) AND the chat/full-stack
  projects ignore it via `testIgnore: "learn/**"`.
- **FR-L3 (no `test.setTimeout` bump needed).** THE SYSTEM SHALL prove
  every FR on the FIRST item of a freshly opened session — no full 30-item
  walk. Individual tests SHALL complete under the 60s per-test default.

### Q-7 — skill chip

- **FR-P7-1 (chip visible on first item).** WHEN the page opens on
  `/learn/quiz` THE SYSTEM SHALL render exactly one
  `[data-testid="quiz-skill-chip"]` element in the frame region with a
  non-empty accessible text (the skill name).
- **FR-P7-2 (chip persists into `reviewing`).** WHEN the learner answers
  the first item (A → Submit → feedback visible) THE SYSTEM SHALL keep
  exactly one `[data-testid="quiz-skill-chip"]` element in the DOM whose
  text is IDENTICAL to the pre-submit reading. Zero flicker, zero
  duplication.
- **FR-P7-3 (chip carries the served skill's accent).** THE SYSTEM SHALL
  render the chip's dot glyph with a computed CSS color that resolves from
  a `--color-bucket-*` variable (i.e. the color is not `""` and not the
  fallback `initial`). This is the wired-through evidence of `accent_var`,
  the join the L1 test cannot observe.
- **FR-P7-4 (chip is honest-absent when no join — L1-covered, not
  re-proved here).** *L1 coverage:* `quiz_item_vm.test.ts::skill_id with no
  match → skillName null`. No L4 test authored (the seeded bank always
  matches).

### Q-8 — End session

- **FR-P8-1 (End control renders on first item).** WHEN the page opens on
  `/learn/quiz` THE SYSTEM SHALL render exactly one
  `[data-testid="quiz-end-session"]` element in the frame region, visible
  and interactive.
- **FR-P8-2 (End routes to the dashboard, NOT Summary).** WHEN the learner
  clicks `[data-testid="quiz-end-session"]` on the first item (before any
  submit) THE SYSTEM SHALL navigate the page to a URL matching `/learn` and
  NOT matching `/learn/summary`. The transition SHALL complete under the
  10s Playwright default.
- **FR-P8-3 (End persists into `reviewing`).** WHEN the learner answers
  the first item (A → Submit → feedback visible) THE SYSTEM SHALL keep
  `[data-testid="quiz-end-session"]` visible and interactive on the
  reviewing screen alongside the existing `quiz-next` / `quiz-finish`
  controls.
- **FR-P8-4 (Finish still routes to Summary — regression guard).** WHEN
  the learner answers the first item AND clicks `[data-testid="quiz-finish"]`
  THE SYSTEM SHALL navigate to a URL matching `/learn/summary?session=…`.
  End session's addition SHALL NOT collapse the Finish path into the
  dashboard route. FR-P8-2 and FR-P8-4 together assert the two exits stay
  distinct.
- **FR-P8-5 (End is idempotent under double-click — L1-covered).**
  *L1 coverage:* the reducer's `end_session` from `done` → no-op, plus
  `sessionRepo.close` idempotency (already tested). No L4 test authored.

### Q-9 — collapsible timer

- **FR-P9-1 (timer collapsed on first item).** WHEN the page opens on
  `/learn/quiz` THE SYSTEM SHALL render exactly one
  `[data-testid="quiz-timer-reveal"]` element AND zero
  `[data-testid="quiz-timer"]` elements — the default is collapsed, no
  clock text present.
- **FR-P9-2 (click reveal shows the clock).** WHEN the learner clicks
  `[data-testid="quiz-timer-reveal"]` THE SYSTEM SHALL render exactly one
  `[data-testid="quiz-timer"]` element whose text matches `/^\d+:\d{2}$/`
  (an `m:ss` reading).
- **FR-P9-3 (the clock ticks forward).** WHILE the timer is revealed and
  the learner idles ~2 seconds THE SYSTEM SHALL update
  `[data-testid="quiz-timer"]`'s text to a reading whose total elapsed
  seconds is STRICTLY GREATER THAN the reading captured before the idle.
  Ticking is real (setInterval), not stubbed. Formatting is `m:ss`.
- **FR-P9-4 (reveal resets to collapsed on `next`).** WHEN the learner
  reveals the timer, answers the first item, and advances to the next item
  via `quiz-next` THE SYSTEM SHALL render the next item's timer in the
  **collapsed** state (`quiz-timer-reveal` present, `quiz-timer` absent).
  The reveal state SHALL NOT carry across items (FR-Q9-7).
- **FR-P9-5 (elapsed does NOT reset on `next`).** WHEN a new item loads
  the `session.started_at` did not change, so a subsequent reveal SHALL
  show a reading GREATER than the initial `0:00` (the elapsed is
  session-scoped, not per-item — FR-Q9-4 / spec §Context).
- **FR-P9-6 (reveal + collapse edges — L1-covered).** *L1 coverage:* the
  jsdom cases already assert re-collapse from expanded, button semantics,
  and the `NaN` / null clamp table. No L4 test authored for the collapse
  path.

### Cross-cutting (structural)

- **FR-X1 (no new port surface exercised).** THE spec SHALL exercise only
  the existing `/learn/quiz` route and existing `data-testid` selectors
  plus the four D1 additions (`quiz-skill-chip`, `quiz-end-session`,
  `quiz-timer-reveal`, `quiz-timer`). It SHALL NOT probe the engine bag,
  the wire kernel, or any adapter directly.
- **FR-X2 (no regression to sibling learn specs).**
  `quiz-progress.spec.ts`, `quiz-done-state.spec.ts`, and
  `quiz-rotation.spec.ts` MUST remain green with this file present. Their
  selectors (`quiz-progress`, `quiz-progress-fill`, `quiz-done-banner`,
  `quiz-next`, `quiz-finish`, `data-skill`, `choice-A`, `quiz-submit`,
  `feedback-banner`) are unchanged.
- **FR-X3 (video artefact per test).** THE SYSTEM SHALL produce one video
  per test (the `learn-e2e` project's `video: "on"` default at
  [`playwright.config.ts:152`](../../frontend/playwright.config.ts:152));
  the spec author SHALL NOT override that setting.

## 4. Data model / contracts

**No production wire / schema change.** The spec reads:

| Selector / signal | Provenance | Consumed for |
|---|---|---|
| `[data-testid="quiz-skill-chip"]` | D1 code plan T1.4 (new in `QuizView`) | FR-P7-1/2/3 |
| `[data-testid="quiz-end-session"]` | D1 code plan T2.4 (new in `QuizView`) | FR-P8-1/2/3 |
| `[data-testid="quiz-timer-reveal"]` | D1 code plan T3.4 (new in `QuizView`) | FR-P9-1/2/4/5 |
| `[data-testid="quiz-timer"]` | D1 code plan T3.4 | FR-P9-2/3 |
| `[data-testid="quiz-progress"]` (sentinel) | S4-shipped | skip discipline |
| `[data-testid="choice-A"]` + `quiz-submit` + `feedback-banner` | pre-D1 | driving the answer + reviewing transitions |
| `[data-testid="quiz-next"]` + `quiz-finish` | pre-D1 | FR-P8-4, FR-P9-4 |

**No new fixtures, no seed override, no `addInitScript`.** The spec walks the
default dev-seed bank (`Maya` + 171 items over `InMemoryEngineDb`), same as
the S4/S5 specs. No auth setup, no `MOCK_MIDDLEWARE`, no
`E2E_AUTHENTICATED`.

## 5. Invariants & security boundaries

- **F-R1 / F-R2 (Frontend Ring):** untouched — the spec only *reads* the
  DOM; it does not import adapters, ports, or SDK types.
- **Root [`AGENTS.md`] Architecture Invariants #1–#8:** N/A — no Python
  touched.
- **`⚠️ Ask first` triggers:** none. Playwright is an existing dev
  dependency; adding a `.spec.ts` under `e2e/learn/` is a routine addition
  the S4/S5 specs already precedented. No ADR.
- **G8 (test-mass-rewrite gate):** N/A — this spec adds new tests, does not
  weaken existing ones.
- **Live-LLM in CI ban:** upheld — the whole `learn-e2e` project is T1
  (seeded engine, no LLM, no network beyond the local dev server).
- **PII / secrets in video:** none — the walk uses the seeded learner
  "Maya", not a real WorkOS session; nothing sensitive is recorded.

## 6. Edge cases

- **First item's skill is a valid seeded skill.** The join always hits;
  FR-P7-1/3 read a real accent color. No null-chip edge to prove at L4.
- **`session.started_at` a few ms before page load.** The first `m:ss`
  reading could round to `"0:00"` or `"0:01"`; FR-P9-2 asserts the FORMAT
  (`/^\d+:\d{2}$/`), not a specific numeric value.
- **Wall-clock idle length for tick assertion.** FR-P9-3 idles ~2s (>=
  1_000ms of `page.waitForTimeout`) to guarantee a tick; a longer idle
  would slow the suite without buying evidence.
- **Feedback-banner selector absence.** All learn specs already wait for
  `feedback-banner` with a 10s timeout ([quiz-progress.spec.ts:51](../../frontend/e2e/learn/quiz-progress.spec.ts:51)).
  If it never appears the test fails on that assertion, not on a downstream
  chip / End check — a legible failure mode.
- **A learner-provided seed with `target_count: null`.** Not exercised —
  the L4 spec walks the default seed only. FR-Q9's session-elapsed
  derivation is unaffected by `target_count`; the L1 tests cover the null
  path.
- **Route matcher `/learn` vs `/learn/quiz` vs `/learn/summary`.** FR-P8-2
  MUST assert the URL matches `/learn` AND NOT `/learn/summary` AND NOT
  `/learn/quiz` — three checks avoid a false pass on "still on /learn/quiz"
  or a false pass on "landed on /learn/summary".

## 7. Non-functional requirements

- **Runtime budget:** whole file under **90s wall-clock** on the
  `learn-e2e` project (~5 tests × ≤15s each; the tick test dominates at ~5s
  incl. reveal + idle + assertion). No `test.setTimeout` overrides.
- **Determinism:** every assertion reads a stable selector or a bounded
  numeric comparison. No timing-sensitive equality checks (FR-P9-3 uses
  strict-greater-than, not exact-equals).
- **Reversibility:** additive — deleting `e2e/learn/quiz-frame.spec.ts`
  restores today's e2e footprint exactly.
- **No live LLM anywhere** — pure T1.
- **Cost:** one dev-server on the local machine; zero network egress; zero
  cloud budget.
- **Artefact:** one `.webm` video per test (learn-e2e default) + a trace
  on failure. Reviewers open the video from the Playwright report.

## 8. Test plan

Each FR maps to one Playwright `test(...)` inside a `test.describe`.
Failure/skip discipline first. Every L4 FR is annotated with the L1 test
that already covers its edge cases (so a reviewer sees the L1↔L4 split is
deliberate, not a gap).

| FR | Test (in `quiz-frame.spec.ts`) | Layer | L1 partner |
|----|--------------------------------|-------|-----------|
| FR-L1 | (harness) `test.skip` on missing `quiz-progress` sentinel | L4 harness | — |
| FR-L2 | (config) file placed under `e2e/learn/`; verified by lint of the file path | L4 config | — |
| FR-L3 | (structural) no `test.setTimeout` in the file | L4 config | — |
| FR-P7-1 | `describe('Q-7 skill chip')::first item shows a non-empty chip` | L4 | `quiz_item_vm.test.ts::match populates name` |
| FR-P7-2 | `describe('Q-7 skill chip')::chip persists across answering→reviewing` | L4 | `QuizView.test.tsx::chip present in both phases` (T1.8) |
| FR-P7-3 | `describe('Q-7 skill chip')::dot glyph resolves an accent color` | L4 | `QuizView.test.tsx::renders chip with accent style` (T1.3) |
| FR-P7-4 | (L1-covered, not in file) | — | `quiz_item_vm.test.ts::no-match → null` (T1.1b) |
| FR-P8-1 | `describe('Q-8 End session')::End control visible on first item` | L4 | `QuizView.test.tsx::quiz-end-session renders when enabled` (T2.3a) |
| FR-P8-2 | `describe('Q-8 End session')::End routes to /learn, not /learn/summary` | L4 | `quiz_page.test.tsx::End calls closeSession + push('/learn')` (T2.5) |
| FR-P8-3 | `describe('Q-8 End session')::End persists into reviewing` | L4 | (implicit in T2.3a — no L1 partner needed) |
| FR-P8-4 | `describe('Q-8 End session')::Finish still routes to /learn/summary` | L4 (regression) | `quiz_screen_reducer.test.ts::finish still to done` (T2.1e) |
| FR-P8-5 | (L1-covered) | — | `quiz_screen_reducer.test.ts::end_session from done → no-op` (T2.1d) |
| FR-P9-1 | `describe('Q-9 timer')::timer collapsed by default` | L4 | `QuizView.test.tsx::default collapsed` (T3.3b) |
| FR-P9-2 | `describe('Q-9 timer')::click reveal → m:ss text renders` | L4 | `QuizView.test.tsx::click reveal → quiz-timer` (T3.3c) |
| FR-P9-3 | `describe('Q-9 timer')::the clock ticks forward` | L4 | `quiz_frame_timer.test.ts` covers formatting; L4 alone can prove real tick |
| FR-P9-4 | `describe('Q-9 timer')::reveal resets to collapsed on next item` | L4 | `QuizView.test.tsx::item_loaded resets reveal` (T3.3e) |
| FR-P9-5 | `describe('Q-9 timer')::elapsed does not reset on next item` | L4 | (L4-only — session-scoped derivation not observable in jsdom without wall-clock advance) |
| FR-P9-6 | (L1-covered) | — | `QuizView.test.tsx::collapse from expanded` (T3.3d), `quiz_frame_timer.test.ts` (T3.1) |
| FR-X1 | (structural) grep the spec — no `import` from `frontend/lib/*` | grep | — |
| FR-X2 | run sibling learn specs alongside → all green | L4 | — |
| FR-X3 | Playwright report contains one `.webm` per test | artifact | — |

**Cross-file coverage rule:** every D1 spec FR (Q-7, Q-8, Q-9) has at least
one L1 test + at least one L4 test, EXCEPT the pure-derivation cases
(FR-P7-4, FR-P8-5, FR-P9-6) which the L1 layer proves definitively and the
L4 layer would only re-prove wastefully. The spec table above makes that
split explicit so §Analyze can grep it.

## 9. Definition of Done

- [ ] All in-scope FRs implemented; each has one Playwright `test(...)`
      whose assertion(s) were **seen to fail first** against a pre-D1 tree
      (grep-checkable: run the file BEFORE any D1 code lands; it must red
      on the missing `quiz-skill-chip` / `quiz-end-session` /
      `quiz-timer-reveal` selectors — the "watched red" evidence root
      `AGENTS.md` requires).
- [ ] Whole file green under `npm run test:e2e:learn -- e2e/learn/quiz-frame.spec.ts`
      after D1 code lands; command output pasted, not summarized.
- [ ] `npm run test:e2e:learn` (full learn-e2e suite) green — sibling
      specs `quiz-progress.spec.ts`, `quiz-done-state.spec.ts`,
      `quiz-rotation.spec.ts`, `bank-integration.spec.ts` unchanged and
      passing (FR-X2). Output pasted.
- [ ] `frontend` `tsc --noEmit` → 0 errors (the spec is TS-compiled).
      Output pasted.
- [ ] `pytest tests/architecture/ -q` green (baseline gate — no Python
      touched, but the constitution stays green).
- [ ] One video (`.webm`) per test is present in the Playwright HTML
      report; a reviewer link (or the raw `test-results/` path) is
      recorded in the sprint board §Sprint D1 evidence section.
- [ ] The sprint board §Sprint D1 evidence section (added by the code
      plan's T5.3) links to this Playwright spec + the video/report path.
- [ ] No ADR. No new dep. No new fixture. No `test.setTimeout` bump. If
      any of those became necessary during implementation, this spec is
      wrong — escalate to `sdd-replan`, don't paper over.

---

## Premise audit (Stage 1 discipline — verified against the working tree)

Every load-bearing claim this spec makes about the Playwright layout was
verified against the current tree.

| Premise | Status | Evidence (`file:line`) |
|---|---|---|
| `learn-e2e` Playwright project exists, video on, testDir = `./e2e/learn/` | **verified** | [`playwright.config.ts:141-155`](../../frontend/playwright.config.ts:141) |
| Chat / full-stack projects `testIgnore: "learn/**"` so a new file there won't double-run | **verified** | [`playwright.config.ts:118,124,130,133,138`](../../frontend/playwright.config.ts:118) |
| `npm run test:e2e:learn` script exists and runs the `learn-e2e` project | **verified** | `frontend/package.json` — line 43 (`"test:e2e:learn": "playwright test --project=learn-e2e"`) |
| The skip-sentinel pattern is used by every learn spec | **verified** | [quiz-progress.spec.ts:69](../../frontend/e2e/learn/quiz-progress.spec.ts:69), [quiz-done-state.spec.ts:68](../../frontend/e2e/learn/quiz-done-state.spec.ts:68), [quiz-rotation.spec.ts:51](../../frontend/e2e/learn/quiz-rotation.spec.ts:51) |
| `[data-testid="quiz-progress"]` is a stable sentinel (S4-shipped) | **verified** | S4 spec §10 evidence + [`components/quiz/QuizProgress.tsx:38`](../../frontend/components/quiz/QuizProgress.tsx:38) |
| The `A → Submit → feedback-banner` walk pattern is the sibling learn specs' harness | **verified** | [quiz-progress.spec.ts:48-57](../../frontend/e2e/learn/quiz-progress.spec.ts:48), [quiz-done-state.spec.ts:43-55](../../frontend/e2e/learn/quiz-done-state.spec.ts:43), [quiz-rotation.spec.ts:33-40](../../frontend/e2e/learn/quiz-rotation.spec.ts:33) |
| `learn-e2e` is pure T1 — no auth, no LLM, no backend | **verified** | quiz-progress.spec.ts comment §L4 + config §T1 comment; no `E2E_AUTHENTICATED` / `MOCK_MIDDLEWARE` in any learn spec |
| The four new D1 testids (`quiz-skill-chip`, `quiz-end-session`, `quiz-timer-reveal`, `quiz-timer`) are the code plan's contract | **verified** | D1 code plan §2 files-touched table; D1 code spec FR-Q7-2 / FR-Q8-3 / FR-Q9-2 / FR-Q9-3 |
| End-session's route target is `/learn` (dashboard route) | **verified** | [`nav_model.ts:65`](../../frontend/components/shell/nav_model.ts:65) — `id: "dashboard", route: COACH_BASE` = `/learn`; D1 code plan T2.6 |
| Finish's route target is `/learn/summary` | **verified** | [`quiz/page.tsx:174`](../../frontend/app/(coach)/learn/quiz/page.tsx:174) — `router.push(\`${screen("summary").route}?session=${session.id}\`)` |
| Video is captured for every learn-e2e test by default | **verified** | [`playwright.config.ts:152`](../../frontend/playwright.config.ts:152) — `video: "on"` on `learn-e2e` |

**No refuted premises.** One nuance to lock at plan time (§10 clarify): the
tick-idle length (`~2s` proposed) — cheaper alternatives (500ms) risk a
1-second race; longer (5s) buys nothing. §10 resolves.

## §10 Clarify — decisions to lock at plan time

Three questions the plan resolves; the spec holds room for either resolution.

1. **Tick-idle length for FR-P9-3.** Recommended: **`page.waitForTimeout(2100)`**
   — safely past a 1s tick with margin for the `setInterval(1000)` phase
   offset the reveal introduces. `1100` risks a same-second read (`0:00`
   → `0:00` reads as "not ticking" when the clock did tick at t=1000 but
   we read at t=1099). `5000` wastes 3s per test-run.
2. **Route matcher for FR-P8-2 / FR-P8-4.** Recommended: **`page.waitForURL(/\/learn(?:\?|$|\/[^s])/`)`** for End (matches `/learn`, `/learn?…`, `/learn/quiz` but NOT `/learn/summary`); **`page.waitForURL(/\/learn\/summary/)`** for Finish. Combined with a subsequent `expect(page.url()).not.toContain("/learn/summary")` on End, this avoids a false pass on "still on `/learn/quiz`" because Playwright's `waitForURL` requires the URL actually changes to match the regex. **Simpler equivalent** (plan may prefer): after clicking End, `expect(page).toHaveURL(/\/learn$/, { timeout: 10_000 })`, then `expect(page.url()).not.toContain("/learn/summary")`. Plan locks the exact matcher; either satisfies the FR.
3. **Do we run the whole D1 file once BEFORE any D1 code lands to prove the
   "watched red"?** Recommended: **yes** — commit the spec file first in
   its own commit, run once, confirm ALL new-selector assertions RED
   (skip clauses fire on sentinel first if the S4 selectors were still
   there; here they'd fail on the D1 selectors specifically). Paste the
   red output in the sprint board evidence section BEFORE landing any D1
   code. This is the SDD "red-first" discipline applied at the L4 layer,
   matching how the L1 tests are red-firsted per §5 of the code plan.
