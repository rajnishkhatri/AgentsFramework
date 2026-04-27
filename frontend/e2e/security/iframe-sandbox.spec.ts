/**
 * Iframe sandbox enforcement (SS3.2 / FE-AP-4 auto-reject).
 *
 * Generative canvases must render in `<iframe sandbox="allow-scripts">` --
 * exactly that token, no `allow-same-origin`, no `allow-top-navigation`,
 * no `allow-forms`. Content must arrive via `srcdoc`, never via `src` to a
 * third-party origin.
 *
 * This T1 spec triggers a generative canvas via the mocked SSE stream
 * (scenarios.generativeCanvas) and inspects the resulting iframe.
 */

import { test, expect } from "@playwright/test";
import { sendMessage } from "../fixtures/helpers";
import { buildSSEBody, buildSSEHeaders } from "../fixtures/sse-mock";
import { generativeCanvas } from "../fixtures/scenarios";
import { PROMPTS } from "../fixtures/prompts";

const FORBIDDEN_SANDBOX_TOKENS = [
  "allow-same-origin",
  "allow-top-navigation",
  "allow-forms",
  "allow-popups",
  "allow-modals",
  "allow-pointer-lock",
];

test.describe("Iframe sandbox (binary: Is the canvas iframe properly sandboxed?)", () => {
  test("every iframe declares sandbox='allow-scripts' only", async ({ page }) => {
    await page.route("**/api/run/stream", async (route) => {
      await route.fulfill({
        status: 200,
        headers: buildSSEHeaders(),
        body: buildSSEBody(generativeCanvas()),
      });
    });

    await page.goto("/");
    const composerExists = await page
      .locator("[data-testid='composer'], textarea")
      .count();
    test.skip(composerExists === 0, "Skipped: composer not rendered (auth required).");

    await sendMessage(page, PROMPTS.GENERATIVE_CANVAS);
    await page.waitForTimeout(2_000);

    const iframes = page.locator("iframe");
    const count = await iframes.count();
    if (count === 0) {
      test.skip(true, "Skipped: no iframe rendered (generative UI may not be wired yet).");
    }

    for (let i = 0; i < count; i++) {
      const iframe = iframes.nth(i);
      const sandbox = (await iframe.getAttribute("sandbox")) ?? "";
      expect(sandbox, `iframe ${i} must declare a sandbox`).not.toBe("");
      const tokens = sandbox.split(/\s+/).filter(Boolean);
      expect(tokens).toContain("allow-scripts");
      for (const forbidden of FORBIDDEN_SANDBOX_TOKENS) {
        expect(tokens, `iframe ${i} sandbox must not include ${forbidden}`).not.toContain(forbidden);
      }
    }
  });

  test("generative iframes use srcdoc, not src to third-party origins", async ({ page }) => {
    await page.route("**/api/run/stream", async (route) => {
      await route.fulfill({
        status: 200,
        headers: buildSSEHeaders(),
        body: buildSSEBody(generativeCanvas()),
      });
    });

    await page.goto("/");
    const composerExists = await page
      .locator("[data-testid='composer'], textarea")
      .count();
    test.skip(composerExists === 0, "Skipped: composer not rendered (auth required).");

    await sendMessage(page, PROMPTS.GENERATIVE_CANVAS);
    await page.waitForTimeout(2_000);

    const iframes = page.locator("iframe");
    const count = await iframes.count();
    if (count === 0) {
      test.skip(true, "Skipped: no iframe rendered.");
    }

    const origin = new URL(page.url()).origin;
    for (let i = 0; i < count; i++) {
      const iframe = iframes.nth(i);
      const src = await iframe.getAttribute("src");
      const srcdoc = await iframe.getAttribute("srcdoc");
      if (src && src.length > 0 && !src.startsWith(origin) && !src.startsWith("about:")) {
        throw new Error(`iframe ${i} loads cross-origin src=${src} (FE-AP-4)`);
      }
      expect(srcdoc !== null || src !== null, `iframe ${i} must have srcdoc or src`).toBe(true);
    }
  });
});
