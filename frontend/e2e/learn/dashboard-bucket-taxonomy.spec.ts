/**
 * E2E — Dashboard bucket taxonomy + color dots (D2: D-3b / FR-5).
 *
 * Asserts the six ACT-standard labels and a resolved accent dot on each
 * BucketCard header. L1 covers FR-2 null fallback; this is the chromium smoke.
 *
 * Run: `pnpm exec playwright test --project=learn-e2e e2e/learn/dashboard-bucket-taxonomy.spec.ts`
 */

import { test, expect } from "@playwright/test";

const CANONICAL = [
  "Punctuation",
  "Usage",
  "Sentence Structure",
  "Rhetoric",
  "Organization",
  "Conciseness",
] as const;

const SKILL_IDS = [
  "s-punc",
  "s-gram",
  "s-sent",
  "s-rhet",
  "s-org",
  "s-style",
] as const;

test.describe("D2 dashboard bucket taxonomy", () => {
  test("six cards show canonical labels and resolved bucket dots", async ({
    page,
  }) => {
    await page.goto("/learn", { waitUntil: "networkidle" });
    test.skip(
      (await page.locator("[data-testid='today-focus']").count()) === 0,
      "Skipped: dashboard not rendered (auth/env).",
    );

    const cards = page.locator("[data-testid^='bucket-s-']");
    await expect(cards).toHaveCount(6);

    const headerTexts: string[] = [];
    for (const id of SKILL_IDS) {
      const card = page.locator(`[data-testid="bucket-${id}"]`);
      await expect(card).toHaveCount(1);
      const h3 = card.locator("header h3");
      const name = ((await h3.textContent()) ?? "").trim();
      headerTexts.push(name);

      const dot = card.locator(`[data-testid="bucket-dot-${id}"]`);
      await expect(dot).toHaveCount(1);
      await expect(dot).toHaveAttribute("aria-hidden", "true");

      const bg = await dot.evaluate(
        (el) => getComputedStyle(el as HTMLElement).backgroundColor,
      );
      expect(bg, `dot ${id} background must resolve`).toBeTruthy();
      expect(bg).not.toBe("rgba(0, 0, 0, 0)");
      expect(bg).not.toBe("transparent");
    }

    expect(headerTexts.sort()).toEqual([...CANONICAL].sort());
  });
});
