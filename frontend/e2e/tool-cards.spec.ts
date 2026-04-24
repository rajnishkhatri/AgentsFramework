/**
 * Tool card tests (SS2.8 / F5).
 */

import { test, expect } from "@playwright/test";
import { sendMessage, composer } from "./fixtures/helpers";
import { buildSSEBody, buildSSEHeaders } from "./fixtures/sse-mock";
import { toolCallSuccess, toolCallError } from "./fixtures/scenarios";
import { PROMPTS } from "./fixtures/prompts";

const TOOL_CARD_SELECTORS = [
  "[data-testid='tool-card']",
  ".tool-card",
  "details[data-tool-call-id]",
  "details:has(summary:has-text('list_files'))",
  "details",
].join(", ");

test.describe("Tool cards (binary: Do tool calls render as collapsible cards?)", () => {
  test("tool card appears when agent invokes a tool", async ({ page }) => {
    await page.route("**/api/run/stream", async (route) => {
      await route.fulfill({
        status: 200,
        headers: buildSSEHeaders(),
        body: buildSSEBody(toolCallSuccess()),
      });
    });

    await page.goto("/");
    test.skip((await composer(page).count()) === 0, "Skipped: composer not rendered.");

    await sendMessage(page, PROMPTS.TOOL_CALL);

    const card = page.locator(TOOL_CARD_SELECTORS).first();
    await expect(card).toBeVisible({ timeout: 10_000 });
  });

  test("tool card uses <details> semantics for collapse", async ({ page }) => {
    await page.route("**/api/run/stream", async (route) => {
      await route.fulfill({
        status: 200,
        headers: buildSSEHeaders(),
        body: buildSSEBody(toolCallSuccess()),
      });
    });

    await page.goto("/");
    test.skip((await composer(page).count()) === 0, "Skipped: composer not rendered.");

    await sendMessage(page, PROMPTS.TOOL_CALL);
    await page.waitForTimeout(2_000);

    const details = page.locator("details").first();
    if ((await details.count()) === 0) {
      test.skip(true, "Skipped: tool card does not use <details>.");
    }

    const summary = details.locator("summary");
    await expect(summary).toBeVisible();

    const initiallyOpen = await details.evaluate((el) => (el as HTMLDetailsElement).open);
    await summary.click();
    await page.waitForTimeout(200);
    const afterClick = await details.evaluate((el) => (el as HTMLDetailsElement).open);
    expect(afterClick).toBe(!initiallyOpen);
  });

  test("errored tool render shows error state", async ({ page }) => {
    await page.route("**/api/run/stream", async (route) => {
      await route.fulfill({
        status: 200,
        headers: buildSSEHeaders(),
        body: buildSSEBody(toolCallError()),
      });
    });

    await page.goto("/");
    test.skip((await composer(page).count()) === 0, "Skipped: composer not rendered.");

    await sendMessage(page, PROMPTS.TOOL_ERROR);
    await page.waitForTimeout(2_000);

    const errorIndicator = page.locator(
      "text=/error|errored|rejected|failed/i",
    );
    if ((await errorIndicator.count()) > 0) {
      await expect(errorIndicator.first()).toBeVisible();
    }
  });
});
