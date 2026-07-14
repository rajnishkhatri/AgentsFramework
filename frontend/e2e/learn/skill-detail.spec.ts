/**
 * E2E — SD-6: a dashboard bucket card opens Skill detail (the teach plane).
 *
 * The parity review flagged that the bucket card still drilled into
 * `/learn/quiz?focus=` instead of the now-live `/learn/skill` route (SD-6, the
 * 3rd of three skill entry points E1a wired). This spec is the integration
 * guard the review said was owed: click a bucket → land on `/learn/skill?
 * skillId=<id>` → the skill-detail surface renders (not the quiz frame).
 *
 * Run: `pnpm exec playwright test --project=learn-e2e e2e/learn/skill-detail.spec.ts`
 */

import { test, expect } from "@playwright/test";

test.describe("SD-6 — bucket card → Skill detail", () => {
  test("clicking a bucket navigates to /learn/skill (not a quiz drill)", async ({
    page,
  }) => {
    await page.goto("/learn", { waitUntil: "networkidle" });
    test.skip(
      (await page.locator("[data-testid='today-focus']").count()) === 0,
      "Skipped: dashboard not rendered (auth/env).",
    );

    const card = page.locator('[data-testid="bucket-s-punc"]');
    await expect(card).toHaveCount(1);

    // The link target itself is the teach plane, never the old drill.
    const href = await card.getAttribute("href");
    expect(href).toBe("/learn/skill?skillId=s-punc");
    expect(href).not.toContain("/learn/quiz?focus=");

    await card.click();

    // Landed on Skill detail — the URL and the surface both confirm it.
    await page.waitForURL(/\/learn\/skill\?skillId=s-punc/, { timeout: 15_000 });
    await expect(page.locator("[data-testid='skill-detail']")).toBeVisible({
      timeout: 15_000,
    });
    // And it is NOT the quiz frame (the pre-SD-6 destination).
    await expect(page.locator("[data-testid='quiz-frame']")).toHaveCount(0);
  });
});
