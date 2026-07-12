/**
 * E1b-D2 — open coach from a returning lesson seeds a skill-only pin (FR-8).
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

test.describe("/learn/skill — coach seed (E1b-D2)", () => {
  test("FR-8: Open coach from returning lesson → skill-pinned, no item panel", async ({
    page,
  }) => {
    await seedBrowser(page);
    // Force returning so coachEntry is on the rail (AL-17 requested override).
    await page.goto("/learn/skill?skillId=s-punc&context=returning");
    await expect(page.locator("[data-testid='skill-detail']")).toBeVisible({
      timeout: 15_000,
    });
    const entry = page.locator("[data-testid='coach-entry-seam']");
    await expect(entry).toBeVisible({ timeout: 10_000 });
    await entry.click();
    await expect(page).toHaveURL(/\/learn\/coach/, { timeout: 10_000 });
    // Lesson pin: no current-item panel (item chrome only).
    await expect(page.getByText(/Current item:/i)).toHaveCount(0);
    // Mode chrome should show In-drill Socratic (pre_submit).
    await expect(page.getByText(/In-drill Socratic/i)).toBeVisible();
  });

  test("FR-7 spoof edge: lesson open never surfaces answer reveal", async ({
    page,
  }) => {
    await seedBrowser(page);
    await page.goto("/learn/skill?skillId=s-punc&context=returning");
    await expect(page.locator("[data-testid='skill-detail']")).toBeVisible({
      timeout: 15_000,
    });
    await page.locator("[data-testid='coach-entry-seam']").click();
    await expect(page).toHaveURL(/\/learn\/coach/, { timeout: 10_000 });
    await expect(page.getByText(/correct answer/i)).toHaveCount(0);
  });
});
