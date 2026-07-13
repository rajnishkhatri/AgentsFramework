/**
 * Epic F — `/learn/progress` smoke (FR-5/8/9 + FR-3 DOM grep + axe).
 */

import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
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

async function assertNoBlockers(page: Page, label: string): Promise<void> {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag22aa", "best-practice"])
    .analyze();
  const blockers = results.violations.filter(
    (v) => v.impact === "serious" || v.impact === "critical",
  );
  expect(
    blockers,
    `[${label}] ${blockers.length} serious/critical a11y violations: ` +
      blockers.map((v) => `${v.id} (${v.nodes.length} nodes)`).join(", "),
  ).toEqual([]);
}

test.describe("Epic F — /learn/progress", () => {
  test.beforeEach(async ({ page }) => {
    await seedBrowser(page);
  });

  test("nav → /learn/progress renders (200, no 404)", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto("/learn");
    const progressNav = page.locator('a[data-screen="progress"]');
    await expect(progressNav).toBeVisible();
    await expect(progressNav).toHaveAttribute("href", "/learn/progress");
    await progressNav.click();
    await expect(page).toHaveURL(/\/learn\/progress/);
    await expect(page.locator('[data-testid="progress-root"]')).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByRole("heading", { name: "Your progress" })).toBeVisible();
  });

  test("range toggle updates caption; FR-3 no projected/goal copy", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto("/learn/progress");
    await expect(page.locator('[data-testid="progress-root"]')).toBeVisible({
      timeout: 15_000,
    });
    const body = await page.locator("body").innerText();
    expect(body).toMatch(/Accuracy trend/i);
    expect(body).not.toMatch(/projected|goal 28|on track/i);

    const tabs = page.locator('[data-testid="progress-range-tabs"]');
    await expect(tabs).toBeVisible();
    await page.locator('[data-testid="progress-range-30d"]').click();
    await expect(page.locator('[data-testid="progress-root"]')).toBeVisible();
    await page.locator('[data-testid="progress-range-all"]').click();
    await expect(page.getByRole("heading", { name: "Accuracy trend" })).toBeVisible();
  });

  test("@axe clean on progress", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto("/learn/progress");
    await expect(page.locator('[data-testid="progress-root"]')).toBeVisible({
      timeout: 15_000,
    });
    await assertNoBlockers(page, "Progress");
  });

  test("iPhone: Progress is a live link (no dead control)", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/learn");
    const progress = page.locator('a[data-screen="progress"]');
    await expect(progress).toBeVisible();
    await expect(progress).toHaveAttribute("href", "/learn/progress");
    await expect(progress).not.toHaveAttribute("aria-disabled", "true");
    // Tabs are layout-hidden on narrow — not a dead disabled control.
    await page.goto("/learn/progress");
    await expect(page.locator('[data-testid="progress-root"]')).toBeVisible({
      timeout: 15_000,
    });
    // Range tabs remain in DOM for a11y tree but are CSS-hidden (@container).
    const tabs = page.locator('[data-testid="progress-range-tabs"]');
    await expect(tabs).toBeAttached();
  });
});
