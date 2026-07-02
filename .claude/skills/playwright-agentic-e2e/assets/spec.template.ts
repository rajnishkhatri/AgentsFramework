/**
 * spec template — a tiered spec skeleton for an agent chat app.
 *
 * Pick ONE tier per file (or per describe). The imports and guards differ:
 *   - T1 mocked: import from "@playwright/test", mock the stream via page.route.
 *   - T3 full-stack: import { test, expect } from the auth fixture, use
 *     { authenticatedPage }, and require a real backend.
 *
 * Delete the tier you don't use.
 */

/* =========================================================================
 * TIER 1 — mocked stream (deterministic, CI-safe, no auth)
 * ========================================================================= */
import { test as t1Test, expect as t1Expect } from "@playwright/test";
import { sendMessage, waitForResponse } from "../fixtures/helpers";

// Minimal canned SSE — replace with your event scenarios.
function buildSSEBody(events: unknown[]): string {
  return events.map((e) => `data: ${JSON.stringify(e)}\n\n`).join("");
}
function buildSSEHeaders(): Record<string, string> {
  return {
    "Content-Type": "text/event-stream",
    "Cache-Control": "no-cache, no-transform",
    "X-Accel-Buffering": "no",
    Connection: "keep-alive",
  };
}

t1Test.describe("chat shell (T1, mocked)", () => {
  t1Test("renders an assistant reply from a mocked stream", async ({ page }) => {
    await page.route("**/api/run/stream", async (route) => {
      await route.fulfill({
        status: 200,
        headers: buildSSEHeaders(),
        body: buildSSEBody([
          { type: "RUN_STARTED" },
          { type: "TEXT_MESSAGE_CONTENT", delta: "Hello " },
          { type: "TEXT_MESSAGE_CONTENT", delta: "world." },
          { type: "RUN_FINISHED" },
        ]),
      });
    });

    await page.goto("/");
    await sendMessage(page, "say hello");
    const reply = await waitForResponse(page, { timeoutMs: 15_000 });

    // Assert STRUCTURE, not exact prose.
    t1Expect(((await reply.textContent()) ?? "").trim().length).toBeGreaterThan(0);
  });
});

/* =========================================================================
 * TIER 3 — full-stack against a real backend (on-demand; needs auth)
 * ========================================================================= */
import { test as t3Test, expect as t3Expect } from "../fixtures/auth.fixture";
import { sendMessage as t3Send, waitForResponse as t3Wait } from "../fixtures/helpers";

t3Test.describe("chat (T3, full-stack)", () => {
  // Don't run against a mock backend; require the real one.
  t3Test.skip(process.env.MOCK_MIDDLEWARE === "1", "Requires real backend.");

  t3Test("a real agent reply renders", async ({ authenticatedPage: page }) => {
    t3Test.setTimeout(180_000); // live agents can be slow

    await page.goto("/");
    await t3Send(page, "What files are in the project root?");
    const reply = await t3Wait(page, { timeoutMs: 150_000 });

    const text = ((await reply.textContent()) ?? "").trim();
    // Provenance / structure / bounded-content — never exact wording.
    t3Expect(text.length).toBeGreaterThan(0);
    // e.g. a loose semantic check rather than a verbatim listing:
    // t3Expect(text).toMatch(/\b(file|directory|folder)\b/i);
  });
});
