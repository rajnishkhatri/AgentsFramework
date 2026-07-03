/**
 * PreAct /learn theme toggle (FR-K1) — Phase 4.1.
 *
 * FR-K1: WHEN the theme toggle is activated THE SYSTEM SHALL flip `data-theme`
 * light↔dark and the token layer (incl. the six bucket accents) SHALL
 * re-resolve. The prototype oracle is iphone · "header toggle themes the whole
 * page"; this spec re-states it against the real shell:
 *
 *   - iPhone (≤480px): the non-focus chrome (Dashboard) carries a header
 *     toggle; flipping it themes <html data-theme> and persists across
 *     navigation into a focus screen (Quiz), whose FocusModeChrome header
 *     carries the same control.
 *   - desktop: the sidebar carries the toggle.
 *
 * Seeded via the same non-prod override hook as the loop spec (the dashboard
 * needs bucket cards on screen so the accent re-resolution is observable).
 */

import { test, expect, type Page } from "@playwright/test";
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

/** The resolved --color-accent custom property on <html> (re-resolves per theme). */
async function accentToken(page: Page): Promise<string> {
  return page.evaluate(() =>
    getComputedStyle(document.documentElement)
      .getPropertyValue("--color-accent")
      .trim(),
  );
}

const themeToggle = (page: Page) =>
  page.getByRole("button", { name: /theme/i }).first();

test.describe("PreAct /learn theme toggle (FR-K1)", () => {
  test.beforeEach(async ({ page }) => {
    await seedBrowser(page);
  });

  test("iPhone header toggle themes the whole page and the accents re-resolve", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/learn");
    await expect(page.locator("[data-testid^='bucket-']").first()).toBeVisible();

    const before = await accentToken(page);
    await themeToggle(page).click();

    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    // FR-K1: the token layer re-resolves — the accent is the dark-palette hex now.
    const after = await accentToken(page);
    expect(after).not.toBe(before);

    // Flips back (a toggle, not a one-way switch).
    await themeToggle(page).click();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  });

  test("the chosen theme persists into a focus screen, whose header keeps the control", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/learn");
    await expect(page.locator("[data-testid^='bucket-']").first()).toBeVisible();
    await themeToggle(page).click();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");

    // Enter the Quiz focus screen: theme sticks, and the focus chrome (which
    // hides every other control) still exposes the toggle (FR-K1 reachability).
    await page.goto("/learn/quiz");
    await expect(page.locator("[data-testid='quiz-context']")).toBeVisible({
      timeout: 10_000,
    });
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    await expect(themeToggle(page)).toBeVisible();
  });

  test("desktop sidebar carries the toggle", async ({ page }) => {
    await page.goto("/learn");
    await expect(page.locator("[data-testid^='bucket-']").first()).toBeVisible();
    await expect(themeToggle(page)).toBeVisible();
    await themeToggle(page).click();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  });
});
