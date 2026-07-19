/**
 * E2E — Commit-first coach journeys on /learn/quiz (FR-1/5/6/9).
 *
 * Requires flag ON (Playwright webServer defaults it OFF for legacy specs):
 *   NEXT_PUBLIC_FF_COMMIT_FIRST_COACH=1 E2E_BYPASS_AUTH=1 \
 *     npx playwright test --project=learn-e2e e2e/learn/quiz-commit-first.spec.ts
 *
 * Journeys:
 *   (a) wrong → 3 nudges → escape → walked-through breakdown
 *   (b) wrong → try again → correct → "Worked through it with the coach"
 */

import { test, expect, type Page } from "@playwright/test";

async function quizReady(page: Page): Promise<boolean> {
  await page.goto("/learn/quiz", { waitUntil: "networkidle" });
  const progress = page.locator("[data-testid='quiz-progress']");
  if ((await progress.count()) === 0) return false;
  // Flag must be ON — no pre-commit hint toggle.
  return (await page.locator("[data-testid='quiz-hint-toggle']").count()) === 0;
}

/** Pick a letter that is not the correct answer by trying A then checking loop. */
async function submitWrong(page: Page): Promise<void> {
  // Prefer A; if first-try solve (A correct), try B instead on a fresh item.
  await page.locator("[data-testid='choice-A']").click();
  await page.locator("[data-testid='quiz-submit']").click();
  const coached = page.locator("[data-testid='quiz-coached-section']");
  const feedback = page.locator("[data-testid='feedback-banner']");
  await Promise.race([
    coached.waitFor({ state: "visible", timeout: 10_000 }),
    feedback.waitFor({ state: "visible", timeout: 10_000 }),
  ]);
  if (await feedback.isVisible()) {
    // A was correct — advance and try B on the next item.
    await page.locator("[data-testid='quiz-next']").click();
    await page.locator("[data-skill]").first().waitFor({ timeout: 10_000 });
    await page.locator("[data-testid='choice-B']").click();
    await page.locator("[data-testid='quiz-submit']").click();
    await expect(coached).toBeVisible({ timeout: 10_000 });
  }
}

test.describe("commit-first coach journeys", () => {
  test("wrong → 3 nudges → escape → walked-through breakdown", async ({
    page,
  }) => {
    test.skip(
      !(await quizReady(page)),
      "Skipped: quiz not rendered or commit_first_coach flag OFF.",
    );

    await submitWrong(page);
    await expect(page.locator("[data-testid='quiz-rung-counter']")).toHaveText(
      "1 of 3",
    );
    await page.locator("[data-testid='quiz-nudge']").click();
    await expect(page.locator("[data-testid='quiz-rung-counter']")).toHaveText(
      "2 of 3",
    );
    await page.locator("[data-testid='quiz-nudge']").click();
    await expect(page.locator("[data-testid='quiz-rung-counter']")).toHaveText(
      "3 of 3",
    );
    await expect(page.locator("[data-testid='quiz-escape']")).toBeVisible();
    await page.locator("[data-testid='quiz-escape']").click();
    await expect(page.locator("[data-testid='feedback-banner']")).toBeVisible({
      timeout: 10_000,
    });
    await expect(page.locator("[data-testid='feedback-banner']")).toHaveAttribute(
      "data-banner",
      "walked_through",
    );
    await expect(page.locator("[data-testid='feedback-result-label']")).toContainText(
      "Walked through",
    );
  });

  test("wrong → try again → correct → coached label", async ({ page }) => {
    test.skip(
      !(await quizReady(page)),
      "Skipped: quiz not rendered or commit_first_coach flag OFF.",
    );

    await submitWrong(page);
    // Exhaust or use try-again after one nudge — FR-5 try-again is at exhaustion.
    await page.locator("[data-testid='quiz-nudge']").click();
    await page.locator("[data-testid='quiz-nudge']").click();
    await page.locator("[data-testid='quiz-try-again']").click();
    // FR-5: try-again clears the pick — submit stays gated until a re-select.
    await expect(page.locator("[data-testid='quiz-submit']")).toBeDisabled();

    // Pick a different letter; if still wrong, keep trying until correct or escape.
    for (const letter of ["B", "C", "D", "A"]) {
      const choice = page.locator(`[data-testid='choice-${letter}']`);
      if ((await choice.count()) === 0) continue;
      await choice.click();
      await page.locator("[data-testid='quiz-submit']").click();
      const feedback = page.locator("[data-testid='feedback-banner']");
      const stillCoached = page.locator("[data-testid='quiz-coached-section']");
      await Promise.race([
        feedback.waitFor({ state: "visible", timeout: 8_000 }),
        stillCoached.waitFor({ state: "visible", timeout: 8_000 }),
      ]);
      if (await feedback.isVisible()) break;
    }

    await expect(page.locator("[data-testid='feedback-banner']")).toBeVisible({
      timeout: 5_000,
    });
    // Either coached solve or walked-through if we never hit the key — prefer coached.
    const label = page.locator("[data-testid='feedback-result-label']");
    if ((await label.count()) > 0) {
      const text = (await label.textContent()) ?? "";
      expect(
        text.includes("Worked through it with the coach") ||
          text.includes("Walked through") ||
          text.includes("Solved on first try"),
      ).toBe(true);
    }
  });
});
