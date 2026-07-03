/**
 * PreAct /learn layout constraints (FR-J1) + coarse-pointer touch targets
 * (FR-K3) — Phase 4.5.
 *
 * FR-J1: desktop content is constrained to ≤1180px and the Quiz column to
 * ≤760px — measured on the RENDERED boxes (a wide viewport would happily let
 * an unconstrained flex child sprawl), not asserted on class strings.
 *
 * FR-K3: while the pointer is coarse (the iPhone surface), every interactive
 * target is ≥44px in its smaller dimension: the bottom tab bar's links, the
 * focus-mode chrome's controls (✕ + theme toggle), and the quiz actions.
 */

import { test, expect, type Locator, type Page } from "@playwright/test";
import {
  LEARN_SEED_CORPUS,
  LEARN_SEED_GLOBAL_KEY,
} from "../fixtures/preact_learn_corpus";

async function seedBrowser(page: Page): Promise<void> {
  await page.addInitScript(
    ([key, corpus]) => {
      (window as unknown as Record<string, unknown>)[key as string] = corpus;
    },
    [LEARN_SEED_GLOBAL_KEY, LEARN_SEED_CORPUS] as const,
  );
}

async function minDimension(target: Locator): Promise<number> {
  const box = await target.boundingBox();
  expect(box, "target must have a layout box").not.toBeNull();
  return Math.min(box!.width, box!.height);
}

test.describe("FR-J1 width constraints (desktop)", () => {
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: 1600, height: 1000 });
    await seedBrowser(page);
  });

  test("dashboard content is constrained to ≤1180px on a 1600px viewport", async ({
    page,
  }) => {
    await page.goto("/learn");
    await expect(page.getByTestId("today-focus")).toBeVisible();
    const main = page.locator("main").first();
    const box = await main.boundingBox();
    expect(box!.width).toBeLessThanOrEqual(1180 + 1);
  });

  test("the quiz column is constrained to ≤760px", async ({ page }) => {
    await page.goto("/learn/quiz");
    const quiz = page.getByRole("region", { name: /quiz question/i });
    await expect(quiz).toBeVisible({ timeout: 10_000 });
    const box = await quiz.boundingBox();
    expect(box!.width).toBeLessThanOrEqual(760 + 1);
  });
});

test.describe("FR-K3 coarse-pointer touch targets (iPhone)", () => {
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await seedBrowser(page);
  });

  test("every bottom-tab-bar control is ≥44px", async ({ page }) => {
    await page.goto("/learn");
    const nav = page.getByRole("navigation", { name: "Primary" });
    await expect(nav).toBeVisible();
    const items = nav.locator("a, span[aria-disabled='true']");
    const count = await items.count();
    expect(count).toBeGreaterThan(0);
    for (let i = 0; i < count; i += 1) {
      const label = (await items.nth(i).textContent())?.trim() ?? `#${i}`;
      expect(
        await minDimension(items.nth(i)),
        `tab-bar control "${label}" must be ≥44px`,
      ).toBeGreaterThanOrEqual(44);
    }
  });

  test("focus-mode chrome controls (✕ close + theme toggle) are ≥44px", async ({
    page,
  }) => {
    await page.goto("/learn/quiz");
    await expect(page.locator("[data-testid='quiz-context']")).toBeVisible({
      timeout: 10_000,
    });
    expect(
      await minDimension(page.getByTestId("focus-close")),
      "focus ✕ must be ≥44px",
    ).toBeGreaterThanOrEqual(44);
    expect(
      await minDimension(page.getByRole("button", { name: /theme/i })),
      "theme toggle must be ≥44px",
    ).toBeGreaterThanOrEqual(44);
  });

  test("quiz actions (choices, Get-a-hint, Submit) are ≥44px", async ({
    page,
  }) => {
    await page.goto("/learn/quiz");
    await expect(page.locator("[data-testid='quiz-context']")).toBeVisible({
      timeout: 10_000,
    });
    const firstChoice = page.locator("[data-testid^='choice-']").first();
    expect(
      await minDimension(firstChoice),
      "choice row must be ≥44px",
    ).toBeGreaterThanOrEqual(44);
    expect(
      await minDimension(page.getByRole("button", { name: /hint/i })),
      "Get-a-hint must be ≥44px",
    ).toBeGreaterThanOrEqual(44);
    expect(
      await minDimension(page.getByTestId("quiz-submit")),
      "Submit must be ≥44px",
    ).toBeGreaterThanOrEqual(44);
  });
});
