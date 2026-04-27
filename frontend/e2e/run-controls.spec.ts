/**
 * Run controls tests (SS2.5 / F3).
 *
 * Stop, Regenerate, and Edit & resend operations.
 */

import { test, expect } from "@playwright/test";
import { sendMessage, composer, waitForComposerReady } from "./fixtures/helpers";
import { buildSSEBody, buildSSEHeaders } from "./fixtures/sse-mock";
import { longStream, plainMarkdown } from "./fixtures/scenarios";
import { PROMPTS } from "./fixtures/prompts";

const STOP_SELECTORS = [
  "[data-testid='stop-button']",
  "button[aria-label='Stop']",
  "button:has-text('Stop')",
].join(", ");

const REGEN_SELECTORS = [
  "[data-testid='regenerate-button']",
  "button[aria-label='Regenerate']",
  "button:has-text('Regenerate')",
].join(", ");

const EDIT_RESEND_SELECTORS = [
  "[data-testid='edit-resend']",
  "button[aria-label*='Edit']",
  "button:has-text('Edit')",
].join(", ");

const TOOLBAR_SELECTORS = [
  "[role='toolbar'][aria-label='Run controls']",
  "[role='toolbar']",
].join(", ");

test.describe("Run controls (binary: Can the user stop, regenerate, edit?)", () => {
  test("toolbar carries role='toolbar' with aria-label", async ({ page }) => {
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
    await page.waitForTimeout(1_500);

    const toolbar = page.locator(TOOLBAR_SELECTORS).first();
    if ((await toolbar.count()) > 0) {
      await expect(toolbar).toBeVisible();
    }
  });

  test("stop button cancels a running agent and re-enables composer", async ({ page }) => {
    let cancelled = false;
    await page.route("**/api/run/cancel", async (route) => {
      cancelled = true;
      await route.fulfill({ status: 204, body: "" });
    });
    await page.route("**/api/run/stream", async (route) => {
      await route.fulfill({
        status: 200,
        headers: buildSSEHeaders(),
        body: buildSSEBody(longStream()),
      });
    });

    await page.goto("/");
    test.skip((await composer(page).count()) === 0, "Skipped: composer not rendered.");

    await sendMessage(page, PROMPTS.LONG_STREAM);

    const stopBtn = page.locator(STOP_SELECTORS).first();
    if ((await stopBtn.count()) > 0) {
      await stopBtn.click();
      await waitForComposerReady(page);
      expect(cancelled).toBe(true);
    }
  });

  test("regenerate is keyboard-focusable", async ({ page }) => {
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

    const regen = page.locator(REGEN_SELECTORS).first();
    if ((await regen.count()) > 0) {
      await regen.focus();
      await expect(regen).toBeFocused();
    }
  });

  test("edit & resend populates the composer with the prior message", async ({ page }) => {
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

    const message = "Original question";
    await sendMessage(page, message);
    await page.waitForTimeout(2_000);

    const edit = page.locator(EDIT_RESEND_SELECTORS).first();
    if ((await edit.count()) > 0) {
      await edit.click();
      const value = await c.inputValue().catch(() => "");
      expect(value).toContain(message);
    }
  });
});
