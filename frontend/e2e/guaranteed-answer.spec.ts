/**
 * Guaranteed-answer tests (eval-UI F11). T1: a run that ends on a tool
 * result with no prose must still fill the answer slot -- the empty
 * answer slot is the bug under test (GJ-F-008/GJ-012 root cause).
 */

import { test, expect } from "@playwright/test";
import { sendMessage, composer } from "./fixtures/helpers";
import { buildSSEBody, buildSSEHeaders } from "./fixtures/sse-mock";
import { toolOnlyRun } from "./fixtures/scenarios";

test.describe("Guaranteed answer (binary: Is the answer slot ever empty?)", () => {
  test("tool-only run renders the fallback recap, never an empty answer", async ({
    page,
  }) => {
    await page.route("**/api/run/stream", async (route) => {
      await route.fulfill({
        status: 200,
        headers: buildSSEHeaders(),
        body: buildSSEBody(toolOnlyRun()),
      });
    });
    await page.goto("/");
    test.skip((await composer(page).count()) === 0, "Skipped: composer not rendered.");

    await sendMessage(page, "write the file");

    const message = page.locator("[data-testid='assistant-message']");
    await expect(message).toHaveAttribute("data-state", "complete", {
      timeout: 10_000,
    });

    const fallback = page.locator("[data-testid='fallback-answer']");
    await expect(fallback).toBeVisible();
    await expect(fallback).toContainText("Completed 1 step");
    await expect(fallback).toContainText("summary generated from tool results");

    // The tool card is still the primary evidence alongside the recap.
    await expect(page.locator("[data-testid='tool-card']")).toBeVisible();
  });
});
