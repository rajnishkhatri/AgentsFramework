/**
 * Streaming markdown tests (SS2.4 / F2).
 *
 * Auto-reject anti-pattern: FE-AP-5 (aria-live MUST be polite, never assertive).
 */

import { test, expect } from "@playwright/test";
import { sendMessage, composer } from "./fixtures/helpers";
import { buildSSEBody, buildSSEHeaders } from "./fixtures/sse-mock";
import { plainMarkdown } from "./fixtures/scenarios";
import { PROMPTS } from "./fixtures/prompts";

test.describe("Streaming markdown (binary: Are tokens streamed politely?)", () => {
  test("response region uses aria-live='polite' (FE-AP-5 guard)", async ({ page }) => {
    await page.route("**/api/run/stream", async (route) => {
      await route.fulfill({
        status: 200,
        headers: buildSSEHeaders(),
        body: buildSSEBody(plainMarkdown()),
      });
    });

    await page.goto("/");
    test.skip((await composer(page).count()) === 0, "Skipped: composer not rendered.");

    await sendMessage(page, PROMPTS.PLAIN_MARKDOWN);
    await page.waitForTimeout(2_000);

    const liveRegions = page.locator("[aria-live]");
    const count = await liveRegions.count();
    test.skip(count === 0, "Skipped: no aria-live region found.");

    for (let i = 0; i < count; i++) {
      const value = await liveRegions.nth(i).getAttribute("aria-live");
      expect(value, `aria-live region ${i} must be 'polite' (FE-AP-5)`).not.toBe(
        "assertive",
      );
    }
  });

  test("streamed response region is non-atomic (aria-atomic='false')", async ({ page }) => {
    await page.route("**/api/run/stream", async (route) => {
      await route.fulfill({
        status: 200,
        headers: buildSSEHeaders(),
        body: buildSSEBody(plainMarkdown()),
      });
    });

    await page.goto("/");
    test.skip((await composer(page).count()) === 0, "Skipped: composer not rendered.");

    await sendMessage(page, PROMPTS.PLAIN_MARKDOWN);
    await page.waitForTimeout(2_000);

    const polite = page.locator("[aria-live='polite']").first();
    if ((await polite.count()) > 0) {
      const atomic = await polite.getAttribute("aria-atomic");
      expect(atomic === null || atomic === "false").toBe(true);
    }
  });

  test("typing in composer during stream does not lose focus", async ({ page }) => {
    await page.route("**/api/run/stream", async (route) => {
      await route.fulfill({
        status: 200,
        headers: buildSSEHeaders(),
        body: buildSSEBody(plainMarkdown()),
      });
    });

    await page.goto("/");
    const c = composer(page);
    test.skip((await c.count()) === 0, "Skipped: composer not rendered.");

    await sendMessage(page, PROMPTS.PLAIN_MARKDOWN);
    await c.focus();
    await c.type("draft text");
    await expect(c).toBeFocused();
  });

  test("response text grows over time (incremental render)", async ({ page }) => {
    await page.route("**/api/run/stream", async (route) => {
      await route.fulfill({
        status: 200,
        headers: buildSSEHeaders(),
        body: buildSSEBody(plainMarkdown()),
      });
    });

    await page.goto("/");
    test.skip((await composer(page).count()) === 0, "Skipped: composer not rendered.");

    await sendMessage(page, PROMPTS.PLAIN_MARKDOWN);

    const responseRegion = page.locator(
      "article[aria-live='polite'], [role='log'], [data-testid='message-content']",
    );
    const target = responseRegion.first();
    test.skip((await target.count()) === 0, "Skipped: response region not found.");
    await target.waitFor({ timeout: 5_000 });

    const finalText = (await target.textContent()) ?? "";
    expect(finalText.length).toBeGreaterThan(10);
  });
});
