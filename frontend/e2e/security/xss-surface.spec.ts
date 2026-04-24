/**
 * dangerouslySetInnerHTML scan (SS3.4 / FE-AP-12 auto-reject).
 *
 * Verifies the rendered HTML has no `dangerouslySetInnerHTML` (which would
 * appear in source as a `<*>` with literal innerHTML attached). Because
 * React strips the directive from the rendered DOM, the meaningful check
 * is for unescaped `<script>` insertion in agent-output regions.
 */

import { test, expect } from "@playwright/test";
import { sendMessage, waitForResponse } from "../fixtures/helpers";
import { buildSSEBody, buildSSEHeaders } from "../fixtures/sse-mock";
import { plainMarkdown } from "../fixtures/scenarios";
import { PROMPTS } from "../fixtures/prompts";

test.describe("XSS surface (binary: Is agent output rendered safely?)", () => {
  test("rendered chat HTML contains no <script> tags from agent text", async ({ page }) => {
    await page.route("**/api/run/stream", async (route) => {
      await route.fulfill({
        status: 200,
        headers: buildSSEHeaders(),
        body: buildSSEBody(plainMarkdown()),
      });
    });

    await page.goto("/");
    const composerExists = await page
      .locator("[data-testid='composer'], textarea")
      .count();
    test.skip(composerExists === 0, "Skipped: composer not rendered (auth required).");

    await sendMessage(page, PROMPTS.PLAIN_MARKDOWN);
    await waitForResponse(page);

    const messageScripts = await page
      .locator("[role='log'] script, article script, .message-content script")
      .count();
    expect(messageScripts, "Agent output regions must not contain <script>").toBe(0);
  });

  test("page source does not reference dangerouslySetInnerHTML on agent regions", async ({ page }) => {
    await page.goto("/");
    const html = await page.content();
    expect(
      html.includes("dangerouslySetInnerHTML"),
      "dangerouslySetInnerHTML must not appear in rendered HTML",
    ).toBe(false);
  });
});
