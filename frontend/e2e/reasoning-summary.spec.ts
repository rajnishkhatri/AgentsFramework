/**
 * F10 Tier-2 "Show reasoning" expander (T1, mocked SSE).
 *
 * The recap arrives in-stream as `CUSTOM reasoning_summary` before
 * RUN_FINISHED. Progressive disclosure: collapsed by default, content
 * revealed on expand; absent entirely when the backend sent no recap
 * (cost guard skipped a 0–1-tool run).
 */

import { test, expect } from "@playwright/test";
import { sendMessage, composer } from "./fixtures/helpers";
import { buildSSEBody, buildSSEHeaders } from "./fixtures/sse-mock";
import { reasoningRecapRun, plainMarkdown } from "./fixtures/scenarios";

test.describe("Reasoning recap expander (F10 Tier-2)", () => {
  test("no recap event -> no expander (cost-guarded run)", async ({ page }) => {
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
    await expect(page.locator("[data-testid='reasoning-summary']")).toHaveCount(0);
  });

  test("recap renders collapsed, expands to the summary text", async ({ page }) => {
    await page.route("**/api/run/stream", async (route) => {
      await route.fulfill({
        status: 200,
        headers: buildSSEHeaders(),
        body: buildSSEBody(reasoningRecapRun()),
      });
    });
    await page.goto("/");
    test.skip((await composer(page).count()) === 0, "Skipped: composer not rendered.");

    await sendMessage(page, "write then verify the file");
    const message = page.locator("[data-testid='assistant-message']");
    await expect(message).toHaveAttribute("data-state", "complete", {
      timeout: 10_000,
    });

    const expander = page.locator("[data-testid='reasoning-summary']");
    await expect(expander).toBeVisible();
    // Collapsed by default (progressive disclosure).
    await expect(expander).not.toHaveAttribute("open", "");
    const recapText = expander.locator("p");
    await expect(recapText).toBeHidden();

    await expander.locator("summary").click();
    await expect(recapText).toBeVisible();
    await expect(recapText).toContainText("wrote the file first");

    // The recap is its own layer -- never part of the answer body.
    await expect(message).toContainText("The file now contains status=active.");
  });
});
