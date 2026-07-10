/**
 * VALIDATION WALK — Epic A/B continuity fixes (FLAG-1 / FLAG-4 / FLAG-6 / FR-8).
 *
 * Companion to docs/plan/epic-ab-continuity-fixes.spec.md and the manual
 * walkthrough at frontend/scripts/validate_continuity_fixes_ui.md.
 *
 * One narrated describe per fix so the reporter reads as a checklist.
 * FLAG-5 (Wrap-up `?session=`) stays out of scope (Epic C0) — documented in
 * the manual walk as a known gap, not asserted here.
 *
 * Run (against a running bypass-auth dev server on :3000):
 *   E2E_SCREENSHOTS=1 CI=1 BASE_URL=http://localhost:3000 \
 *     pnpm exec playwright test --project=learn-e2e \
 *     e2e/learn/validate_continuity_fixes.spec.ts --reporter=list
 *
 * Or: pnpm test:e2e:continuity
 */

import { test, expect, type Page } from "@playwright/test";

async function shot(
  page: Page,
  testInfo: import("@playwright/test").TestInfo,
  name: string,
): Promise<void> {
  const buf = await page.screenshot();
  await testInfo.attach(name, { body: buf, contentType: "image/png" });
}

async function openQuizAnswering(page: Page): Promise<void> {
  await page.goto("/learn/quiz", { waitUntil: "networkidle" });
  await expect(page.locator("[data-testid='quiz-context']")).toBeVisible({
    timeout: 15_000,
  });
}

async function submitFirstChoice(page: Page): Promise<void> {
  await page.locator("[data-testid^='choice-']").first().click();
  await page.locator("[data-testid='quiz-submit']").click();
  await expect(page.locator("[data-testid='feedback-banner']")).toBeVisible({
    timeout: 10_000,
  });
}

test.describe("Continuity fixes — FR-8 Reveal polish", () => {
  test("enabled Reveal uses foreground via data-enabled (not muted-only)", async ({
    page,
  }, testInfo) => {
    test.setTimeout(60_000);
    const step = (n: number, msg: string) => console.log(`  [FR-8/${n}] ${msg}`);

    await openQuizAnswering(page);
    const reveal = page.locator("[data-testid='quiz-reveal']");
    test.skip(
      (await reveal.count()) === 0,
      "quiz-reveal not rendered — auth or env gate is closed",
    );

    await expect(reveal).toBeDisabled();
    await expect(reveal).toHaveAttribute("data-enabled", "false");
    const disabledClass = (await reveal.getAttribute("class")) ?? "";
    expect(disabledClass).toMatch(/text-muted/);
    step(1, "disabled Reveal is muted ghost");

    await page.locator("[data-testid^='choice-']").first().click();
    await expect(reveal).toBeEnabled();
    await expect(reveal).toHaveAttribute("data-enabled", "true");
    const enabledClass = (await reveal.getAttribute("class")) ?? "";
    expect(enabledClass).toMatch(/data-\[enabled=true\]:text-fg|text-fg/);
    step(2, "enabled Reveal carries foreground treatment (FR-8)");
    await shot(page, testInfo, "FR-8-reveal-enabled");
  });
});

test.describe("Continuity fixes — FLAG-4 Back resumes left item", () => {
  test("Coach ← Back restores the left quiz item (not a fresh Q1)", async ({
    page,
  }, testInfo) => {
    test.setTimeout(90_000);
    const step = (n: number, msg: string) => console.log(`  [FLAG-4/${n}] ${msg}`);

    await openQuizAnswering(page);
    await submitFirstChoice(page);
    await page.locator("[data-testid='quiz-next']").click();
    await expect(page.locator("[data-testid='quiz-context']")).toBeVisible({
      timeout: 10_000,
    });
    step(1, "learner advanced past Q1 onto the leave-off item");

    const leftContext = await page.locator("[data-testid='quiz-context']").innerText();
    const progressBefore = await page
      .locator("[data-testid='quiz-progress']")
      .innerText()
      .catch(() => "");
    step(2, `leave-off progress="${progressBefore.slice(0, 40)}…"`);

    await submitFirstChoice(page);
    const askCoach = page.locator("[data-testid='feedback-ask-coach']");
    test.skip(
      (await askCoach.count()) === 0,
      "Ask-the-coach not on this surface (iPad split) — use desktop viewport",
    );
    await askCoach.click();
    await expect(page).toHaveURL(/\/learn\/coach/);
    step(3, "Ask-the-coach → /learn/coach");

    await page.locator("[data-testid='coach-back']").click();
    // Left from Feedback → resume restores reviewing (not answering), so the
    // passage lives on feedback-recap — quiz-context is answering-only.
    await expect(page.locator("[data-testid='feedback-banner']")).toBeVisible({
      timeout: 15_000,
    });
    await expect(page).toHaveURL(/\/learn\/quiz/);
    const returned = await page.locator("[data-testid='feedback-recap']").innerText();
    const norm = (s: string) => s.replace(/\s+/g, " ").trim();
    expect(norm(returned)).toContain(norm(leftContext).slice(0, 48));
    const progressAfter = await page
      .locator("[data-testid='quiz-progress']")
      .innerText()
      .catch(() => "");
    // Left from Feedback → resume reviewing at the same N (not answering N+1).
    expect(progressAfter).toBe(progressBefore);
    await expect(page.locator("[data-testid='quiz-next']")).toBeVisible();
    step(4, "Back restored the same quiz-context + progress in review (FR-3)");
    await shot(page, testInfo, "FLAG-4-resumed-item");
  });
});

test.describe("Continuity fixes — FLAG-1 miss-count refresh", () => {
  test("history N refreshes after a second pin on the same skill", async ({
    page,
  }, testInfo) => {
    test.setTimeout(120_000);
    const step = (n: number, msg: string) => console.log(`  [FLAG-1/${n}] ${msg}`);

    await openQuizAnswering(page);
    const skillA = await page.locator("[data-skill]").first().getAttribute("data-skill");
    step(0, `first item skill = ${skillA}`);

    await submitFirstChoice(page);
    const askCoach = page.locator("[data-testid='feedback-ask-coach']");
    test.skip((await askCoach.count()) === 0, "Ask-the-coach missing (desktop only)");
    await askCoach.click();
    await expect(page).toHaveURL(/\/learn\/coach/);

    const historyLine = page.locator("[data-testid='coach-history']");
    const firstText =
      (await historyLine.count()) > 0 ? await historyLine.innerText() : "";
    test.skip(
      firstText === "",
      "First pin produced no miss history — cannot prove N refresh",
    );
    step(1, `first pin history = "${firstText}"`);

    await page.locator("[data-testid='coach-back']").click();
    // Resume is reviewing — advance with Next (do not re-submit).
    await expect(page.locator("[data-testid='feedback-banner']")).toBeVisible({
      timeout: 15_000,
    });
    await page.locator("[data-testid='quiz-next']").click();

    let foundSameSkill = false;
    for (let i = 0; i < 12; i++) {
      await expect(page.locator("[data-testid='quiz-context']")).toBeVisible({
        timeout: 10_000,
      });
      const skill = await page.locator("[data-skill]").first().getAttribute("data-skill");
      step(2, `walk[${i}] skill = ${skill}`);
      if (skill === skillA) {
        foundSameSkill = true;
        break;
      }
      await submitFirstChoice(page);
      await page.locator("[data-testid='quiz-next']").click();
    }
    test.skip(
      !foundSameSkill,
      `No second item on skill ${skillA} within 12 steps`,
    );

    await submitFirstChoice(page);
    test.skip(
      (await askCoach.count()) === 0,
      "Second same-skill item was correct — no Ask-coach pin",
    );
    await askCoach.click();
    await expect(page).toHaveURL(/\/learn\/coach/);
    await expect(historyLine).toBeVisible({ timeout: 5_000 });
    const secondText = await historyLine.innerText();
    step(3, `second pin history = "${secondText}"`);
    expect(secondText).not.toBe(firstText);
    await shot(page, testInfo, "FLAG-1-history-refreshed");
  });
});

test.describe("Continuity fixes — FLAG-6 Mastery change label", () => {
  test('summary delta tile is labeled "Mastery change"', async ({
    page,
  }, testInfo) => {
    test.setTimeout(90_000);
    const step = (n: number, msg: string) => console.log(`  [FLAG-6/${n}] ${msg}`);

    await openQuizAnswering(page);
    await submitFirstChoice(page);
    await page.locator("[data-testid='quiz-finish']").click();
    await expect(page).toHaveURL(/\/learn\/summary/);
    step(1, "Finish → /learn/summary");

    const delta = page.locator("[data-testid='summary-delta']");
    await expect(delta).toBeVisible({ timeout: 10_000 });
    await expect(delta).toContainText(/Mastery change/i);
    const text = await delta.innerText();
    // Must not be a bare "Mastery" tile (FLAG-6). Allow "Mastery change".
    expect(text).toMatch(/Mastery change/i);
    expect(text.replace(/Mastery change/i, "").trim()).not.toMatch(/^Mastery\b/i);
    step(2, `delta tile text = "${text.replace(/\s+/g, " ").trim()}" (FR-7)`);
    await shot(page, testInfo, "FLAG-6-mastery-change");
  });
});
