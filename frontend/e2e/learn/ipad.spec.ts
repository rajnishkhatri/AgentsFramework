/**
 * PreAct iPad split — persistent live coach panel (FR-J3/J3a/J4) — Phase 4.3.
 *
 * The prototype oracle rows this re-states against the real shell:
 *   - ipad · "split Quiz with live coach panel"      → quiz_split_with_persistent_live_coach_panel
 *   - ipad · "in-drill coach panel posts into the Coach thread" → panel_message_lands_in_shared_coach_thread
 *   - ipad · deeper-hint "One more nudge"            → one_more_nudge_deeper_hint
 *
 * Surface: width 481..1024 is the iPad band (`surfaceForWidth`); 1024×768
 * exercises the split. The coach SSE is MOCKED (no live LLM); the shared-thread
 * assertion navigates via the in-app sidebar link (client-side nav — a
 * page.goto() would reload the JS heap and drop the module store, which is the
 * documented non-persistence contract, not a bug).
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

test.describe("PreAct iPad split (FR-J3/J3a)", () => {
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize(IPAD);
    await seedBrowser(page);
    await mockCoachSSE(page);
  });

  test("quiz_split_with_persistent_live_coach_panel", async ({ page }) => {
    await openQuiz(page);
    const panel = page.getByTestId("coach-panel");
    await expect(panel).toBeVisible();
    await expect(panel).toContainText("Socratic mode · watching this item");
    // Item-scoped composer copy (FR-J3), distinct from the Coach screen's.
    await expect(
      panel.getByPlaceholder("Ask about this item…"),
    ).toBeVisible();
    // The panel survives answering → reviewing (persistent, not per-phase).
    await page.locator("[data-testid^='choice-']").first().click();
    await page.locator("[data-testid='quiz-submit']").click();
    await expect(page.locator("[data-testid='feedback-banner']")).toBeVisible();
    await expect(panel).toBeVisible();
  });

  test("panel_message_lands_in_shared_coach_thread", async ({ page }) => {
    await openQuiz(page);
    const panel = page.getByTestId("coach-panel");
    const composer = panel.getByPlaceholder("Ask about this item…");
    await composer.fill("why is the comma wrong here?");
    await composer.press("Enter");

    // The mocked reply streams into the panel…
    await expect(panel.getByRole("log")).toContainText(
      "why is the comma wrong here?",
    );

    // …and the SAME thread is on the full Coach screen after in-app nav
    // (sidebar link → client-side transition keeps the module store alive).
    await page.getByRole("navigation", { name: "Primary" }).getByText("Coach").click();
    await expect(page).toHaveURL(/\/learn\/coach$/);
    await expect(
      page.getByRole("log", { name: "Coach conversation" }),
    ).toContainText("why is the comma wrong here?");
  });

  test("one_more_nudge_deeper_hint", async ({ page }) => {
    await openQuiz(page);
    const panel = page.getByTestId("coach-panel");
    const nudge = panel.getByTestId("one-more-nudge");

    // Two-tier: the deeper rungs are not shown until asked.
    await expect(panel).not.toContainText("Nudge 2:");

    await nudge.click();
    await expect(panel.getByTestId("panel-nudge-2")).toContainText(
      "name the rule in play",
    );
    await expect(panel).not.toContainText("Nudge 3:");

    await nudge.click();
    await expect(panel.getByTestId("panel-nudge-3")).toContainText(
      "find the exact spot where the choices differ",
    );

    // Ladder exhausted — there is NO rung 4 (FR-D5): the control disables.
    await expect(nudge).toBeDisabled();

    // Neither revealed tier leaks an answer (the reviewed-ladder discipline):
    // no "the answer is X" style reveal in the panel.
    await expect(panel).not.toContainText(/answer is [A-D]/);
  });
});
