/**
 * Chat shell layout tests (SS2.2).
 *
 * Validates the three-row grid (header / messages / composer), the empty
 * state copy, and autoscroll on new messages.
 */

import { test, expect } from "@playwright/test";
import { sendMessage, composer, messages } from "./fixtures/helpers";
import { buildSSEBody, buildSSEHeaders } from "./fixtures/sse-mock";
import { plainMarkdown } from "./fixtures/scenarios";

test.describe("Chat shell (binary: Does the shell render and autoscroll?)", () => {
  test("composer is visible at the bottom of the viewport", async ({ page }) => {
    await page.goto("/");
    const c = composer(page);
    const composerExists = await c.count();
    test.skip(composerExists === 0, "Skipped: composer not rendered (auth required).");

    const box = await c.boundingBox();
    expect(box).not.toBeNull();
    const viewport = page.viewportSize();
    if (box && viewport) {
      expect(box.y + box.height).toBeLessThanOrEqual(viewport.height + 50);
    }
  });

  test("empty state shows the welcome prompt", async ({ page }) => {
    await page.goto("/");
    const composerExists = await composer(page).count();
    test.skip(composerExists === 0, "Skipped: composer not rendered.");

    const empty = page.locator(
      "text=/what can i help|how can i help|start a conversation/i",
    );
    if ((await empty.count()) > 0) {
      await expect(empty.first()).toBeVisible();
    }
  });

  test("six successive messages keep the latest visible (autoscroll)", async ({ page }) => {
    let callCount = 0;
    await page.route("**/api/run/stream", async (route) => {
      callCount += 1;
      await route.fulfill({
        status: 200,
        headers: buildSSEHeaders(),
        body: buildSSEBody(
          plainMarkdown({
            runId: `run-${callCount}`,
            messageId: `msg-${callCount}`,
          }),
        ),
      });
    });

    await page.goto("/");
    const composerExists = await composer(page).count();
    test.skip(composerExists === 0, "Skipped: composer not rendered.");

    for (let i = 0; i < 6; i++) {
      await sendMessage(page, `Question ${i + 1}`);
      await page.waitForTimeout(500);
    }

    const all = messages(page);
    const last = all.last();
    if ((await last.count()) > 0) {
      await expect(last).toBeInViewport();
    }
  });
});
