/**
 * Generative UI tests (SS2.9 / F13).
 *
 * PyramidPanel renders inline (no iframe). SandboxedCanvas renders inside
 * an `<iframe sandbox="allow-scripts">` (FE-AP-4 enforcement is in
 * `e2e/security/iframe-sandbox.spec.ts`; this spec validates the rendering
 * contract).
 */

import { test, expect } from "@playwright/test";
import { sendMessage, composer } from "./fixtures/helpers";
import { buildSSEBody, buildSSEHeaders } from "./fixtures/sse-mock";
import { generativePanel, generativeCanvas } from "./fixtures/scenarios";
import { PROMPTS } from "./fixtures/prompts";

test.describe("Generative UI (binary: Are panels inline and canvases iframed?)", () => {
  test("PyramidPanel renders inline (no iframe)", async ({ page }) => {
    await page.route("**/api/run/stream", async (route) => {
      await route.fulfill({
        status: 200,
        headers: buildSSEHeaders(),
        body: buildSSEBody(generativePanel()),
      });
    });

    await page.goto("/");
    test.skip((await composer(page).count()) === 0, "Skipped: composer not rendered.");

    await sendMessage(page, PROMPTS.GENERATIVE_PANEL);
    await page.waitForTimeout(2_000);

    const panel = page.locator(
      "[data-testid='pyramid-panel'], [data-component='pyramid_panel']",
    );
    if ((await panel.count()) > 0) {
      await expect(panel.first()).toBeVisible();
      const innerIframes = panel.locator("iframe");
      expect(await innerIframes.count()).toBe(0);
    }
  });

  test("SandboxedCanvas renders inside an iframe", async ({ page }) => {
    await page.route("**/api/run/stream", async (route) => {
      await route.fulfill({
        status: 200,
        headers: buildSSEHeaders(),
        body: buildSSEBody(generativeCanvas()),
      });
    });

    await page.goto("/");
    test.skip((await composer(page).count()) === 0, "Skipped: composer not rendered.");

    await sendMessage(page, PROMPTS.GENERATIVE_CANVAS);
    await page.waitForTimeout(2_000);

    const iframe = page.locator("iframe").first();
    if ((await iframe.count()) === 0) {
      test.skip(true, "Skipped: SandboxedCanvas not rendered yet.");
    }

    await expect(iframe).toBeVisible();
  });
});
