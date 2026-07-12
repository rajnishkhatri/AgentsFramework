/**
 * PreAct Sprint S1+S2 — Summary CTA contrast + tappable skill/bucket names.
 *
 * Spec: docs/plan/preact-summary-cta-and-skill-links.spec.md
 *
 * TWO proofs, both over the REAL dev bank path (NO `__PREACT_E2E_SEED__`
 * override — the app falls through to the Garvit-seed + governed-bank wiring, the
 * same path the bank-integration spec exercises). This is deliberate: the
 * recommended-next skill is a real bank skill, and the buckets are the six
 * ACT-English skills with Garvit's mastery spread.
 *
 *   T2 (FR-1). The "Start recommended drill" CTA must clear WCAG-AA contrast. Before
 *       the S1 fix it inherited the card's PER-BUCKET accent as its fill and,
 *       with white text over the mid/pale buckets, measured ~3.6:1 (FAIL). The
 *       fix fills with the bucket-independent BRAND accent (~6.5:1). We assert it
 *       with axe's `color-contrast` rule scoped to the recommended card, light
 *       AND dark (the brand accent has a dark value too).
 *
 *   T6 (FR-4, FR-5). The recommended-skill NAME (Summary) and each Dashboard
 *       BUCKET CARD are links into a focused drill (`/learn/quiz?focus=<id>`),
 *       honored by the Quiz page (FR-6) — never the coming-soon /learn/skill
 *       route (FR-2). We click each and assert the URL + a rendered quiz item.
 */

import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

/** Answer one bank item and Finish → land on the Summary (real dev bank path). */
async function walkToSummary(page: Page): Promise<void> {
  await page.goto("/learn/quiz", { waitUntil: "networkidle" });
  await expect(page.locator("[data-testid='quiz-context']")).toBeVisible({
    timeout: 15_000,
  });
  await page.locator("[data-testid^='choice-']").first().click();
  await page.locator("[data-testid='quiz-submit']").click();
  await expect(page.locator("[data-testid='feedback-banner']")).toBeVisible({
    timeout: 15_000,
  });
  await page.locator("[data-testid='quiz-finish']").click();
  await expect(page).toHaveURL(/\/learn\/summary\?session=/);
  await expect(page.locator("[data-testid='summary-recommended']")).toBeVisible({
    timeout: 15_000,
  });
}

/** Assert zero color-contrast violations within the recommended-next card. */
async function assertCtaContrast(page: Page, label: string): Promise<void> {
  const results = await new AxeBuilder({ page })
    .include("[data-testid='summary-recommended']")
    .withRules(["color-contrast"])
    .analyze();
  expect(
    results.violations,
    `[${label}] color-contrast violation on the recommended-next CTA/card: ` +
      results.violations
        .map((v) => `${v.id} (${v.nodes.length} nodes)`)
        .join(", "),
  ).toEqual([]);
}

test.describe("Summary CTA contrast (S1 / FR-1) — real dev bank path", () => {
  test("the 'Start recommended drill' CTA clears WCAG-AA contrast (light)", async ({
    page,
  }) => {
    await walkToSummary(page);
    // The CTA is the accent-filled control; assert it renders with the fix's
    // brand-accent utility (bucket-independent), then prove contrast via axe.
    const cta = page.locator("[data-testid='summary-start-next']");
    await expect(cta).toBeVisible();
    await expect(cta).toHaveClass(/bg-accent/);
    await assertCtaContrast(page, "Summary CTA light");
    // DoD evidence artifact: the legible CTA over its recommended-next card.
    if (process.env.CTA_SHOT_DIR) {
      await page
        .locator("[data-testid='summary-recommended']")
        .screenshot({ path: `${process.env.CTA_SHOT_DIR}/summary-cta-light.png` });
    }
  });

  test("the CTA clears WCAG-AA contrast in dark theme too", async ({ page }) => {
    // next-themes persists the choice in localStorage("theme"); seed dark so the
    // dark brand accent (#e5967c) + on-accent text pairing is the one measured.
    await page.addInitScript(() => {
      window.localStorage.setItem("theme", "dark");
    });
    await walkToSummary(page);
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    await assertCtaContrast(page, "Summary CTA dark");
    if (process.env.CTA_SHOT_DIR) {
      await page
        .locator("[data-testid='summary-recommended']")
        .screenshot({ path: `${process.env.CTA_SHOT_DIR}/summary-cta-dark.png` });
    }
  });
});

test.describe("Focused-drill navigation (S2 / FR-4, FR-5) — real dev bank path", () => {
  test("the Summary recommended-skill name opens a focused drill", async ({
    page,
  }) => {
    await walkToSummary(page);

    const link = page.locator("[data-testid='summary-skill-link']");
    await expect(link).toBeVisible();
    const href = await link.getAttribute("href");
    expect(href, "skill name links to a focused quiz").toMatch(
      /^\/learn\/quiz\?focus=/,
    );
    // FR-2: never the dead coming-soon Skill route.
    expect(href).not.toContain("/learn/skill");

    await link.click();
    await expect(page).toHaveURL(/\/learn\/quiz\?focus=/);
    // The focused drill renders a real bank item (FR-6 honored the param).
    await expect(page.locator("[data-testid='quiz-context']")).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.locator("[data-testid^='choice-']")).toHaveCount(4);
  });

  test("a Dashboard bucket card opens a focused drill on that skill", async ({
    page,
  }) => {
    await page.goto("/learn", { waitUntil: "networkidle" });
    const card = page.locator("[data-testid^='bucket-']").first();
    await expect(card).toBeVisible({ timeout: 15_000 });
    const href = await card.getAttribute("href");
    expect(href, "bucket card links to a focused quiz").toMatch(
      /^\/learn\/quiz\?focus=/,
    );
    expect(href).not.toContain("/learn/skill");

    await card.click();
    await expect(page).toHaveURL(/\/learn\/quiz\?focus=/);
    await expect(page.locator("[data-testid='quiz-context']")).toBeVisible({
      timeout: 15_000,
    });
  });
});
