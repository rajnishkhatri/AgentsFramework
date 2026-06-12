/**
 * Task understanding card (task_understanding plan Phase 3, T1 mocked SSE).
 *
 * The plan-time artifact arrives in-stream as `CUSTOM task_understanding`
 * before the answer text. Soft gate: the card renders alongside the
 * streaming answer (never blocking it) with the restated intent, the
 * success checklist, and the provenance badge. Absent entirely when the
 * backend sent no artifact (failure path first — no card, no layout shift).
 */

import { test, expect } from "@playwright/test";
import { sendMessage, composer } from "./fixtures/helpers";
import { buildSSEBody, buildSSEHeaders } from "./fixtures/sse-mock";
import { taskUnderstandingRun, plainMarkdown } from "./fixtures/scenarios";

test.describe("Task understanding card (Phase 3 soft gate)", () => {
  test("no artifact event -> no card", async ({ page }) => {
    await page.route("**/api/run/stream", async (route) => {
      await route.fulfill({
        status: 200,
        headers: buildSSEHeaders(),
        body: buildSSEBody(plainMarkdown()),
      });
    });
    await page.goto("/");
    test.skip((await composer(page).count()) === 0, "Skipped: composer not rendered.");

    await sendMessage(page, "what is the moon?");
    await expect(page.locator("[data-testid='assistant-message']")).toHaveAttribute(
      "data-state",
      "complete",
      { timeout: 10_000 },
    );
    await expect(page.locator("[data-testid='task-understanding-card']")).toHaveCount(0);
  });

  test("artifact renders intent + checklist + provenance while the answer lands", async ({ page }) => {
    await page.route("**/api/run/stream", async (route) => {
      await route.fulfill({
        status: 200,
        headers: buildSSEHeaders(),
        body: buildSSEBody(taskUnderstandingRun()),
      });
    });
    await page.goto("/");
    test.skip((await composer(page).count()) === 0, "Skipped: composer not rendered.");

    await sendMessage(page, "create f3.txt and verify it");
    const message = page.locator("[data-testid='assistant-message']");
    await expect(message).toHaveAttribute("data-state", "complete", {
      timeout: 10_000,
    });

    const card = page.locator("[data-testid='task-understanding-card']");
    await expect(card).toBeVisible();
    await expect(card).toHaveAttribute("data-source", "generated");
    await expect(card).toHaveAttribute("data-condition-count", "2");
    await expect(card).toContainText("Create /workspace/f3.txt and verify its contents.");
    await expect(
      page.locator("[data-testid='understanding-condition-0']"),
    ).toContainText("exists with 'hello'");
    await expect(
      page.locator("[data-testid='understanding-condition-1']"),
    ).toContainText("listed via a shell command");

    // FD5: the card is its own layer — the answer body still rendered.
    await expect(message).toContainText("Created the file and verified its contents.");

    // Phase 4: edits are only possible while the run is live (the server
    // 409s late edits) — a completed run renders NO edit affordance.
    await expect(page.locator("[data-testid='understanding-edit']")).toHaveCount(0);
  });
});
