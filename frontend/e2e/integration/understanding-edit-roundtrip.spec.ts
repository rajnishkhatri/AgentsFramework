/**
 * Tier 2 — TaskUnderstanding edit round trip (task_understanding plan
 * Phase 4, §5 "T2 Playwright E2E: pause → edit → resume").
 *
 * Drives the real Next.js BFF (`/api/run/stream` +
 * `/api/run/understanding/{threadId}`) against the mock middleware
 * (`fixtures/mock-middleware.ts`), whose "understanding" scenario holds
 * the SSE stream open until the browser pauses — the genuine abort/resume
 * transport behavior that T1 `route.fulfill` (atomic bodies) cannot
 * exercise. The same flow runs headlessly per-commit in
 * `components/chat/understanding_edit_flow.test.tsx` with a scripted
 * runtime; this spec proves it through the real BFF + fetch-SSE path.
 *
 * Requires:
 *   MOCK_MIDDLEWARE=1
 *   E2E_AUTHENTICATED=1 (BFF session auth; the edit route 401s without it)
 *
 * The live-backend span assertion (PARAMETER_CHANGED in the trace +
 * conditions_source="user_edited" in eval.goal_judge) stays on the GCP
 * verification checklist — it needs the real Python middleware.
 */

import { test, expect } from "../fixtures/auth.fixture";

test.describe.configure({ mode: "serial" });

test.describe("T2 understanding edit round trip (binary: Does pause→edit→resume reach the resumed card?)", () => {
  test.skip(
    process.env.MOCK_MIDDLEWARE !== "1",
    "Skipped: MOCK_MIDDLEWARE!=1 (T2 integration tests).",
  );

  test("pause → edit → save & resume renders the user_edited card and the answer", async ({
    authenticatedPage: page,
  }) => {
    await page.goto("/");

    const composer = page.locator("textarea[aria-label='Compose message']");
    await expect(composer).toBeVisible();
    await composer.fill("check my understanding of this task");
    await page.locator("button[aria-label='Send']").click();

    // Initial leg: card streams in, run stays open (pausable).
    const card = page.locator("[data-testid='task-understanding-card']");
    await expect(card).toBeVisible({ timeout: 10_000 });
    await expect(card).toHaveAttribute("data-source", "generated");

    // Pause + enter edit mode.
    await page.locator("[data-testid='understanding-edit']").click();
    await expect(card).toHaveAttribute("data-editing", "true");

    // Correct the intent and one condition.
    await page
      .locator("[data-testid='understanding-intent-input']")
      .fill("Only verify the file contents.");
    await page
      .locator("[data-testid='understanding-condition-input-1']")
      .fill("The verification command output was shown.");
    await page.locator("[data-testid='understanding-save']").click();

    // Resume leg: same turn completes with the edited artifact.
    const message = page.locator("[data-testid='assistant-message']");
    await expect(message).toHaveAttribute("data-state", "complete", {
      timeout: 15_000,
    });
    await expect(card).toHaveAttribute("data-source", "user_edited");
    await expect(card).toContainText("Only verify the file contents.");
    await expect(
      page.locator("[data-testid='understanding-condition-1']"),
    ).toContainText("verification command output");
    await expect(message).toContainText(
      "Resumed and completed against the corrected understanding.",
    );
  });

  test("cancel resumes unchanged: the card keeps its generated provenance", async ({
    authenticatedPage: page,
  }) => {
    await page.goto("/");
    const composer = page.locator("textarea[aria-label='Compose message']");
    await expect(composer).toBeVisible();
    await composer.fill("check my understanding again");
    await page.locator("button[aria-label='Send']").click();

    const card = page.locator("[data-testid='task-understanding-card']");
    await expect(card).toBeVisible({ timeout: 10_000 });
    await page.locator("[data-testid='understanding-edit']").click();
    await expect(card).toHaveAttribute("data-editing", "true");
    await page.locator("[data-testid='understanding-cancel-edit']").click();

    const message = page.locator("[data-testid='assistant-message']");
    await expect(message).toHaveAttribute("data-state", "complete", {
      timeout: 15_000,
    });
    await expect(card).toHaveAttribute("data-source", "generated");
  });
});
