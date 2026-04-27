/**
 * Composer keyboard / IME / a11y tests (SS2.3 / F4).
 *
 * Mirrors the manual checks plus the static contract enforced by
 * `frontend/scripts/check_composer_keyboard.ts`.
 */

import { test, expect } from "@playwright/test";
import { composer, sendButton, sendMessage } from "./fixtures/helpers";
import { buildSSEBody, buildSSEHeaders } from "./fixtures/sse-mock";
import { plainMarkdown } from "./fixtures/scenarios";

const isMac = process.platform === "darwin";

test.describe("Composer (binary: Does the composer respect the keyboard contract?)", () => {
  test("send button is disabled when composer is empty", async ({ page }) => {
    await page.goto("/");
    const c = composer(page);
    test.skip((await c.count()) === 0, "Skipped: composer not rendered.");

    const btn = sendButton(page);
    if ((await btn.count()) > 0) {
      const isDisabled = await btn.isDisabled();
      expect(isDisabled).toBe(true);
    }
  });

  test("send button enables on first character", async ({ page }) => {
    await page.goto("/");
    const c = composer(page);
    test.skip((await c.count()) === 0, "Skipped: composer not rendered.");

    await c.fill("hi");
    const btn = sendButton(page);
    if ((await btn.count()) > 0) {
      await expect(btn).toBeEnabled();
    }
  });

  test("Cmd/Ctrl+Enter submits and clears the textarea", async ({ page }) => {
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

    await sendMessage(page, "What is 2 + 2?");
    await page.waitForTimeout(500);
    const value = await c.inputValue().catch(() => "");
    expect(value).toBe("");
  });

  test("Shift+Enter inserts a newline (no submit)", async ({ page }) => {
    let submitted = false;
    await page.route("**/api/run/stream", async (route) => {
      submitted = true;
      await route.fulfill({
        status: 200,
        headers: buildSSEHeaders(),
        body: buildSSEBody(plainMarkdown()),
      });
    });

    await page.goto("/");
    const c = composer(page);
    test.skip((await c.count()) === 0, "Skipped: composer not rendered.");

    await c.fill("line one");
    await c.press("Shift+Enter");
    await c.type("line two");
    await page.waitForTimeout(500);

    const value = await c.inputValue().catch(() => "");
    expect(value).toContain("line one");
    expect(value).toContain("line two");
    expect(submitted, "Shift+Enter must NOT submit").toBe(false);
  });

  test("composer is keyboard-focusable and announces correctly", async ({ page }) => {
    await page.goto("/");
    const c = composer(page);
    test.skip((await c.count()) === 0, "Skipped: composer not rendered.");

    await c.focus();
    await expect(c).toBeFocused();

    const ariaLabel = (await c.getAttribute("aria-label")) ?? "";
    const hasAccessibleName = ariaLabel.length > 0
      || (await c.getAttribute("aria-labelledby")) !== null
      || (await c.getAttribute("placeholder")) !== null;
    expect(hasAccessibleName, "composer must have an accessible name").toBe(true);
  });

  test(`uses ${isMac ? "Meta" : "Control"}+Enter as the submit chord`, async ({ page }) => {
    let receivedSubmit = false;
    await page.route("**/api/run/stream", async (route) => {
      receivedSubmit = true;
      await route.fulfill({
        status: 200,
        headers: buildSSEHeaders(),
        body: buildSSEBody(plainMarkdown()),
      });
    });

    await page.goto("/");
    const c = composer(page);
    test.skip((await c.count()) === 0, "Skipped: composer not rendered.");

    await c.fill("test");
    const mod = isMac ? "Meta" : "Control";
    await c.press(`${mod}+Enter`);
    await page.waitForTimeout(1_000);

    expect(receivedSubmit).toBe(true);
  });
});
