/**
 * trace_id provenance (SS3.5 / FE-AP-7 auto-reject).
 *
 * The browser must NEVER generate a trace_id. The Python runtime mints
 * trace_id and the frontend forwards it verbatim through every layer.
 *
 * This spec asserts the negative: outbound request bodies to /api/run/stream
 * contain no `trace_id` field. The positive (response carries trace_id) is
 * covered by `e2e/integration/bff-stream-proxy.spec.ts` (T2).
 */

import { test, expect } from "@playwright/test";
import { sendMessage } from "../fixtures/helpers";
import { buildSSEBody, buildSSEHeaders } from "../fixtures/sse-mock";
import { plainMarkdown } from "../fixtures/scenarios";
import { PROMPTS } from "../fixtures/prompts";

test.describe("trace_id provenance (binary: Is trace_id generated server-side?)", () => {
  test("no /api/* request body contains a client-generated trace_id", async ({ page }) => {
    const offendingRequests: { url: string; body: string }[] = [];

    page.on("request", (req) => {
      if (!req.url().includes("/api/")) return;
      const body = req.postData();
      if (body && /"trace_id"\s*:/.test(body)) {
        offendingRequests.push({ url: req.url(), body });
      }
    });

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
    await page.waitForTimeout(2_000);

    expect(
      offendingRequests,
      `Browser-generated trace_id detected in: ${JSON.stringify(offendingRequests)}`,
    ).toEqual([]);
  });
});
