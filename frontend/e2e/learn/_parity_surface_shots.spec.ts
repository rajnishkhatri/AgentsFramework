/**
 * Capture named full-page screenshots of each PreACT parity surface for the
 * 2026-07-13 e2e validation report. Not a behavioral gate — visual evidence only.
 */
import { test, expect, type Page } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  LEARN_SEED_CORPUS,
  LEARN_SEED_GLOBAL_KEY,
} from "../fixtures/preact_learn_corpus";

const OUT = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../../docs/plan/assets/preact-parity-e2e-2026-07-13/screenshots",
);

async function seed(page: Page): Promise<void> {
  await page.addInitScript(
    ([key, corpus]) => {
      (window as unknown as Record<string, unknown>)[key as string] = corpus;
    },
    [LEARN_SEED_GLOBAL_KEY, LEARN_SEED_CORPUS] as const,
  );
}

async function shot(page: Page, name: string): Promise<void> {
  await page.screenshot({
    path: path.join(OUT, `${name}.png`),
    fullPage: true,
  });
}

test.describe("Parity surface screenshots", () => {
  test.beforeEach(async ({ page }) => {
    await seed(page);
    await page.setViewportSize({ width: 1280, height: 800 });
  });

  test("01 dashboard", async ({ page }) => {
    await page.goto("/learn", { waitUntil: "networkidle" });
    await expect(page.locator("[data-testid='dashboard-root']")).toBeVisible({
      timeout: 15_000,
    });
    await shot(page, "01-dashboard");
  });

  test("02 quiz answering", async ({ page }) => {
    await page.goto("/learn/quiz", { waitUntil: "networkidle" });
    await expect(page.locator("[data-testid='quiz-context']")).toBeVisible({
      timeout: 15_000,
    });
    await shot(page, "02-quiz-answering");
  });

  test("03 quiz feedback + reveal + ask-coach", async ({ page }) => {
    await page.goto("/learn/quiz", { waitUntil: "networkidle" });
    await expect(page.locator("[data-testid='quiz-context']")).toBeVisible({
      timeout: 15_000,
    });
    await page.locator("[data-testid^='choice-']").first().click();
    await page.locator("[data-testid='quiz-submit']").click();
    await expect(page.locator("[data-testid='feedback-banner']")).toBeVisible({
      timeout: 10_000,
    });
    await shot(page, "03-quiz-feedback");
  });

  test("04 coach cold", async ({ page }) => {
    await page.goto("/learn/coach", { waitUntil: "networkidle" });
    await expect(page.locator("[data-testid='coach-root'], main").first()).toBeVisible({
      timeout: 15_000,
    });
    await shot(page, "04-coach-cold");
  });

  test("05 coach pinned from feedback", async ({ page }) => {
    await page.goto("/learn/quiz", { waitUntil: "networkidle" });
    await expect(page.locator("[data-testid='quiz-context']")).toBeVisible({
      timeout: 15_000,
    });
    await page.locator("[data-testid^='choice-']").first().click();
    await page.locator("[data-testid='quiz-submit']").click();
    await expect(page.locator("[data-testid='feedback-banner']")).toBeVisible({
      timeout: 10_000,
    });
    const ask = page.locator("[data-testid='feedback-ask-coach']");
    test.skip((await ask.count()) === 0, "Ask-the-coach not on this viewport");
    await ask.click();
    await expect(page).toHaveURL(/\/learn\/coach/);
    await shot(page, "05-coach-pinned");
  });

  test("06 skill detail", async ({ page }) => {
    await page.goto("/learn/skill?skillId=s-punc&context=returning", {
      waitUntil: "networkidle",
    });
    await expect(page.locator("[data-testid='skill-detail']")).toBeVisible({
      timeout: 15_000,
    });
    await shot(page, "06-skill-detail");
  });

  test("07 progress", async ({ page }) => {
    await page.goto("/learn/progress", { waitUntil: "networkidle" });
    await expect(page.locator("[data-testid='progress-root']")).toBeVisible({
      timeout: 15_000,
    });
    await shot(page, "07-progress");
  });

  test("08 summary", async ({ page }) => {
    await page.goto("/learn/quiz", { waitUntil: "networkidle" });
    await expect(page.locator("[data-testid='quiz-context']")).toBeVisible({
      timeout: 15_000,
    });
    await page.locator("[data-testid^='choice-']").first().click();
    await page.locator("[data-testid='quiz-submit']").click();
    await expect(page.locator("[data-testid='feedback-banner']")).toBeVisible({
      timeout: 10_000,
    });
    const finish = page.locator("[data-testid='quiz-finish']");
    if ((await finish.count()) > 0) {
      await finish.click();
    } else {
      await page.locator("[data-testid='quiz-end']").click();
      await page.goto("/learn/summary", { waitUntil: "networkidle" });
    }
    await expect(page).toHaveURL(/\/learn\/summary/);
    await shot(page, "08-summary");
  });
});
