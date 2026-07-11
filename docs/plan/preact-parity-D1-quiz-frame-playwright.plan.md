---
title: 'Sprint D1 — Playwright validation · Plan + Tasks'
type: plan
status: Draft — 2026-07-10
date: 2026-07-10
owner: Rajnish Khatri
epic: D
implements: docs/plan/preact-parity-D1-quiz-frame-playwright.spec.md
related:
  - docs/plan/preact-parity-D1-quiz-frame-playwright.spec.md   # the spec this implements
  - docs/plan/preact-parity-D1-quiz-frame.spec.md              # code spec (L1 partners)
  - docs/plan/preact-parity-D1-quiz-frame.plan.md              # code plan (T-numbers referenced)
  - frontend/e2e/learn/quiz-progress.spec.ts                   # pattern — S4 L4 spec
  - frontend/e2e/learn/quiz-done-state.spec.ts                 # pattern — S5 L4 spec
  - frontend/e2e/learn/quiz-rotation.spec.ts                   # pattern — data-* hook + skip
  - frontend/playwright.config.ts                              # learn-e2e project (video on)
---

# Sprint D1 — Playwright validation · Plan + Tasks

Implements [preact-parity-D1-quiz-frame-playwright.spec.md](preact-parity-D1-quiz-frame-playwright.spec.md).
One new file, no config change, no new dep → **no ADR**, **no `decisions.md`**
line (routine addition of a sibling `.spec.ts` under `e2e/learn/`, precedented
by S4's `quiz-progress.spec.ts` and S5's `quiz-done-state.spec.ts`).

---

## 1. Architecture / approach

**One spec file, three `describe` blocks, one shared harness.** Follows the
sibling learn-e2e specs exactly:

```
e2e/learn/quiz-frame.spec.ts
├── Shared harness (top of file)
│   ├── counterText(page)   ← copied verbatim from quiz-progress.spec.ts (sentinel for skip)
│   ├── answerToFeedback(page)   ← same shape as quiz-done-state.spec.ts:43-49
│   ├── answerAndAdvance(page)   ← same shape as quiz-progress.spec.ts:48-57
│   └── revealTimer(page)   ← D1-specific one-liner
├── describe('Q-7 skill chip')
│   ├── test('first item shows a non-empty chip', ...)          FR-P7-1
│   ├── test('chip persists across answering→reviewing', ...)   FR-P7-2
│   └── test('dot glyph resolves an accent color', ...)         FR-P7-3
├── describe('Q-8 End session')
│   ├── test('End control visible on first item', ...)          FR-P8-1
│   ├── test('End routes to /learn, not /learn/summary', ...)   FR-P8-2
│   ├── test('End persists into reviewing', ...)                FR-P8-3
│   └── test('Finish still routes to /learn/summary', ...)      FR-P8-4
└── describe('Q-9 collapsible timer')
    ├── test('timer collapsed by default', ...)                 FR-P9-1
    ├── test('click reveal → m:ss text renders', ...)           FR-P9-2
    ├── test('the clock ticks forward', ...)                    FR-P9-3
    ├── test('reveal resets to collapsed on next item', ...)    FR-P9-4
    └── test('elapsed does not reset on next item', ...)        FR-P9-5
```

Total: 12 tests + shared harness.

### 1.1 Locked plan decisions (from spec §10)

1. **Tick-idle length** — `page.waitForTimeout(2100)`. Rationale: safely
   past the first `setInterval(1000)` boundary regardless of the reveal's
   phase offset; ≥1_000ms would race and ~5s would waste 3s per run.
2. **Route matchers.**
   - End (FR-P8-2): after click, `await expect(page).toHaveURL(/\/learn$/, { timeout: 10_000 })` **followed by** `expect(page.url()).not.toContain("/learn/summary")` and `expect(page.url()).not.toContain("/learn/quiz")`. The two negative-guards eliminate a false-pass on either wrong route.
   - Finish (FR-P8-4): `await page.waitForURL(/\/learn\/summary/, { timeout: 10_000 })`, mirroring [quiz-done-state.spec.ts:162](../../frontend/e2e/learn/quiz-done-state.spec.ts:162) verbatim.
3. **Red-first at L4.** Yes. Land this spec file **in its own commit** before
   any D1 code, run once against `main`, paste the RED output showing every
   new-selector assertion failing (skip-sentinel would fire only if the S4
   progress selector went missing — it hasn't; the D1 selectors are what
   fail). Commit + evidence go into the sprint board §Sprint D1 evidence
   block, above the code plan's block-level red/green outputs.

### 1.2 Why no CI-tier addition

`learn-e2e` is on-demand only (per
[`PLAYWRIGHT_TESTING_ARCHITECTURE.md`](../Architectures/PLAYWRIGHT_TESTING_ARCHITECTURE.md)
"L4 Behavioral Validation — on-demand only, never in per-commit CI").
D1 does not change this. The sprint's DoD gate is:
- L1 tests run in `make check` (per code plan §T4.1);
- L4 tests run manually via `npm run test:e2e:learn` before flipping the
  sprint board to Implemented.

### 1.3 Why no new fixtures

Every selector already exists in the code plan; no seed override, no
`addInitScript`, no auth setup, no mock middleware. The dev seed's
default 30-item bank is enough — every FR fires on item 1 or on the item-1
→ item-2 transition.

### 1.4 Why one file, not three

Three separate specs (`quiz-chip.spec.ts`, `quiz-end-session.spec.ts`,
`quiz-timer.spec.ts`) would triple the dev-server spin-up and video
overhead for the same coverage. The three `describe` blocks in one file
share the same page context per test and reuse the harness. The sibling
learn specs made the same call for cohesive sub-features (`quiz-done-state.spec.ts`
covers `banner + retake + summary route` in one file, not three).

## 2. Files touched

| File | Edit | Owning FR(s) |
|------|------|-----------|
| **NEW** `frontend/e2e/learn/quiz-frame.spec.ts` | Author the 12 tests + shared harness above | FR-L1 … FR-P9-5 |
| [`docs/plan/preact-parity-sprint-board-D.md`](preact-parity-sprint-board-D.md) | (after run) add L4 evidence section link + video/report path | FR-X3 + DoD §9 |

**Explicitly NOT touched:**

- `frontend/playwright.config.ts` (no config change; `learn-e2e` already
  picks up new files under `e2e/learn/`).
- `frontend/package.json` (no new script; the existing
  `test:e2e:learn` invocation runs the new file).
- Any sibling learn spec (`quiz-progress.spec.ts`, `quiz-done-state.spec.ts`,
  `quiz-rotation.spec.ts`, `bank-integration.spec.ts`, `a11y.spec.ts`, …) —
  their selectors are unchanged; regression guard is a full-suite run
  (T4.1 below), not an edit.
- Any production `.tsx` / `.ts` file (that is the D1 code plan's territory).
- Any ADR / `decisions.md` (routine sibling `.spec.ts` addition).

## 3. Task list

Task markers:
- `[red]` — the assertion that must FAIL against a pre-D1 tree.
- `[green]` — the D1 code change (owned by the code plan) that flips it.
- `[verify]` — check that runs after (arch tests, sibling suites, video artefact).
- `[P]` — parallel-safe with siblings inside the same block.

Every FR from [spec §3](preact-parity-D1-quiz-frame-playwright.spec.md#3-functional-requirements-ears)
maps to at least one `[red]` + `[green]` pair — see §4 crosswalk.

### Block 0 — Baseline

- **T0.1** From `frontend/`: `pnpm exec tsc --noEmit -p tsconfig.json` → 0
  errors on `main` (baseline; a compile error in an unrelated file must
  not be attributed to D1). Paste.
- **T0.2** From `frontend/`: `npm run test:e2e:learn` on `main` (pre-D1
  code, pre-D1 spec file) → all sibling specs green. Paste PASS summary.
- **T0.3** Root: `.venv/bin/python -m pytest tests/architecture/ -q` →
  all pass. Paste.

### Block 1 — Author the spec file (`e2e/learn/quiz-frame.spec.ts`)

Do this **before** any D1 production code lands. The file is written to
red at every new-selector assertion.

- **T1.1 [green]** Create `frontend/e2e/learn/quiz-frame.spec.ts`.
  Preamble mirroring [quiz-progress.spec.ts:1-27](../../frontend/e2e/learn/quiz-progress.spec.ts:1):
  file docstring naming L4 tier + `learn-e2e` project + run command +
  scope statement (chip / End / timer wired-through only; L1 covers
  edges).
- **T1.2 [green] [P]** Copy the harness verbatim from
  `quiz-progress.spec.ts`:
  - `counterText(page)` — the skip-sentinel reader.
  - `answerAndAdvance(page)` — A → Submit → feedback → Next.
  Add one D1-specific helper:
  - `answerToFeedback(page)` — A → Submit → feedback (stop before Next),
    same shape as [quiz-done-state.spec.ts:43-49](../../frontend/e2e/learn/quiz-done-state.spec.ts:43).
  - `revealTimer(page)` — one-liner: click
    `[data-testid="quiz-timer-reveal"]` and wait for
    `[data-testid="quiz-timer"]` to be visible (10s timeout).
- **T1.3 [green] [P]** Author `describe('Q-7 skill chip')`:
  - `test('first item shows a non-empty chip', ...)` → FR-P7-1.
    Assertions:
    ```ts
    await page.goto("/learn/quiz", { waitUntil: "networkidle" });
    test.skip((await counterText(page)) === "", "Skipped: quiz not rendered (auth/env).");
    const chip = page.locator("[data-testid='quiz-skill-chip']");
    await expect(chip).toHaveCount(1);
    await expect(chip).toBeVisible();
    const text = (await chip.textContent())?.trim() ?? "";
    expect(text.length).toBeGreaterThan(0);
    ```
  - `test('chip persists across answering→reviewing', ...)` → FR-P7-2.
    Read the chip text pre-submit, run `answerToFeedback(page)`, read the
    chip text again → `expect(after).toBe(before)`; `toHaveCount(1)`
    at both readings.
  - `test('dot glyph resolves an accent color', ...)` → FR-P7-3.
    Read the dot's computed color (locator = `quiz-skill-chip [data-testid='bucket-dot']`
    OR the chip's `::before` if the plan inlines the dot; the code plan
    should expose a `[data-testid='bucket-dot']` inside the chip for a
    stable read — flag if it doesn't). Assert the color is not `""`, not
    `"rgba(0, 0, 0, 0)"`, not `"transparent"`. (Reads via
    `getComputedStyle(el).backgroundColor` in `evaluate`.)
- **T1.4 [green] [P]** Author `describe('Q-8 End session')`:
  - `test('End control visible on first item', ...)` → FR-P8-1.
    `await expect(page.locator("[data-testid='quiz-end-session']")).toHaveCount(1);`
    plus `.toBeVisible()`.
  - `test('End routes to /learn, not /learn/summary', ...)` → FR-P8-2.
    Click End; `await expect(page).toHaveURL(/\/learn$/, { timeout: 10_000 });`
    then `expect(page.url()).not.toContain("/learn/summary");` then
    `expect(page.url()).not.toContain("/learn/quiz");`.
  - `test('End persists into reviewing', ...)` → FR-P8-3. After
    `answerToFeedback(page)`, assert End still visible + interactive.
  - `test('Finish still routes to /learn/summary', ...)` → FR-P8-4
    (regression). After `answerToFeedback(page)`, click `quiz-finish`;
    `await page.waitForURL(/\/learn\/summary/, { timeout: 10_000 });`
    (verbatim from quiz-done-state.spec.ts).
- **T1.5 [green] [P]** Author `describe('Q-9 collapsible timer')`:
  - `test('timer collapsed by default', ...)` → FR-P9-1.
    `await expect(page.locator("[data-testid='quiz-timer-reveal']")).toHaveCount(1);`
    plus `await expect(page.locator("[data-testid='quiz-timer']")).toHaveCount(0);`.
  - `test('click reveal → m:ss text renders', ...)` → FR-P9-2.
    `await revealTimer(page)`; then read the text and assert
    `/^\d+:\d{2}$/`.
  - `test('the clock ticks forward', ...)` → FR-P9-3. `revealTimer(page)`;
    parse the reading to total seconds; `await page.waitForTimeout(2100)`;
    parse the new reading; `expect(after).toBeGreaterThan(before)`. Helper
    `parseElapsed(text: string): number` folds `m:ss` to seconds.
  - `test('reveal resets to collapsed on next item', ...)` → FR-P9-4.
    `revealTimer(page)`; `answerAndAdvance(page)`; assert
    `quiz-timer-reveal` present, `quiz-timer` absent on item 2.
  - `test('elapsed does not reset on next item', ...)` → FR-P9-5.
    `revealTimer(page)`; read t0; `answerAndAdvance(page)`;
    `revealTimer(page)` again; read t1; `expect(t1).toBeGreaterThan(t0)`.
- **T1.6 [verify]** From `frontend/`: `pnpm exec tsc --noEmit -p tsconfig.json` → 0
  errors (spec file compiles). Paste.

### Block 2 — Red-first run (before any D1 code lands)

Prove the assertions are real by running against a pre-D1 tree.

- **T2.1 [red]** Commit the spec file in its own commit (message:
  `test(preact): D1 Playwright validation (red-first)`); run against the
  current `main`:
  ```
  cd frontend && npm run test:e2e:learn -- e2e/learn/quiz-frame.spec.ts
  ```
  Expected outcome: **every test in the file fails on a `toHaveCount(1)`
  or `toBeVisible()` against a missing D1 selector** (`quiz-skill-chip`,
  `quiz-end-session`, `quiz-timer-reveal`). FR-P8-4 (Finish → summary) may
  pass — it's the regression guard for the pre-existing path — that is
  expected and correct. Paste the PASS/FAIL summary; snapshot the video
  path for the first failing test (evidence "the L4 layer really watched
  it red").
- **T2.2 [verify]** Confirm the sibling learn specs are STILL green on
  the same run (i.e. the new file did not introduce a global-scope import
  or timeout that broke a sibling). Paste sibling pass list.

### Block 3 — Green run (after D1 code lands)

After the D1 code plan's Blocks 1–3 complete (code changes for chip / End /
timer are on the branch):

- **T3.1 [verify]** From `frontend/`:
  ```
  npm run test:e2e:learn -- e2e/learn/quiz-frame.spec.ts
  ```
  Expected: all 12 tests green. Paste output.
- **T3.2 [verify]** Full learn-e2e suite:
  ```
  npm run test:e2e:learn
  ```
  Expected: all learn specs green (FR-X2). Paste PASS summary.
- **T3.3 [verify]** Playwright HTML report generated; open the report
  and confirm one `.webm` video per test in the D1 file (FR-X3). Record
  the report path (`playwright-report/index.html` by default).
- **T3.4 [verify]** `pnpm exec tsc --noEmit` → 0 errors. Paste.
- **T3.5 [verify]** Root `.venv/bin/python -m pytest tests/architecture/ -q`
  → all pass. Paste.
- **T3.6 [verify]** `make check` → green. Paste.

### Block 4 — Evidence + sprint board

- **T4.1 [green]** In [`docs/plan/preact-parity-sprint-board-D.md`](preact-parity-sprint-board-D.md)
  §Sprint D1 evidence section (added by the code plan's T5.3), add a
  **§Playwright evidence** sub-section with:
  - The T2.1 red-first summary (proves the L4 layer saw D1 failing before
    any code landed).
  - The T3.1 green summary (12 passing).
  - The T3.2 full-suite green summary.
  - The path to the Playwright HTML report and the videos.
- **T4.2 [green]** PR-body log: "**D1 L4 evidence pasted.** Playwright
  spec `e2e/learn/quiz-frame.spec.ts` red-firsted against pre-D1 main
  (T2.1), green after D1 code (T3.1), sibling learn specs unchanged and
  green (T3.2). No config change; no new dep; no ADR."

---

## 4. FR → task crosswalk

Every FR from [`spec §3`](preact-parity-D1-quiz-frame-playwright.spec.md#3-functional-requirements-ears)
maps to at least one task; every non-structural FR maps to a red + green pair.

| FR | Red (in T2.1) | Green (in T1.x / T3.1) | Verify |
|----|---------------|-----------------------|--------|
| FR-L1 (skip discipline) | — (structural — pattern copy in T1.2) | T1.2 | T3.1 (test.skip fires cleanly when applicable) |
| FR-L2 (file placement) | — | T1.1 (creates file at `e2e/learn/quiz-frame.spec.ts`) | T3.1 (learn-e2e project picks it up) |
| FR-L3 (no setTimeout bump) | — | T1.1..T1.5 (no `test.setTimeout(...)` in any test) | T3.1 (whole file under 90s per §7) |
| FR-P7-1 | T2.1 (chip absent → toHaveCount(1) fails) | T1.3 + code plan T1.2/T1.4 | T3.1 |
| FR-P7-2 | T2.1 | T1.3 + code plan T1.9 | T3.1 |
| FR-P7-3 | T2.1 (accent color absent) | T1.3 + code plan T1.4 | T3.1 |
| FR-P7-4 | (L1-only — no L4 test) | (code plan T1.1b covers) | — |
| FR-P8-1 | T2.1 (End control absent) | T1.4 + code plan T2.4 | T3.1 |
| FR-P8-2 | T2.1 (click fails; URL stays on quiz) | T1.4 + code plan T2.6 | T3.1 |
| FR-P8-3 | T2.1 | T1.4 + code plan T2.4 | T3.1 |
| FR-P8-4 | (regression — this test should PASS at T2.1) | (already green pre-D1; guard against D1 breaking it) | T3.1 |
| FR-P8-5 | (L1-only) | (code plan T2.1d) | — |
| FR-P9-1 | T2.1 (reveal control absent) | T1.5 + code plan T3.4 | T3.1 |
| FR-P9-2 | T2.1 | T1.5 + code plan T3.4 | T3.1 |
| FR-P9-3 | T2.1 | T1.5 + code plan T3.4 (setInterval real tick) | T3.1 |
| FR-P9-4 | T2.1 | T1.5 + code plan T3.6 (key-by-question-id) | T3.1 |
| FR-P9-5 | T2.1 | T1.5 + code plan T3.7 (startedAt passed once) | T3.1 |
| FR-P9-6 | (L1-only) | (code plan T3.3d + T3.1) | — |
| FR-X1 | — (structural — no `import "@/lib/*"` in the spec) | T1.1 (imports only `@playwright/test`) | T3.1 (grep) |
| FR-X2 | T2.2 baseline green | (no edit to siblings) | T3.2 |
| FR-X3 | — | T1.1 (no `video: "off"` override) | T3.3 (report contains .webm per test) |

**Coverage claim:** every FR-L / FR-P / FR-X row above resolves to a task
that produces either the red-first evidence (T2.1) or the green-after
evidence (T3.1 / T3.2 / T3.3), except the four "L1-covered, not L4" rows
which the code plan proves. Zero-coverage requirements: none.

---

## 5. Parallelization envelope

- **Block 0:** T0.1..T0.3 independent — parallel-safe.
- **Block 1:** T1.1 must land first (creates the file). T1.2..T1.5 are all
  edits to that same file — sequentially inside one authoring pass
  (marked `[P]` in the crosswalk because the *test descriptions* are
  logically independent, but the file edit is one authoring pass).
- **Block 2:** T2.1 → T2.2 sequential (both read the same test-run).
- **Block 3:** all `[verify]` — run in order, each depends on the prior's
  code being on the branch. T3.4/T3.5/T3.6 can run in parallel with each
  other after T3.1 completes.
- **Block 4:** sequential (evidence writes depend on Block 3 outputs).

Cross-block dependency: **Block 2 must complete before ANY D1 production
code lands.** This is what makes the L4 layer honest as "red-first" at the
L4 layer, not just at the L1 layer. If Block 2 slips past D1 code
landing, the red-first evidence is lost and the reviewer sees only green —
they cannot distinguish "L4 evidence was authored red-first and now
passes" from "L4 evidence was authored after the code and never failed".
Not fatal, but the SDD discipline is worth the small ordering cost.

---

## 6. Definition of Done (D1-Playwright)

Mirrors [spec §9](preact-parity-D1-quiz-frame-playwright.spec.md#9-definition-of-done).
All paste-into-PR items are in the block-level tasks above.

- [ ] T0.1–T0.3 baseline outputs pasted.
- [ ] T1.6 `tsc --noEmit` pasted (spec file compiles).
- [ ] T2.1 red-first summary pasted (evidence of new-selector assertions
      failing on pre-D1 `main`; FR-P8-4 regression guard passing is
      expected and OK).
- [ ] T2.2 sibling-suite green on the same red-first run pasted.
- [ ] T3.1 green summary pasted (12 tests passing after D1 code lands).
- [ ] T3.2 full-suite green pasted (FR-X2 held).
- [ ] T3.3 Playwright report path recorded; one video per test confirmed
      (FR-X3).
- [ ] T3.4 `tsc --noEmit` green pasted.
- [ ] T3.5 `pytest tests/architecture/ -q` green pasted.
- [ ] T3.6 `make check` green pasted.
- [ ] T4.1 sprint board §Playwright evidence sub-section added.
- [ ] T4.2 PR-body log line present.
- [ ] **No ADR.** No config change. No new fixture. No `test.setTimeout`
      bump. If any of those became necessary, the plan is wrong —
      escalate to `sdd-replan`.
