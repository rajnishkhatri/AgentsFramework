/**
 * PreAct `/learn` accessibility sweep (WCAG 2.2 AA, per surface).
 *
 * Two kinds of check live here:
 *
 *   1. The AXE SWEEPS (`assertNoBlockers`) run `@axe-core/playwright` on each
 *      seeded surface and require zero serious/critical violations. Live since
 *      the Phase-4 a11y pass closed the two pre-existing violation families:
 *      color-contrast (the light `--color-muted`/`--color-accent`/`--color-success`
 *      and six `--color-bucket-*` tokens were darkened at the token source,
 *      hues preserved — FR-K2) and definition-list (BucketCard's <dl> groups
 *      now hold exactly a <dt> + <dd>, no bare <span> siblings).
 *
 *   2. The STRUCTURAL checks (feedback-not-color-only; composer touch target)
 *      always run — they already hold and guard specific PreAct a11y contracts.
 *
 * Seeded via the same non-prod override hook as the loop spec; Coach via a mocked
 * SSE route.
 */

import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import {
  LEARN_SEED_CORPUS,
  LEARN_SEED_GLOBAL_KEY,
} from "../fixtures/preact_learn_corpus";
import { buildSSEBody, buildSSEHeaders } from "../fixtures/sse-mock";
import { coachTurn } from "../fixtures/coach_transcript";

async function seedBrowser(page: Page): Promise<void> {
  await page.addInitScript(
    ([key, corpus]) => {
      (window as unknown as Record<string, unknown>)[key as string] = corpus;
    },
    [LEARN_SEED_GLOBAL_KEY, LEARN_SEED_CORPUS] as const,
  );
}

async function assertNoBlockers(page: Page, label: string): Promise<void> {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag22aa", "best-practice"])
    .analyze();
  const blockers = results.violations.filter(
    (v) => v.impact === "serious" || v.impact === "critical",
  );
  expect(
    blockers,
    `[${label}] ${blockers.length} serious/critical a11y violations: ` +
      blockers.map((v) => `${v.id} (${v.nodes.length} nodes)`).join(", "),
  ).toEqual([]);
}

/** Drive Quiz to the reviewing sub-state (so Feedback is on screen for the sweep). */
async function answerOneItem(page: Page): Promise<void> {
  await expect(page.locator("[data-testid='quiz-context']")).toBeVisible({ timeout: 10_000 });
  await page.locator("[data-testid^='choice-']").first().click();
  await page.locator("[data-testid='quiz-submit']").click();
  await expect(page.locator("[data-testid='feedback-banner']")).toBeVisible();
}

test.describe("PreAct /learn axe sweep (Phase-4 oracle)", () => {
  test.beforeEach(async ({ page }) => {
    await seedBrowser(page);
  });

  test("Dashboard has zero serious/critical a11y violations", async ({ page }) => {
    await page.goto("/learn");
    await expect(page.locator("[data-testid^='bucket-']").first()).toBeVisible();
    await assertNoBlockers(page, "Dashboard");
  });

  test("Quiz has zero serious/critical a11y violations", async ({ page }) => {
    await page.goto("/learn/quiz");
    await assertNoBlockers(page, "Quiz");
  });

  test("Feedback has zero serious/critical a11y violations", async ({ page }) => {
    await page.goto("/learn/quiz");
    await answerOneItem(page);
    await assertNoBlockers(page, "Feedback");
  });

  test("Summary has zero serious/critical a11y violations", async ({ page }) => {
    await page.goto("/learn/quiz");
    await answerOneItem(page);
    await page.locator("[data-testid='quiz-finish']").click();
    await expect(page).toHaveURL(/\/learn\/summary\?session=/);
    await expect(page.locator("[data-testid='summary-score']")).toBeVisible({ timeout: 10_000 });
    await assertNoBlockers(page, "Summary");
  });

  test("Coach has zero serious/critical a11y violations", async ({ page }) => {
    await page.route("**/api/coach/run/stream", async (route) => {
      await route.fulfill({ status: 200, headers: buildSSEHeaders(), body: buildSSEBody(coachTurn()) });
    });
    await page.goto("/learn/coach");
    await expect(page.locator("[role='log']")).toBeVisible();
    await assertNoBlockers(page, "Coach");
  });
});

test.describe("PreAct /learn axe sweep — dark theme (FR-K1 × FR-K2)", () => {
  // The Phase-4.1 theme toggle makes dark mode reachable from every learn
  // screen, so the dark palette is now a user-facing surface and gets the same
  // AA sweep. next-themes persists the choice in localStorage("theme"); seeding
  // it renders dark from first paint.
  test.beforeEach(async ({ page }) => {
    await seedBrowser(page);
    await page.addInitScript(() => {
      window.localStorage.setItem("theme", "dark");
    });
  });

  test("Dashboard (dark) has zero serious/critical a11y violations", async ({ page }) => {
    await page.goto("/learn");
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    await expect(page.locator("[data-testid^='bucket-']").first()).toBeVisible();
    await assertNoBlockers(page, "Dashboard dark");
  });

  test("Quiz (dark) has zero serious/critical a11y violations (accent CTA)", async ({ page }) => {
    await page.goto("/learn/quiz");
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    await expect(page.locator("[data-testid='quiz-context']")).toBeVisible({ timeout: 10_000 });
    // Select a choice so the accent-filled selected state + live submit button
    // (the known white-on-accent residual) are both on screen for the sweep.
    await page.locator("[data-testid^='choice-']").first().click();
    await assertNoBlockers(page, "Quiz dark");
  });

  test("Feedback (dark) has zero serious/critical a11y violations (success/danger chips)", async ({ page }) => {
    await page.goto("/learn/quiz");
    await answerOneItem(page);
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    await assertNoBlockers(page, "Feedback dark");
  });
});

test.describe("PreAct /learn structural a11y contracts (always-on)", () => {
  test.beforeEach(async ({ page }) => {
    await seedBrowser(page);
  });

  test("Feedback conveys its verdict by text + role, not color alone (FR-A8)", async ({ page }) => {
    await page.goto("/learn/quiz");
    await answerOneItem(page);
    const banner = page.locator("[data-testid='feedback-banner']");
    await expect(banner).toHaveAttribute("role", "status");
    // A non-empty text label (celebrate/soft copy) rides alongside the color +
    // the icon — the signal is never color-only.
    const text = (await banner.textContent())?.trim() ?? "";
    expect(text.length).toBeGreaterThan(0);
  });

  test("Coach composer send affordance meets the ≥44px touch target", async ({ page }) => {
    await page.route("**/api/coach/run/stream", async (route) => {
      await route.fulfill({ status: 200, headers: buildSSEHeaders(), body: buildSSEBody(coachTurn()) });
    });
    await page.goto("/learn/coach");
    await expect(page.locator("[role='log']")).toBeVisible();

    const send = page
      .locator("[data-testid='send-button'], button[aria-label='Send']")
      .first();
    test.skip((await send.count()) === 0, "No dedicated send button — composer submits on Enter.");
    const box = await send.boundingBox();
    expect(box, "send button has a layout box").not.toBeNull();
    if (box) {
      expect(Math.min(box.width, box.height)).toBeGreaterThanOrEqual(44);
    }
  });
});
