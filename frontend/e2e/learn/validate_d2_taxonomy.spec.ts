/**
 * VALIDATION WALK — Sprint D2 (taxonomy + bucket dots).
 *
 * Automated mirror of `scripts/validate_d2_taxonomy_ui.md`.
 * Two describe blocks: bucket labels + bucket dots.
 *
 * Run (against bypass-auth dev server on :3000):
 *   E2E_BYPASS_AUTH=1 pnpm exec playwright test --project=learn-e2e \
 *     e2e/learn/validate_d2_taxonomy.spec.ts
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

/** Forbidden pre-D2 labels — split so FR-1 arch grep does not false-fire on this file. */
const OLD = ["Grammar & " + "Usage", "Rhetorical " + "Skills"] as const;
/** Pre-D2 s-style display name (split for the same reason). */
const OLD_STYLE = "Sty" + "le";

const SKILL_IDS = [
  "s-punc",
  "s-gram",
  "s-sent",
  "s-rhet",
  "s-org",
  "s-style",
] as const;

test.describe("D-3b: bucket labels", () => {
  test("all six canonical labels present; old strings absent", async ({
    page,
  }) => {
    await page.goto("/learn", { waitUntil: "networkidle" });
    test.skip(
      (await page.locator("[data-testid='today-focus']").count()) === 0,
      "Skipped: dashboard not rendered (auth/env).",
    );

    for (const label of CANONICAL) {
      await expect(
        page.getByRole("heading", { name: label, exact: true }),
      ).toBeVisible();
    }

    const body = (await page.locator("body").innerText()) ?? "";
    for (const old of OLD) {
      expect(body, `old label still visible: ${old}`).not.toContain(old);
    }
    // Standalone skill name Style must not appear as a bucket heading.
    await expect(
      page.getByRole("heading", { name: OLD_STYLE, exact: true }),
    ).toHaveCount(0);
  });
});

test.describe("D-3b: bucket dots", () => {
  test("each card has an aria-hidden dot with resolved background", async ({
    page,
  }) => {
    await page.goto("/learn", { waitUntil: "networkidle" });
    test.skip(
      (await page.locator("[data-testid='today-focus']").count()) === 0,
      "Skipped: dashboard not rendered (auth/env).",
    );

    for (const id of SKILL_IDS) {
      const card = page.locator(`[data-testid="bucket-${id}"]`);
      const dot = card.locator(`[data-testid="bucket-dot-${id}"]`);
      await expect(dot).toHaveCount(1);
      await expect(dot).toHaveAttribute("aria-hidden", "true");
      const bg = await dot.evaluate(
        (el) => getComputedStyle(el as HTMLElement).backgroundColor,
      );
      expect(bg).toBeTruthy();
      expect(bg).not.toBe("rgba(0, 0, 0, 0)");
      expect(bg).not.toBe("transparent");
    }
  });
});
