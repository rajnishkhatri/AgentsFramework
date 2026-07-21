/**
 * PreAct iPad split — Direction 2b coachMode inline at 1024×768 (FR-J3/J3a).
 *
 * Surface: width 481..1024 is the iPad band; 1024 − 64 ≥ 900 → inline.
 * Coach SSE is MOCKED (no live LLM).
 */

import { test, expect, type Page } from "@playwright/test";
import {
  LEARN_SEED_CORPUS,
  LEARN_SEED_GLOBAL_KEY,
} from "../fixtures/preact_learn_corpus";
import { buildSSEBody, buildSSEHeaders } from "../fixtures/sse-mock";
import { coachTurn } from "../fixtures/coach_transcript";

const IPAD = { width: 1024, height: 768 };

async function seedBrowser(page: Page): Promise<void> {
  await page.addInitScript(
    ([key, corpus]) => {
      (window as unknown as Record<string, unknown>)[key as string] = corpus;
    },
    [LEARN_SEED_GLOBAL_KEY, LEARN_SEED_CORPUS] as const,
  );
}

async function mockCoachSSE(page: Page): Promise<void> {
  await page.route("**/api/coach/run/stream", async (route) => {
    await route.fulfill({
      status: 200,
      headers: buildSSEHeaders(),
      body: buildSSEBody(coachTurn()),
    });
  });
}

async function openQuiz(page: Page): Promise<void> {
  await page.goto("/learn/quiz");
  await expect(page.locator("[data-testid='quiz-context']")).toBeVisible({
    timeout: 10_000,
  });
}

test.describe("PreAct iPad split (FR-J3/J3a / coachMode inline)", () => {
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize(IPAD);
    await seedBrowser(page);
    await mockCoachSSE(page);
  });

  test("quiz_split_with_persistent_live_coach_panel", async ({ page }) => {
    await openQuiz(page);
    const panel = page.getByTestId("coach-panel-inline");
    await expect(panel).toBeVisible();
    await expect(page.getByTestId("coach-trigger-pill")).toHaveCount(0);
    await expect(page.getByTestId("coach-edge-tab")).toHaveCount(0);
    await expect(
      panel.getByPlaceholder("Ask about this item…"),
    ).toBeVisible();
    await page.locator("[data-testid^='choice-']").first().click();
    await page.locator("[data-testid='quiz-submit']").click();
    await expect(page.locator("[data-testid='feedback-banner']")).toBeVisible();
    await expect(panel).toBeVisible();
  });

  test("panel_message_lands_in_shared_coach_thread", async ({ page }) => {
    await openQuiz(page);
    const panel = page.getByTestId("coach-panel-inline");
    const composer = panel.getByPlaceholder("Ask about this item…");
    await composer.fill("why is the comma wrong here?");
    await composer.press("Enter");

    await expect(panel.getByRole("log")).toContainText(
      "why is the comma wrong here?",
    );

    await page
      .getByRole("navigation", { name: "Primary" })
      .getByRole("link", { name: "Coach" })
      .click();
    await expect(page).toHaveURL(/\/learn\/coach$/);
    await expect(
      page.getByRole("log", { name: "Coach conversation" }),
    ).toContainText("why is the comma wrong here?");
  });

  test("one_more_nudge_deeper_hint", async ({ page }) => {
    await openQuiz(page);
    const panel = page.getByTestId("coach-panel-inline");
    const nudge = panel.getByTestId("one-more-nudge");

    await expect(panel.getByTestId("panel-nudge-2")).toHaveCount(0);

    await nudge.click();
    await expect(panel.getByTestId("panel-nudge-2")).toBeVisible();
    await expect(panel.getByTestId("panel-nudge-3")).toHaveCount(0);

    await nudge.click();
    await expect(panel.getByTestId("panel-nudge-3")).toBeVisible();

    await expect(nudge).toBeDisabled();
    await expect(nudge).toHaveAttribute("aria-disabled", "true");
    await expect(panel).not.toContainText(/answer is [A-D]/);
  });
});
