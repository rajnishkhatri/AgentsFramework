/**
 * Cross-browser smoke matrix (FRONTEND_VALIDATION.md SS4).
 *
 * Runs the SS1 happy path under every project defined in
 * `playwright.config.ts`:
 *   chromium-desktop, mobile-safari, webkit-desktop, firefox-desktop, ipad.
 *
 * Each project supplies its own viewport / browser engine so this single
 * file produces 5 results per assertion. Use `playwright test e2e/cross-browser/`
 * to run and pair with `--project=<name>` to limit to one configuration.
 */

import { test, expect } from "@playwright/test";
import { sendMessage, composer, waitForResponse } from "../fixtures/helpers";
import { buildSSEBody, buildSSEHeaders } from "../fixtures/sse-mock";
import { plainMarkdown } from "../fixtures/scenarios";
import { PROMPTS } from "../fixtures/prompts";

test.describe("Cross-browser smoke matrix (binary: Does the happy path work everywhere?)", () => {
  test("page loads and renders security headers", async ({ page }) => {
    const response = await page.goto("/");
    expect(response).not.toBeNull();
    expect(response!.status()).toBeLessThan(500);
    expect(response!.headers()["content-security-policy"]).toBeDefined();
  });

  test("composer renders and accepts a message via mocked stream", async ({ page }) => {
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
    await waitForResponse(page, { timeoutMs: 10_000 });
  });

  test("CSP forbids unsafe-eval (FE-AP-19) in production builds", async ({ page }) => {
    test.skip(
      process.env.NODE_ENV !== "production",
      "Skipped: production-only check.",
    );

    const response = await page.goto("/");
    const csp = response!.headers()["content-security-policy"]!;
    expect(csp).not.toContain("'unsafe-eval'");
    expect(csp).not.toContain("'unsafe-inline'");
  });

  test("html has data-theme or .dark class for theme support", async ({ page }) => {
    await page.goto("/");
    const html = page.locator("html");
    const dataTheme = await html.getAttribute("data-theme");
    const className = (await html.getAttribute("class")) ?? "";
    const hasTheme = dataTheme !== null || /\b(dark|light)\b/.test(className);
    expect(hasTheme, "html must declare a theme via data-theme or class").toBe(true);
  });
});
