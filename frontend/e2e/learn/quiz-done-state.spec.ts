/**
 * E2E — bounded quiz hard-stop and automatic summary handoff (Phase C).
 *
 * G8 justification: the former S5 tests asserted the now-forbidden
 * "Keep practising", Q31 over-run, milestone wait, and manual See-summary
 * behavior. They are replaced with the stronger FR-C1/C2/C3 contract:
 * resolving Q30 closes and routes automatically without another learner action.
 *
 * L4 Behavioral Validation: seeded browser engine, no backend/auth/LLM.
 * Run: `pnpm exec playwright test --project=learn-e2e e2e/learn/quiz-done-state.spec.ts`
 */

import { test, expect, type Page } from "@playwright/test";

const TARGET = 30;

async function counterText(page: Page): Promise<string> {
  const el = page.locator("[data-testid='quiz-progress']");
  if ((await el.count()) === 0) return "";
  return (await el.textContent())?.trim() ?? "";
}

async function resolveCurrentItem(
  page: Page,
  finalItem = false,
): Promise<void> {
  for (const letter of ["A", "B", "C", "D"]) {
    const choice = page.locator(`[data-testid='choice-${letter}']`);
    if ((await choice.count()) === 0) continue;
    await choice.click();
    await page.locator("[data-testid='quiz-submit']").click();
    const resolved = finalItem
      ? page
          .waitForURL(/\/learn\/summary\?session=/, { timeout: 10_000 })
          .then(() => true)
      : page
          .locator("[data-testid='quiz-next']")
          .waitFor({ state: "visible", timeout: 10_000 })
          .then(() => true);
    const wrong = page
      .locator(`[data-testid='choice-wrong-mark-${letter}']`)
      .waitFor({ state: "visible", timeout: 10_000 })
      .then(() => false);
    try {
      if (await Promise.any([resolved, wrong])) {
        return;
      }
    } catch {
      // Neither terminal UI signal appeared; the final error reports the item.
    }
  }
  throw new Error("item did not resolve after every available choice");
}

async function answerAndAdvance(page: Page): Promise<void> {
  await resolveCurrentItem(page);
  await page.locator("[data-testid='quiz-next']").click();
  await page.locator("[data-skill]").first().waitFor({ timeout: 10_000 });
}

test.describe("Quiz bounded completion — Phase C", () => {
  test("pre-target screens retain normal advance and finish controls", async ({
    page,
  }) => {
    await page.goto("/learn/quiz", { waitUntil: "networkidle" });
    test.skip(
      (await counterText(page)) === "",
      "Skipped: quiz not rendered (auth/env).",
    );

    await resolveCurrentItem(page);

    await expect(page.locator("[data-testid='quiz-next']")).toHaveText(
      /Next question/,
    );
    await expect(page.locator("[data-testid='quiz-finish']")).toHaveText(
      /Finish & see summary/,
    );
    await expect(
      page.locator("[data-testid='quiz-done-banner']"),
    ).toHaveCount(0);
  });

  test("resolving Q30 auto-closes and routes to summary without serving Q31", async ({
    page,
  }) => {
    test.setTimeout(180_000);
    await page.goto("/learn/quiz", { waitUntil: "networkidle" });
    test.skip(
      (await counterText(page)) === "",
      "Skipped: quiz not rendered (auth/env).",
    );

    for (let i = 0; i < TARGET - 1; i += 1) {
      await answerAndAdvance(page);
    }
    expect(await counterText(page)).toContain(
      `Question ${TARGET} of ${TARGET}`,
    );

    // The final resolution owns the handoff: no milestone/continue/finish click.
    await resolveCurrentItem(page, true);

    expect(page.url()).toContain("/learn/summary");
    expect(page.url()).toContain("session=");
    await expect(page.getByText(/Question 31(?:\s|$)/)).toHaveCount(0);
  });
});
