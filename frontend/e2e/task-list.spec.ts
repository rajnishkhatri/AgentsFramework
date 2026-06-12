/**
 * Task-list tests (eval-UI F9). T1: canned STATE_DELTA{todos} frames ->
 * live checklist. Failure-path lead: a cancelled item must stay visibly
 * not-done (subtask-dropped evidence for the wave-2 adversarial cells).
 */

import { test, expect } from "@playwright/test";
import { sendMessage, composer } from "./fixtures/helpers";
import { buildSSEBody, buildSSEHeaders } from "./fixtures/sse-mock";
import { todoListRun } from "./fixtures/scenarios";

test.describe("Task list (binary: Does state_todo render as a live checklist?)", () => {
  test.beforeEach(async ({ page }) => {
    await page.route("**/api/run/stream", async (route) => {
      await route.fulfill({
        status: 200,
        headers: buildSSEHeaders(),
        body: buildSSEBody(todoListRun()),
      });
    });
    await page.goto("/");
  });

  test("cancelled item is never counted as done", async ({ page }) => {
    test.skip((await composer(page).count()) === 0, "Skipped: composer not rendered.");
    await sendMessage(page, "work through my checklist");

    const list = page.locator("[data-testid='task-list']");
    await expect(list).toBeVisible({ timeout: 10_000 });
    await expect(list).toHaveAttribute("data-todo-done", "2");
    await expect(list).toHaveAttribute("data-todo-count", "3");
    await expect(page.locator("[data-testid='todo-t3']")).toHaveAttribute(
      "data-status",
      "cancelled",
    );
  });

  test("checklist renders item content with progress count", async ({ page }) => {
    test.skip((await composer(page).count()) === 0, "Skipped: composer not rendered.");
    await sendMessage(page, "work through my checklist");

    const list = page.locator("[data-testid='task-list']");
    await expect(list).toBeVisible({ timeout: 10_000 });
    await expect(page.locator("[data-testid='todo-progress']")).toHaveText("2/3 done");
    await expect(page.locator("[data-testid='todo-t1']")).toContainText("read notes.md");
  });
});
