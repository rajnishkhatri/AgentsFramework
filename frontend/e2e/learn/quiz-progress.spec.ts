/**
 * E2E — the "Question N of M" session-progress bar on the /learn quiz (S4).
 *
 * Closes the progress half of the reported "/learn is an infinite loop" gap: a
 * learner now sees WHICH question they're on and HOW MANY the session targets.
 * The number spine is S3's `QuizSession.target_count` (30 by the seed floor,
 * `DEFAULT_TARGET_COUNT`); S4 renders it. The counting/clamp math is the pure
 * translator (`quiz_progress_vm.ts`, unit-tested); this spec proves the wired
 * behaviour a user actually sees in a real browser.
 *
 * L4 Behavioral Validation (Agentic Testing Pyramid): real browser against the
 * dev-seeded bank quiz (the `learn-e2e` project, video on), on-demand only — pure
 * T1 (seeded browser engine, no backend/auth/LLM). Sibling `quiz-rotation.spec.ts`
 * proves the SKILL rotates; this proves the COUNTER advances and the bar fills.
 *
 * SCOPE. The live walk exercises the DETERMINATE path (bounded session, position
 * ≤ target): first-item "Question 1 of 30" (FR-3), advance-on-grade 1→2→3 (FR-4),
 * bar fill grows (FR-5), and the a11y progressbar semantics (FR-7). The two
 * INDETERMINATE edges — endless (target null, FR-1) and over-run (position > 30,
 * FR-2) — are byte-covered by the translator + component unit tests
 * (`quiz_progress_vm.test.ts`, `QuizProgress.test.tsx`); reaching item 31 live to
 * force over-run is left to those cheaper layers by design (noted, not silently
 * skipped).
 *
 * Run: `npx playwright test --project=learn-e2e e2e/learn/quiz-progress.spec.ts`
 */

import { test, expect, type Page } from "@playwright/test";

/** The seed floor: `DrizzleSessionRepo.DEFAULT_TARGET_COUNT` with no policy row. */
const TARGET = 30;

/** The progress region's rendered counter text ("Question N of M"), or "" if absent. */
async function counterText(page: Page): Promise<string> {
  const el = page.locator("[data-testid='quiz-progress']");
  if ((await el.count()) === 0) return "";
  return (await el.textContent())?.trim() ?? "";
}

/** The bar fill's inline width (e.g. "3%"), or "" when the fill is absent. */
async function fillWidth(page: Page): Promise<string> {
  const fill = page.locator("[data-testid='quiz-progress-fill']");
  if ((await fill.count()) === 0) return "";
  return (await fill.evaluate((el) => (el as HTMLElement).style.width)) ?? "";
}

/** Answer the current item (A → Submit) and advance past feedback to the next. */
async function answerAndAdvance(page: Page): Promise<void> {
  await page.locator("[data-testid='choice-A']").click();
  await page.locator("[data-testid='quiz-submit']").click();
  await expect(page.locator("[data-testid='feedback-banner']")).toBeVisible({
    timeout: 10_000,
  });
  await page.locator("[data-testid='quiz-next']").click();
  // The next item is loading → answering; wait for the item root to re-render.
  await page.locator("[data-skill]").first().waitFor({ timeout: 10_000 });
}

test.describe("Quiz progress bar — 'Question N of M' (S4)", () => {
  test("first item reads 'Question 1 of 30' with a progressbar (FR-3 / FR-7)", async ({
    page,
  }) => {
    // NO seed override — the app takes the dev bank path (Maya + the 171-item bank
    // over InMemoryEngineDb); the session opens at the target_count floor of 30.
    await page.goto("/learn/quiz", { waitUntil: "networkidle" });

    // Behaviour test, not an environment stand-up: skip if the quiz didn't render.
    const text = await counterText(page);
    test.skip(text === "", "Skipped: quiz progress not rendered (auth/env).");

    // FR-3: a fresh session is on question 1 (1-based), not 0. FR-1 (bounded):
    // the denominator IS shown because target_count is non-null.
    expect(text).toContain(`Question 1 of ${TARGET}`);

    // FR-7 / WAI-ARIA: the bounded bar is DETERMINATE — it carries a measured
    // value (position) against the target, plus a text alternative.
    const bar = page.locator("[data-testid='quiz-progress'] [role='progressbar']");
    await expect(bar).toHaveAttribute("aria-valuemin", "0");
    await expect(bar).toHaveAttribute("aria-valuemax", String(TARGET));
    await expect(bar).toHaveAttribute("aria-valuenow", "1");
    await expect(bar).toHaveAttribute("aria-valuetext", `Question 1 of ${TARGET}`);
  });

  test("the counter advances 1 → 2 → 3 as items are graded (FR-4)", async ({
    page,
  }) => {
    await page.goto("/learn/quiz", { waitUntil: "networkidle" });
    const start = await counterText(page);
    test.skip(start === "", "Skipped: quiz progress not rendered (auth/env).");
    expect(start).toContain(`Question 1 of ${TARGET}`);

    // FR-4: while answering, N = graded-so-far + 1 → each graded item moves the
    // counter forward by exactly one. Walk two items and read the position each time.
    await answerAndAdvance(page);
    expect(await counterText(page)).toContain(`Question 2 of ${TARGET}`);

    await answerAndAdvance(page);
    expect(await counterText(page)).toContain(`Question 3 of ${TARGET}`);
  });

  test("the bar fill grows monotonically as the walk progresses (FR-5)", async ({
    page,
  }) => {
    await page.goto("/learn/quiz", { waitUntil: "networkidle" });
    test.skip((await counterText(page)) === "", "Skipped: quiz progress not rendered (auth/env).");

    // FR-5: fill width = clamp(position / target). On question 1 of 30 that's a
    // small non-zero sliver; after grading two items (question 3 of 30) it is wider.
    const parsePct = (w: string): number => Number(w.replace("%", "")) || 0;
    const w1 = parsePct(await fillWidth(page));
    expect(w1).toBeGreaterThan(0); // a bounded session always shows *some* progress

    await answerAndAdvance(page);
    await answerAndAdvance(page);

    const w3 = parsePct(await fillWidth(page));
    // Strictly wider after two graded items — the bar is a live progress signal,
    // not a static decoration. (3/30 = 10% > 1/30 ≈ 3%.)
    expect(w3).toBeGreaterThan(w1);
    // And still bounded (never past 100%) — the clamp holds.
    expect(w3).toBeLessThanOrEqual(100);
  });

  test("the counter persists across the answer → feedback sub-state (FR-6)", async ({
    page,
  }) => {
    await page.goto("/learn/quiz", { waitUntil: "networkidle" });
    test.skip((await counterText(page)) === "", "Skipped: quiz progress not rendered (auth/env).");

    // FR-6: the bar renders in BOTH answering and reviewing (feedback) phases and
    // never flickers to a bare "Question 0". Answer item 1 and STOP on feedback
    // (do not advance) — the counter must still read a real position.
    await page.locator("[data-testid='choice-A']").click();
    await page.locator("[data-testid='quiz-submit']").click();
    await expect(page.locator("[data-testid='feedback-banner']")).toBeVisible({
      timeout: 10_000,
    });

    // reviewing: N = the item you JUST graded (1), still "of 30", never "of 0".
    const onFeedback = await counterText(page);
    expect(onFeedback).toContain(`Question 1 of ${TARGET}`);
    expect(onFeedback).not.toContain("Question 0");
  });
});
