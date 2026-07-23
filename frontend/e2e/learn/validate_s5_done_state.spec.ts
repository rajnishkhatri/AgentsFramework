/**
 * VALIDATION WALK — Phase C bounded completion (/learn quiz).
 *
 * G8 justification: the old narrated walk validated S5's continuation and Q31
 * over-run, both explicitly removed by FR-C1/C2/C3. This walk now validates the
 * replacement contract: normal pre-target controls, Q30 boundary, then automatic
 * close + summary navigation with no continuation click.
 *
 * Run:
 *   E2E_SCREENSHOTS=1 CI=1 BASE_URL=http://localhost:3000 \
 *     pnpm exec playwright test --project=learn-e2e \
 *     e2e/learn/validate_s5_done_state.spec.ts --reporter=list
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

test("Phase C validation walk — target resolution auto-closes to summary", async ({
  page,
}, testInfo) => {
  test.setTimeout(180_000);
  const log = (msg: string) => console.log(`  ✔ ${msg}`);
  const shot = async (name: string) => {
    const body = await page.screenshot();
    await testInfo.attach(name, { body, contentType: "image/png" });
  };

  await page.goto("/learn/quiz", { waitUntil: "networkidle" });
  test.skip(
    (await counterText(page)) === "",
    "Skipped: quiz not rendered (auth/env).",
  );
  expect(await counterText(page)).toContain(`Question 1 of ${TARGET}`);

  await resolveCurrentItem(page);
  await expect(page.locator("[data-testid='quiz-next']")).toHaveText(
    /Next question/,
  );
  await expect(page.locator("[data-testid='quiz-finish']")).toHaveText(
    /Finish & see summary/,
  );
  await shot("01-pre-target-feedback");
  log("pre-target controls remain available");
  await page.locator("[data-testid='quiz-next']").click();
  await page.locator("[data-skill]").first().waitFor({ timeout: 10_000 });

  for (let i = 2; i <= TARGET - 1; i += 1) {
    await answerAndAdvance(page);
  }
  expect(await counterText(page)).toContain(
    `Question ${TARGET} of ${TARGET}`,
  );
  await shot("02-q30-boundary");
  log(`reached Question ${TARGET} of ${TARGET} without closing early`);

  await resolveCurrentItem(page, true);

  expect(page.url()).toContain("/learn/summary");
  expect(page.url()).toContain("session=");
  await expect(page.getByText(/Question 31(?:\s|$)/)).toHaveCount(0);
  await shot("03-auto-summary");
  log("Q30 resolution auto-closed and routed to Summary; no Q31");
});
