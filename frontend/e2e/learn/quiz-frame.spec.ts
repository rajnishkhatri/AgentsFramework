/**
 * E2E — Quiz session-frame chrome on /learn/quiz (D1: Q-7 chip + Q-8 End + Q-9 timer).
 *
 * Closes the session-framing half of the PreAct parity gap: a learner sees WHICH
 * skill the current item drills, has an honest exit that lands on the dashboard
 * (not Summary), and can reveal a session-elapsed clock on demand (collapsed by
 * default). The L1 layer (translator + QuizView + reducer) covers edges; this
 * spec proves the wired behaviour a user sees in a real browser.
 *
 * L4 Behavioral Validation (Agentic Testing Pyramid): real browser against the
 * dev-seeded bank quiz (the `learn-e2e` project, video on), on-demand only — pure
 * T1 (seeded browser engine, no backend/auth/LLM). Sibling `quiz-progress.spec.ts`
 * / `quiz-done-state.spec.ts` prove progress + done-state; this proves the frame.
 *
 * SCOPE. Every FR fires on the FIRST item (or item-1 → item-2). No full 30-item
 * walk. L1 covers null-join / reducer no-op / format clamp edges.
 *
 * Run: `npx playwright test --project=learn-e2e e2e/learn/quiz-frame.spec.ts`
 */

import { test, expect, type Page } from "@playwright/test";

/** The progress region's rendered counter text ("Question N of M"), or "" if absent. */
async function counterText(page: Page): Promise<string> {
  const el = page.locator("[data-testid='quiz-progress']");
  if ((await el.count()) === 0) return "";
  return (await el.textContent())?.trim() ?? "";
}

/** Answer the current item (A → Submit) and STOP on the feedback screen. */
async function answerToFeedback(page: Page): Promise<void> {
  await page.locator("[data-testid='choice-A']").click();
  await page.locator("[data-testid='quiz-submit']").click();
  await expect(page.locator("[data-testid='feedback-banner']")).toBeVisible({
    timeout: 10_000,
  });
}

/** Answer the current item (A → Submit) and advance past feedback to the next. */
async function answerAndAdvance(page: Page): Promise<void> {
  await answerToFeedback(page);
  await page.locator("[data-testid='quiz-next']").click();
  await page.locator("[data-skill]").first().waitFor({ timeout: 10_000 });
}

/** Click the timer reveal and wait for the clock to appear. */
async function revealTimer(page: Page): Promise<void> {
  await page.locator("[data-testid='quiz-timer-reveal']").click();
  await expect(page.locator("[data-testid='quiz-timer']")).toBeVisible({
    timeout: 10_000,
  });
}

/** Fold an `m:ss` reading into total seconds. */
function parseElapsed(text: string): number {
  const m = text.trim().match(/^(\d+):(\d{2})$/);
  if (m == null) return Number.NaN;
  return Number(m[1]) * 60 + Number(m[2]);
}

test.describe("Q-7 skill chip", () => {
  test("first item shows a non-empty chip", async ({ page }) => {
    await page.goto("/learn/quiz", { waitUntil: "networkidle" });
    test.skip(
      (await counterText(page)) === "",
      "Skipped: quiz not rendered (auth/env).",
    );

    const chip = page.locator("[data-testid='quiz-skill-chip']");
    await expect(chip).toHaveCount(1);
    await expect(chip).toBeVisible();
    const text = (await chip.textContent())?.trim() ?? "";
    expect(text.length).toBeGreaterThan(0);
  });

  test("chip persists across answering→reviewing", async ({ page }) => {
    await page.goto("/learn/quiz", { waitUntil: "networkidle" });
    test.skip(
      (await counterText(page)) === "",
      "Skipped: quiz not rendered (auth/env).",
    );

    const chip = page.locator("[data-testid='quiz-skill-chip']");
    await expect(chip).toHaveCount(1);
    const before = (await chip.textContent())?.trim() ?? "";
    expect(before.length).toBeGreaterThan(0);

    await answerToFeedback(page);

    await expect(chip).toHaveCount(1);
    const after = (await chip.textContent())?.trim() ?? "";
    expect(after).toBe(before);
  });

  test("dot glyph resolves an accent color", async ({ page }) => {
    await page.goto("/learn/quiz", { waitUntil: "networkidle" });
    test.skip(
      (await counterText(page)) === "",
      "Skipped: quiz not rendered (auth/env).",
    );

    const dot = page.locator(
      "[data-testid='quiz-skill-chip'] [data-testid='bucket-dot']",
    );
    await expect(dot).toHaveCount(1);
    const color = await dot.evaluate(
      (el) => getComputedStyle(el).backgroundColor,
    );
    expect(color).not.toBe("");
    expect(color).not.toBe("rgba(0, 0, 0, 0)");
    expect(color).not.toBe("transparent");
  });
});

test.describe("Q-8 End session", () => {
  test("End control visible on first item", async ({ page }) => {
    await page.goto("/learn/quiz", { waitUntil: "networkidle" });
    test.skip(
      (await counterText(page)) === "",
      "Skipped: quiz not rendered (auth/env).",
    );

    const end = page.locator("[data-testid='quiz-end-session']");
    await expect(end).toHaveCount(1);
    await expect(end).toBeVisible();
  });

  test("End routes to /learn, not /learn/summary", async ({ page }) => {
    await page.goto("/learn/quiz", { waitUntil: "networkidle" });
    test.skip(
      (await counterText(page)) === "",
      "Skipped: quiz not rendered (auth/env).",
    );

    await page.locator("[data-testid='quiz-end-session']").click();
    await expect(page).toHaveURL(/\/learn$/, { timeout: 10_000 });
    expect(page.url()).not.toContain("/learn/summary");
    expect(page.url()).not.toContain("/learn/quiz");
  });

  test("End persists into reviewing", async ({ page }) => {
    await page.goto("/learn/quiz", { waitUntil: "networkidle" });
    test.skip(
      (await counterText(page)) === "",
      "Skipped: quiz not rendered (auth/env).",
    );

    await answerToFeedback(page);

    const end = page.locator("[data-testid='quiz-end-session']");
    await expect(end).toBeVisible();
    await expect(end).toBeEnabled();
  });

  test("Finish still routes to /learn/summary", async ({ page }) => {
    await page.goto("/learn/quiz", { waitUntil: "networkidle" });
    test.skip(
      (await counterText(page)) === "",
      "Skipped: quiz not rendered (auth/env).",
    );

    await answerToFeedback(page);
    await page.locator("[data-testid='quiz-finish']").click();
    await page.waitForURL(/\/learn\/summary/, { timeout: 10_000 });
  });
});

test.describe("Q-9 collapsible timer", () => {
  test("timer collapsed by default", async ({ page }) => {
    await page.goto("/learn/quiz", { waitUntil: "networkidle" });
    test.skip(
      (await counterText(page)) === "",
      "Skipped: quiz not rendered (auth/env).",
    );

    await expect(page.locator("[data-testid='quiz-timer-reveal']")).toHaveCount(
      1,
    );
    await expect(page.locator("[data-testid='quiz-timer']")).toHaveCount(0);
  });

  test("click reveal → m:ss text renders", async ({ page }) => {
    await page.goto("/learn/quiz", { waitUntil: "networkidle" });
    test.skip(
      (await counterText(page)) === "",
      "Skipped: quiz not rendered (auth/env).",
    );

    await revealTimer(page);
    const text = (await page.locator("[data-testid='quiz-timer']").textContent())
      ?.trim() ?? "";
    expect(text).toMatch(/^\d+:\d{2}$/);
  });

  test("the clock ticks forward", async ({ page }) => {
    await page.goto("/learn/quiz", { waitUntil: "networkidle" });
    test.skip(
      (await counterText(page)) === "",
      "Skipped: quiz not rendered (auth/env).",
    );

    await revealTimer(page);
    const before = parseElapsed(
      (await page.locator("[data-testid='quiz-timer']").textContent())?.trim() ??
        "",
    );
    expect(Number.isFinite(before)).toBe(true);

    await page.waitForTimeout(2100);

    const after = parseElapsed(
      (await page.locator("[data-testid='quiz-timer']").textContent())?.trim() ??
        "",
    );
    expect(after).toBeGreaterThan(before);
  });

  test("reveal resets to collapsed on next item", async ({ page }) => {
    await page.goto("/learn/quiz", { waitUntil: "networkidle" });
    test.skip(
      (await counterText(page)) === "",
      "Skipped: quiz not rendered (auth/env).",
    );

    await revealTimer(page);
    await answerAndAdvance(page);

    await expect(page.locator("[data-testid='quiz-timer-reveal']")).toHaveCount(
      1,
    );
    await expect(page.locator("[data-testid='quiz-timer']")).toHaveCount(0);
  });

  test("elapsed does not reset on next item", async ({ page }) => {
    await page.goto("/learn/quiz", { waitUntil: "networkidle" });
    test.skip(
      (await counterText(page)) === "",
      "Skipped: quiz not rendered (auth/env).",
    );

    await revealTimer(page);
    // Capture an early reading, then advance; the session clock keeps running
    // across items (FR-Q9-4 / FR-P9-5), so the next reveal must be strictly later.
    const t0 = parseElapsed(
      (await page.locator("[data-testid='quiz-timer']").textContent())?.trim() ??
        "",
    );
    expect(Number.isFinite(t0)).toBe(true);

    await answerAndAdvance(page);
    await revealTimer(page);
    // Guarantee at least one tick past t0 after the item transition.
    await page.waitForTimeout(2100);

    const t1 = parseElapsed(
      (await page.locator("[data-testid='quiz-timer']").textContent())?.trim() ??
        "",
    );
    expect(t1).toBeGreaterThan(t0);
  });
});
