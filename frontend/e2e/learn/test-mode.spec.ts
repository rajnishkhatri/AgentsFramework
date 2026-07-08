/**
 * PreAct Test Mode — timed fixed-section runner (video-recorded, T1).
 *
 * Test Mode is DECOUPLED from the adaptive quiz: it runs a fixed English section
 * (the converted Test-01 corpus) with a live per-section countdown and grades the
 * whole section at once via the pure engine Grader. No backend, no auth, no live
 * LLM — the corpus is a checked-in `lib/` asset the page imports directly, and the
 * grader is browser-pure, so nothing needs seeding.
 *
 * Two behaviors are pinned:
 *   1. TIMED WALK — the countdown is visible and ticks DOWN; a SCRIPTED subset of
 *      answers (keyed to the official Test-01 key) yields a BYTE-STABLE raw score.
 *   2. AUTO-SUBMIT — with a tiny injected duration (`?dur=`, non-prod only) the
 *      clock hits zero and force-submits to the results screen with no manual tap.
 *
 * Video is `on` for the `learn-e2e` project, so each test yields a reviewable
 * recording.
 */

import { test, expect, type Page } from "@playwright/test";
import { TEST01_ENGLISH_ANSWER_KEY } from "../../lib/adapters/engine/_test01_english_corpus";
// D2 split: the timed test serves ONLY the manifest's test_only subset — the
// walk below must mirror exactly what the page serves.
import { TEST01_SERVED_QUESTIONS } from "../../lib/adapters/engine/_test01_split";

/**
 * A deterministic scripted decision per corpus question, in corpus order: answer
 * the first N correct (from the official key), the rest wrong, the tail
 * unanswered. The expected raw score is then a fixed function of this script,
 * independent of any scheduling (Test Mode has none). We answer the first 10
 * correct, next 5 wrong, leave the rest blank → raw = 10.
 */
const CORRECT_COUNT = 10;
const WRONG_COUNT = 5;
const EXPECTED_RAW = CORRECT_COUNT;
const TOTAL = TEST01_SERVED_QUESTIONS.length; // 24 after the D2 split

/** A wrong letter for a question: the first A–D letter that isn't its answer. */
function wrongLetterFor(questionId: string): string {
  const correct = TEST01_ENGLISH_ANSWER_KEY[questionId];
  return ["A", "B", "C", "D"].find((l) => l !== correct) ?? "A";
}

async function answerCurrent(page: Page, letter: string): Promise<void> {
  await expect(page.locator("[data-testid='quiz-context']")).toBeVisible({ timeout: 10_000 });
  await page.locator(`[data-testid='choice-${letter}']`).click();
}

test.describe("PreAct Test Mode (timed fixed section)", () => {
  test("a timed English section: clock ticks down and a scripted walk scores byte-stable", async ({
    page,
  }) => {
    await page.goto("/learn/test");

    // Intro → start the clock.
    await expect(page.locator("[data-testid='test-intro']")).toBeVisible();
    await page.locator("[data-testid='test-start']").click();

    // The countdown is visible and running. Read it twice and assert it decreased
    // (18:00 → less), proving a live tick rather than a static label.
    const timer = page.locator("[data-testid='test-timer']");
    await expect(timer).toBeVisible();
    const first = (await timer.textContent())?.trim() ?? "";
    await page.waitForTimeout(1_500);
    const second = (await timer.textContent())?.trim() ?? "";
    expect(second <= first).toBe(true); // mm:ss strings compare lexicographically while same width
    expect(second).not.toBe("18:00"); // it moved off the start

    // Walk the section applying the scripted decision to each item.
    for (let i = 0; i < TOTAL; i++) {
      const q = TEST01_SERVED_QUESTIONS[i]!;
      if (i < CORRECT_COUNT) {
        await answerCurrent(page, TEST01_ENGLISH_ANSWER_KEY[q.id]!);
      } else if (i < CORRECT_COUNT + WRONG_COUNT) {
        await answerCurrent(page, wrongLetterFor(q.id));
      } // else: leave unanswered

      const last = i === TOTAL - 1;
      await page.locator(`[data-testid='test-${last ? "submit-section" : "next"}']`).click();
    }

    // Results: the raw score is exactly the scripted correct count, byte-stable.
    await expect(page.locator("[data-testid='test-results']")).toBeVisible({ timeout: 10_000 });
    await expect(page.locator("[data-testid='test-score']")).toHaveText(
      `${EXPECTED_RAW}/${TOTAL}`,
    );
    // The official scale band renders (a range, not a single number).
    await expect(page.locator("[data-testid='test-scale-band']")).toBeVisible();
  });

  test("the countdown auto-submits the section at zero (no manual tap)", async ({ page }) => {
    // Inject a tiny duration so the clock expires in ~1.2s (non-prod ?dur= hook).
    await page.goto("/learn/test?dur=1200");
    await page.locator("[data-testid='test-start']").click();

    // Answer just the first item so the score isn't trivially structural.
    const q0 = TEST01_SERVED_QUESTIONS[0]!;
    await answerCurrent(page, TEST01_ENGLISH_ANSWER_KEY[q0.id]!);

    // Without any submit tap, the expiring countdown forces the results screen.
    await expect(page.locator("[data-testid='test-results']")).toBeVisible({ timeout: 10_000 });
    // One correct answer, the rest unanswered → raw 1.
    await expect(page.locator("[data-testid='test-score']")).toHaveText(`1/${TOTAL}`);
  });
});
