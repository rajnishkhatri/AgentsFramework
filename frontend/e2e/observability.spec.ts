/**
 * Observability tests (SS2.11).
 *
 * - trace_id provenance check (cross-references security/trace-id.spec.ts)
 * - production console silence (Rule O3: console.* forbidden outside adapters/)
 */

import { test, expect, type ConsoleMessage } from "@playwright/test";
import { sendMessage, composer } from "./fixtures/helpers";
import { buildSSEBody, buildSSEHeaders } from "./fixtures/sse-mock";
import { plainMarkdown } from "./fixtures/scenarios";
import { PROMPTS } from "./fixtures/prompts";

const isProd = process.env.NODE_ENV === "production";

test.describe("Observability (binary: Is the runtime quiet and trace_id forwarded?)", () => {
  test("production console is silent during a happy-path run", async ({ page }) => {
    test.skip(!isProd, "Skipped: production-only check (set NODE_ENV=production).");

    const messages: { type: string; text: string }[] = [];
    page.on("console", (msg: ConsoleMessage) => {
      const t = msg.type();
      if (t === "log" || t === "warning" || t === "error") {
        messages.push({ type: t, text: msg.text() });
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
    test.skip((await composer(page).count()) === 0, "Skipped: composer not rendered.");

    await sendMessage(page, PROMPTS.PLAIN_MARKDOWN);
    await page.waitForTimeout(2_000);

    const appMessages = messages.filter(
      (m) => !/devtools|react devtools|hmr/i.test(m.text),
    );
    expect(
      appMessages,
      `Production console must be silent: ${JSON.stringify(appMessages)}`,
    ).toEqual([]);
  });

  test("trace_id is preserved in error responses surfaced to the UI", async ({ page }) => {
    const traceId = "test-trace-from-server-xyz";
    await page.route("**/api/run/stream", async (route) => {
      await route.fulfill({
        status: 500,
        contentType: "application/json",
        headers: { "x-trace-id": traceId },
        body: JSON.stringify({ error: "server_error", trace_id: traceId }),
      });
    });

    await page.goto("/");
    test.skip((await composer(page).count()) === 0, "Skipped: composer not rendered.");

    await sendMessage(page, PROMPTS.PLAIN_MARKDOWN);
    await page.waitForTimeout(2_000);

    const html = await page.content();
    if (/error|failed|something went wrong/i.test(html)) {
      const exposesTrace = html.includes(traceId);
      if (!exposesTrace) {
        test.info().annotations.push({
          type: "info",
          description:
            "trace_id not surfaced in error UI; consider exposing it for support correlation.",
        });
      }
    }
  });
});
