# S4 manual validation — the "Question N of M" progress bar (`/learn` quiz)

**What S4 ships:** a session-progress surface at the top of the quiz — a
`Question N of M` counter above a thin bar that fills as you answer. It closes the
*progress* half of the reported "`/learn` is an infinite loop with no sense of how
far you are" gap. (The *done-state + retake* half is S5, not built yet.)

**Where the numbers come from:** `M` is `QuizSession.target_count`, seeded by S3.
With no `session.target_count.<mode>` content-plane row, the session opens at the
floor `DEFAULT_TARGET_COUNT = 30` (`lib/adapters/engine/repos/drizzle_session_repo.ts:26`)
— so the dev-seed quiz reads **"of 30"**. `N` is 1-based: while *answering* it's the
question you're **on** (graded-so-far + 1); while *reviewing* feedback it's the one
you **just** graded. All the counting/clamp math is the pure translator
`lib/translators/quiz_progress_vm.ts`; the component `components/quiz/QuizProgress.tsx`
only renders the VM (F-R1).

Files under test:
`lib/translators/quiz_progress_vm.ts` · `components/quiz/QuizProgress.tsx` ·
`app/(coach)/learn/quiz/page.tsx` (the wire). Committed on
`feat/preact-s3-bounded-session` (`2e1cd1b`), PR
[#137](https://github.com/rajnishkhatri/AgentsFramework/pull/137).

---

## A. Automated proof (run this first)

The Playwright spec `e2e/learn/quiz-progress.spec.ts` drives the four determinate-path
behaviours in a real browser (video on, no auth). It is the fastest way to confirm
S4 works before eyeballing anything.

**One-time:** start the dev server with auth bypass (the root `frontend-preview`
launch config sets `E2E_BYPASS_AUTH=1`), then point Playwright at it:

```bash
# From repo root — start the bypass-auth dev server (background):
#   (Claude Code: preview_start "frontend-preview"; or manually:)
E2E_BYPASS_AUTH=1 pnpm --dir frontend dev    # serves http://localhost:3000

# From frontend/ — run the S4 spec against the running server.
# CI=1 skips the config's own webServer block so it reuses the one above:
cd frontend
CI=1 BASE_URL=http://localhost:3000 \
  ./node_modules/.bin/playwright test --project=learn-e2e \
  e2e/learn/quiz-progress.spec.ts --reporter=list
```

Expected (verified 2026-07-09):

```
Running 4 tests using 1 worker
  ✓ 1 … first item reads 'Question 1 of 30' with a progressbar (FR-3 / FR-7)
  ✓ 2 … the counter advances 1 → 2 → 3 as items are graded (FR-4)
  ✓ 3 … the bar fill grows monotonically as the walk progresses (FR-5)
  ✓ 4 … the counter persists across the answer → feedback sub-state (FR-6)
  4 passed
```

> **Note (by design):** the spec covers the DETERMINATE path (bounded, position ≤ 30).
> The two INDETERMINATE edges — **endless** (target `null`, FR-1) and **over-run**
> (position > 30, FR-2) — are byte-covered by the unit tests
> (`lib/translators/quiz_progress_vm.test.ts`, `components/quiz/QuizProgress.test.tsx`);
> reaching item 31 live to force over-run is left to those cheaper layers. To run
> them: `cd frontend && ./node_modules/.bin/vitest run lib/translators/quiz_progress_vm.test.ts components/quiz/QuizProgress.test.tsx`.

---

## B. Manual walkthrough (localhost UI)

**Start:** `E2E_BYPASS_AUTH=1 pnpm --dir frontend dev`, then open
<http://localhost:3000/learn/quiz>. Dev-seed learner is **Maya**; the quiz serves the
171-item ACT-English bank.

### Step 1 — First item shows "Question 1 of 30" (FR-3, FR-1 bounded)

Land on `/learn/quiz`. **Above the question stem**, before you touch anything, you
should see:

- the text **`Question 1 of 30`** (1-based — it's **1**, never **0**);
- a thin full-width track with a tiny filled sliver on the left (~3% = 1/30).

✅ Pass: counter reads `Question 1 of 30` on a fresh session.
❌ Fail: reads `Question 0 …`, or the denominator is missing on a bounded session,
or no bar renders.

### Step 2 — The counter advances as you answer (FR-4)

Pick any choice (A–D) → **Submit answer**. Feedback appears. Click **Next question →**.

- On the next item, the counter reads **`Question 2 of 30`** and the bar is wider.
- Answer + Next again → **`Question 3 of 30`**, wider still.

✅ Pass: each graded item moves the counter forward by exactly one (1 → 2 → 3) and the
bar fill grows monotonically.
❌ Fail: counter sticks on 1, jumps by more than one, or the bar doesn't move.

### Step 3 — The counter holds on the feedback sub-state (FR-6)

On any item, **Submit** but **do not** click Next — stay on the feedback banner.

- The counter still reads a real position (the item you **just** graded, e.g.
  `Question 1 of 30`) — it does **not** flicker to `Question 0` or blank.

✅ Pass: the bar persists across answering → reviewing with a stable position.
❌ Fail: the bar disappears or shows `Question 0` on the feedback view.

### Step 4 — Accessibility: it's a real progressbar, not a colour-only cue (FR-7)

The bar isn't decoration — a screen reader must announce it. Verify the DOM
semantics (DevTools → Elements, or the console snippet below):

```js
// Paste in the browser console on /learn/quiz:
(() => {
  const region = document.querySelector("[data-testid='quiz-progress']");
  const bar = document.querySelector("[data-testid='quiz-progress'] [role='progressbar']");
  return {
    counter: region?.textContent.trim(),
    role: bar?.getAttribute("role"),
    valuemin: bar?.getAttribute("aria-valuemin"),
    valuemax: bar?.getAttribute("aria-valuemax"),
    valuenow: bar?.getAttribute("aria-valuenow"),
    valuetext: bar?.getAttribute("aria-valuetext"),
    dataBounded: bar?.getAttribute("data-bounded"),
  };
})();
```

Expected on the first item (verified live 2026-07-09):

```js
{ counter: "Question 1 of 30", role: "progressbar",
  valuemin: "0", valuemax: "30", valuenow: "1",
  valuetext: "Question 1 of 30", dataBounded: "true" }
```

The counter is real **text** (not conveyed by colour alone → WCAG 2.2 AA), and the
`role="progressbar"` carries `aria-valuenow/valuemax` + a text alternative, so AT
announces the position.

> **Why this matters (the a11y fix S4 caught):** the *indeterminate* cases — endless
> and over-run — deliberately **OMIT** `aria-valuenow`/`aria-valuemax` (WAI-ARIA), so
> AT announces "indeterminate" rather than a misleading "0%"/"100%". You won't hit
> those on the bounded dev-seed walk; they're pinned in the unit tests. (The original
> S4 draft announced `aria-valuenow=0` for endless sessions — the design pass fixed it.)

---

## C. Selector reference (for DevTools / debugging)

| What | Selector |
|---|---|
| Progress region (counter + bar) | `[data-testid='quiz-progress']` |
| The ARIA progressbar | `[data-testid='quiz-progress'] [role='progressbar']` |
| The filling element (its `style.width` = fraction) | `[data-testid='quiz-progress-fill']` |
| Item root (also carries `data-skill`) | `[data-skill]` |
| A choice button | `[data-testid='choice-A']` … `choice-D` |
| Submit | `[data-testid='quiz-submit']` |
| Feedback banner | `[data-testid='feedback-banner']` |
| Next / Finish | `[data-testid='quiz-next']` · `[data-testid='quiz-finish']` |

---

## D. Known scope / not-in-S4

- **Done-state + retake (S5)** is NOT built — after the target is reached the loop
  still continues (over-run: the counter shows the true position and **drops** the
  `of M` denominator, bar clamped full). There's no "you're done, retake?" prompt yet.
- **`?focus=<skill>` drill does NOT pin the quiz to one skill** — pre-existing gap
  (the scheduler has no focus filter); the bar still counts correctly, but the items
  rotate across skills. Separate work; see the S3.1 runbook.
- The dev-seed target is the **30** floor because there's no content-plane
  `session.target_count.*` row. A future bank-growth / policy change could seed a
  different `M`; the bar renders whatever `target_count` the session opened with.
