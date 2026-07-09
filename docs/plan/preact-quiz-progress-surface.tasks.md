# Tasks — S4 · Visible session-progress surface (`/learn` quiz)

**Spec:** [`preact-quiz-progress-surface.spec.md`](preact-quiz-progress-surface.spec.md) · **Plan:** [`preact-quiz-progress-surface.plan.md`](preact-quiz-progress-surface.plan.md)
**Status:** Ready for implementation (Stage 3 done; Stage 4 analyze below).

Atomic, file-level, red-first. Each task names its EARS criteria and its exact
pass/fail check. `[dep: …]` = must land after; `‖` = parallelizable with siblings.
All frontend commands run from `frontend/` with the local binary
(`./node_modules/.bin/…`) — never repo-root/`npx` (worktree-pollution + missing-jsdom).

---

## Checklist — every FR is measurable (Stage 3 gate)

| FR | Measurable as | Verdict |
|----|---------------|---------|
| FR-1 endless (null) | translator output `{total:null, bounded:false, fraction:0}` | ✅ L1 assert |
| FR-2 over-run | translator `{fraction:1, total:null}` when `position>target` | ✅ L1 assert |
| FR-3 first item | translator `position===1` at `gradedTotal=0, phase=answering` | ✅ L1 assert |
| FR-4 advance-on-grade | `position===gradedTotal+1` (answering) / `===gradedTotal` (reviewing) | ✅ L1 assert |
| FR-5 bar fill | component bar width == `fraction` | ✅ SSR DOM assert |
| FR-6 loading-carry | translator `position` stable under `phase="loading"` | ✅ L1 assert |
| FR-7 a11y | component has `role="progressbar"` + `aria-valuenow/min/max` | ✅ SSR DOM assert |
| FR-8 pure translator | translator imports `wire/` only (no React/adapter) | ✅ structural / layering test |
| FR-9 read-only | component+translator import graph: no engine/repo/scheduler | ✅ structural / layering test |
| FR-10 no regression | S3/S3.1 + reducer suites stay green (unchanged) | ✅ L1 green |

No unmeasurable criterion → nothing flagged back to the spec.

---

## T-s0 — Export the phase tag from the reducer (or decide the param type)  ‖-none (first)

- **File:** `frontend/components/quiz/quiz_screen_reducer.ts` (add one exported type) —
  OR skip and have the translator take a plain string-union param (plan §2 note).
- **Do:** export `export type QuizScreenPhase = QuizScreenState["phase"];` so T-s1 can
  type its `phase` param without importing React-adjacent types. (If we instead inline
  the union in the translator, this task is a no-op — pick the inline union to keep the
  translator import-free of the reducer; that is the plan's preferred path.)
- **Decision (locked):** translator takes `phase: "loading" | "answering" | "reviewing"
  | "done"` inline → **T-s0 becomes a no-op** and T-s1 imports nothing from the reducer.
  Kept as a task only to record the decision; no code change.
- **Pass/fail:** N/A (decision record). Proceed to T-s1.

## T-s1 — Pure translator `quiz_progress_vm.ts` (RED then GREEN)  [dep: T-s0 decision]

- **Files (new):** `frontend/lib/translators/quiz_progress_vm.ts` (+ its test in T-s2).
- **RED first (T-s2 authored before this body exists):** run T-s2 → must fail (module
  missing / values wrong). Paste the failing output.
- **Implement:** `toQuizProgressVM(gradedTotal: number, phase: "loading"|"answering"|
  "reviewing"|"done", targetCount: number | null): QuizProgressVM`, exporting the
  `QuizProgressVM` interface. Math **exactly** per plan §3:
  - `position`: answering→`gradedTotal+1`; reviewing→`gradedTotal`; loading/done→carry
    (`gradedTotal`); floored at `Math.max(1, …)`.
  - `bounded = targetCount != null`.
  - `fraction = bounded ? clamp(position/targetCount, 0, 1) : 0`.
  - `total = (bounded && position <= targetCount) ? targetCount : null`.
  - House-style header ("Imports `wire/` only. No I/O, no React, no SDK."). Imports
    `wire/engine_entities` types only (or nothing — `targetCount` is a plain `number|null`).
- **EARS:** FR-1, FR-2, FR-3, FR-4, FR-6, FR-8.
- **Pass/fail:** T-s2 green; `./node_modules/.bin/tsc --noEmit -p tsconfig.json` = 0.

## T-s2 — Translator tests `quiz_progress_vm.test.ts` (failure-paths FIRST)  [authored before T-s1 body]

- **File (new):** `frontend/lib/translators/quiz_progress_vm.test.ts`.
- **Do:** table-driven vitest, **failure/edge rows first**, no mocks:
  1. **FR-1** `targetCount=null, gradedTotal=6, phase=answering` → `{position:7, total:null,
     bounded:false, fraction:0}`.
  2. **FR-2** `targetCount=30, gradedTotal=31, phase=answering` → `position:32,
     fraction:1, total:null` (denominator dropped).
  3. **FR-2 (boundary)** `targetCount=30, gradedTotal=29, phase=answering` → `position:30,
     total:30, fraction:1` (exactly at target still shows "of 30").
  4. **FR-3** `targetCount=30, gradedTotal=0, phase=answering` → `position:1, total:30,
     fraction:1/30`.
  5. **FR-4** `targetCount=30, gradedTotal=5, phase=reviewing` → `position:5` (the item
     just graded), and same inputs `phase=answering` → `position:6`.
  6. **FR-6** `targetCount=30, gradedTotal=5, phase=loading` → `position:5` (carry, not 0/1).
  7. **happy** `targetCount=30, gradedTotal=14, phase=answering` → `position:15, total:30,
     fraction:0.5`.
- **EARS:** FR-1, FR-2, FR-3, FR-4, FR-6.
- **Pass/fail:** all rows green after T-s1; each row seen RED before T-s1 body.

## T-s3 — Presentational `QuizProgress.tsx` (RED then GREEN)  [dep: T-s1] ‖ T-s2

- **Files (new):** `frontend/components/quiz/QuizProgress.tsx` (+ test in T-s4).
- **RED first (T-s4 first):** run T-s4 → fail (component missing).
- **Implement:** `export function QuizProgress({ vm }: { vm: QuizProgressVM })`. Renders:
  - counter text as an **inline string literal** (this codebase has **no `t()`/i18n
    helper** — `QuizView`/`FeedbackView` use inline literals; the style guide prescribes
    `t()` but it is unimplemented, so matching the surrounding code is correct here):
    `total != null ? \`Question ${position} of ${total}\` : \`Question ${position}\``.
  - a progressbar: `role="progressbar"`, `aria-valuemin={0}`, `aria-valuemax={vm.total ??
    100}` (or `aria-valuemax={100}` with `aria-valuenow={Math.round(fraction*100)}` for
    the endless case), `aria-valuenow`, `aria-valuetext` = the counter text (FR-7).
  - fill element width from `vm.fraction` via inline `style={{ width:
    \`${Math.round(fraction*100)}%\` }}` — app-origin reviewed markup styling its OWN
    width from a numeric VM field is **not** FE-AP-12 (that bans agent-emitted HTML), and
    is the pragmatic way to bind a dynamic width under strict CSP (no arbitrary Tailwind
    width class exists for a runtime %). Bar hidden or indeterminate when `!vm.bounded`
    (FR-1).
  - `data-testid="quiz-progress"`; `cn()` (from `@/lib/utils`) for static classes (U6);
    no logic (F-R1).
- **EARS:** FR-5, FR-7 (+ FR-1/FR-2 rendering).
- **Pass/fail:** T-s4 green; `tsc --noEmit` = 0.

## T-s4 — Component SSR tests `QuizProgress.test.tsx` (failure-first)  [authored before T-s3 body]

- **File (new):** `frontend/components/quiz/QuizProgress.test.tsx`.
- **Do:** repo SSR convention (`renderToStaticMarkup` + JSDOM, twin of
  `QuizView.test.tsx`), failure/edge first:
  1. **FR-1** `vm={position:7,total:null,bounded:false,fraction:0}` → text contains
     "Question 7", does **not** contain " of "; no full/bounded bar.
  2. **FR-2** `vm={position:32,total:null,bounded:true,fraction:1}` → text "Question 32",
     no "of"; bar fill width == 100%.
  3. **FR-7** any bounded vm → `[role="progressbar"]` present with `aria-valuenow`,
     `aria-valuemin`, `aria-valuemax`.
  4. **FR-5** `vm={…,fraction:0.5}` → fill element width == "50%".
- **EARS:** FR-1, FR-2, FR-5, FR-7.
- **Pass/fail:** all green after T-s3; each seen RED first.

## T-s5 — Wire the bar into the quiz page  [dep: T-s1, T-s3]

- **File:** `frontend/app/(coach)/learn/quiz/page.tsx`.
- **Do:** in the `answering`/`reviewing` block, compute
  `const progressVm = toQuizProgressVM(state.score.total, state.phase,
  session?.target_count ?? null);` then render `<QuizProgress vm={progressVm} />`
  **above** `content` in a small frame that feeds **both** return paths (plain `return
  content` at ~:263 and the iPad-split at ~:251). Keep it thin glue — no math in the page
  (F-R1). Do not touch the `loading`/`done` early return (FR-6: placeholder stays).
- **EARS:** FR-5 (visible), FR-9 (page passes existing state, no new engine call),
  FR-10 (no serving/reducer edit).
- **Pass/fail:** `tsc --noEmit` = 0; page still renders (manual/preview); no new import of
  an engine/repo/scheduler in the page beyond what already exists.

## T-s6 — Live E2E `quiz-progress.spec.ts` (on-demand)  [dep: T-s5] ‖-none

- **File (new):** `frontend/e2e/learn/quiz-progress.spec.ts` (`learn-e2e` project).
- **Do:** open `/learn/quiz`; assert `[data-testid="quiz-progress"]` text == "Question 1
  of 30"; answer A + Submit + Next; assert it reads "Question 2 of 30". `test.skip` if the
  item doesn't render (auth/env), same guard as `quiz-rotation.spec.ts`.
- **EARS:** FR-1, FR-3, FR-5 (live).
- **Pass/fail:** `npx playwright test --project=learn-e2e e2e/learn/quiz-progress.spec.ts`
  → 1 passed (on-demand; not in `make check`).

## T-sg — Full gate + DoD evidence  [dep: T-s1..T-s5]

- **Do & paste output (not summaries):**
  - `cd frontend && ./node_modules/.bin/vitest run lib/translators/quiz_progress_vm.test.ts
    components/quiz/QuizProgress.test.tsx` → green.
  - `./node_modules/.bin/tsc --noEmit -p tsconfig.json` → 0 errors.
  - `./node_modules/.bin/vitest run tests/architecture/test_frontend_layering.test.ts` (F-R1/2
    hold: translator pure, component imports no adapter) → green.
  - Regression: `./node_modules/.bin/vitest run components/quiz/quiz_screen_reducer.test.ts`
    + the S3/S3.1 touched suites → unchanged green (FR-10).
  - `cd .. && .venv/bin/python -m pytest tests/architecture/ -q` → green (constitution).
  - Live: preview `/learn/quiz` shows "Question 1 of 30" → "2 of 30" on Next (screenshot).
- **EARS:** all (integration gate).
- **Pass/fail:** every command green; DoD boxes in spec §9 + plan §7 ticked with pasted
  evidence. **No ADR** (plan §6 is the record).

---

## Dependency graph

```
T-s0 (decision, no-op)
   └─► T-s2 (translator tests, RED) ─┐
                                     ├─► T-s1 (translator, GREEN) ─┐
   T-s4 (component tests, RED) ──────┼─► T-s3 (component, GREEN) ──┤
                                     │                             ├─► T-s5 (page wire)
                                     │                             │      └─► T-s6 (E2E, on-demand)
                                     └─────────────────────────────┴─► T-sg (gate)
```

T-s2‖T-s4 (both RED first, independent). T-s1‖T-s3 order: T-s1 before T-s3 (component
needs the VM type). T-s6 is optional/on-demand.

---

## Stage 4 — Analyze (cross-artifact + grounding + baseline)

Read-only consistency check: spec ↔ plan ↔ tasks ↔ constitution.

**Grounding — every path/API the plan+tasks reference exists (probed 2026-07-08):**

| Reference | Exists? | Evidence |
|---|---|---|
| `QuizSession.target_count` (nullable) | ✅ | `lib/wire/engine_entities.ts:213` |
| `SessionTally.total` increments per submit | ✅ | `components/quiz/quiz_screen_reducer.ts:172-173` |
| `session` in page state (holds target_count) | ✅ | `app/(coach)/learn/quiz/page.tsx:74` |
| page `content` var + two return paths (:251 split, :263 plain) | ✅ | page.tsx:194/251/263 |
| translator siblings to mirror (`quiz_item_vm`, `session_summary_vm`) | ✅ | `lib/translators/` (33 files) |
| component SSR test convention (`QuizView.test.tsx`) | ✅ | `components/quiz/QuizView.test.tsx` |
| `learn-e2e` Playwright project + `quiz-rotation.spec.ts` conventions | ✅ | `e2e/learn/quiz-rotation.spec.ts` |
| `t()` i18n helper | ❌ **REFUTED** | `lib/i18n*` does not exist; no component imports `@/lib/i18n`; `QuizView` uses inline literals ("Get a hint", "Submit answer"). Plan/tasks **corrected** to inline literals. |
| `cn()` | ✅ | `lib/utils.ts:4` |

**No new dependency** (nothing added to `package.json`/`pyproject.toml`) → no ADR dep
trigger. **No invariant violation** (F-R1 split is the design; F-R2/W2 N/A). **No
zero-coverage FR** (checklist above maps all 10).

**CRITICAL findings (found + resolved at analyze, the cheap correction point):**
1. **`t()`/`@/lib/i18n` referenced but does not exist.** The style guide §13 prescribes a
   `t()` i18n helper, but it is unimplemented in this repo — sibling components
   (`QuizView`, `FeedbackView`) render **inline string literals**. Plan T3 + task T-s3
   **corrected** to inline literals (matching surrounding code is the right call; do not
   introduce an i18n layer as a side effect of a progress bar). No other non-existent
   file/API referenced.

**Baseline (must be green before implementation — run at Stage-6 start):**
`make check` (or the frontend equivalent) + `pytest tests/architecture/ -q`. Recorded as
the T-sg precondition; not run here (analyze is read-only).

**Verdict:** artifacts are consistent and grounded. Ready for **sdd-implement**.
