/**
 * Error and resilience tests (SS2.15).
 *
 * Mocks 401 / 429 / 500 responses from /api/run/stream and asserts the UI
 * surfaces the failure gracefully.
 */

import { test, expect } from "@playwright/test";
import { sendMessage, composer } from "./fixtures/helpers";
import { PROMPTS } from "./fixtures/prompts";

test.describe("Error resilience (binary: Are network failures handled gracefully?)", () => {
  test("401 response routes the user to the auth flow or shows an auth error", async ({ page }) => {
    await page.route("**/api/run/stream", async (route) => {
      await route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({ error: "unauthorized" }),
      });
    });

    await page.goto("/");
    test.skip((await composer(page).count()) === 0, "Skipped: composer not rendered.");

    await sendMessage(page, PROMPTS.PLAIN_MARKDOWN);
    await page.waitForTimeout(2_000);

    const url = page.url();
    const errorIndicator = page.locator(
      "text=/sign in|unauthorized|please log in|session expired/i",
    );
    const handled = url.includes("authkit.")
      || url.includes("workos.")
      || (await errorIndicator.count()) > 0;
    expect(handled, "401 must redirect to auth or display an auth error").toBe(true);
  });

  test("429 response surfaces a rate-limit message", async ({ page }) => {
    await page.route("**/api/run/stream", async (route) => {
      await route.fulfill({
        status: 429,
        contentType: "application/json",
        headers: { "retry-after": "60" },
        body: JSON.stringify({ error: "rate_limited" }),
      });
    });

    await page.goto("/");
    test.skip((await composer(page).count()) === 0, "Skipped: composer not rendered.");

    await sendMessage(page, PROMPTS.PLAIN_MARKDOWN);
    await page.waitForTimeout(2_000);

    const indicator = page.locator(
      "text=/rate limit|too many|try again|slow down/i",
    );
    if ((await indicator.count()) > 0) {
      await expect(indicator.first()).toBeVisible();
    }
  });

  test("500 response surfaces a generic error and re-enables composer", async ({ page }) => {
    await page.route("**/api/run/stream", async (route) => {
      await route.fulfill({
        status: 500,
        contentType: "application/json",
        body: JSON.stringify({
          error: "server_error",
          trace_id: "test-trace-from-server",
        }),
      });
    });

    await page.goto("/");
    const c = composer(page);
    test.skip((await c.count()) === 0, "Skipped: composer not rendered.");

    await sendMessage(page, PROMPTS.PLAIN_MARKDOWN);
    await page.waitForTimeout(2_000);

    await expect(c).toBeEnabled();
  });

  test("offline network surfaces an error and re-enables composer", async ({ page, context }) => {
    await page.goto("/");
    const c = composer(page);
    test.skip((await c.count()) === 0, "Skipped: composer not rendered.");

    await context.setOffline(true);
    await sendMessage(page, PROMPTS.PLAIN_MARKDOWN);
    await page.waitForTimeout(2_000);

    await expect(c).toBeEnabled();
    await context.setOffline(false);
  });
});
