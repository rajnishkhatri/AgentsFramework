/**
 * E1a `/learn/skill` surface e2e (FR-19 / FR-3 / FR-15).
 */

import { test, expect } from "@playwright/test";
import {
  LEARN_SEED_CORPUS,
  LEARN_SEED_GLOBAL_KEY,
} from "../fixtures/preact_learn_corpus";

async function seedBrowser(page: import("@playwright/test").Page): Promise<void> {
  await page.addInitScript(
    ([key, corpus]) => {
      (window as unknown as Record<string, unknown>)[key as string] = corpus;
    },
    [LEARN_SEED_GLOBAL_KEY, LEARN_SEED_CORPUS] as const,
  );
}

test.describe("/learn/skill — E1a", () => {
  test("FR-19: valid skillId renders the lesson", async ({ page }) => {
    await seedBrowser(page);
    await page.goto("/learn/skill?skillId=s-punc");
    await expect(page.locator("[data-testid='skill-detail']")).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.locator("[data-testid='block-ground']")).toBeVisible();
  });

  test("FR-19: missing skillId → 404-equiv", async ({ page }) => {
    await seedBrowser(page);
    await page.goto("/learn/skill");
    await expect(page.locator("[data-testid='skill-detail-404']")).toBeVisible({
      timeout: 15_000,
    });
  });

  test("FR-3: unknown skillId → 404-equiv", async ({ page }) => {
    await seedBrowser(page);
    await page.goto("/learn/skill?skillId=s-nope");
    await expect(page.locator("[data-testid='skill-detail-404']")).toBeVisible({
      timeout: 15_000,
    });
  });

  test("FR-15: Practice this skill CTA navigates to focused quiz", async ({
    page,
  }) => {
    await seedBrowser(page);
    await page.goto("/learn/skill?skillId=s-punc");
    await expect(page.locator("[data-testid='skill-detail']")).toBeVisible({
      timeout: 15_000,
    });
    await page.locator("[data-testid='try-choice-0']").click();
    const cta = page.locator("[data-testid='practice-skill-cta']");
    await expect(cta).toBeVisible();
    await expect(cta).toHaveAttribute("href", "/learn/quiz?focus=s-punc");
    await cta.click();
    await expect(page).toHaveURL(/\/learn\/quiz\?focus=s-punc/);
  });
});
