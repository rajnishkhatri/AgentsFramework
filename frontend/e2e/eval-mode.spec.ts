/**
 * Eval-mode capture surface tests (eval-UI F7 + F5/F6). T1: with
 * `?eval=GJ-F-008` the case id is pinned, the trace chip surfaces the
 * forwarded trace_id, and the model badge renders from the
 * /selected_model state delta.
 */

import { test, expect } from "@playwright/test";
import { sendMessage, composer } from "./fixtures/helpers";
import { buildSSEBody, buildSSEHeaders } from "./fixtures/sse-mock";
import { plainMarkdown } from "./fixtures/scenarios";
import type { AGUIEvent } from "../lib/wire/ag_ui_events";

const TRACE = "trace-eval-0001";

function withModelDelta(events: ReadonlyArray<AGUIEvent>): AGUIEvent[] {
  const [first, ...rest] = events;
  const delta: AGUIEvent = {
    type: "STATE_DELTA",
    delta: [{ op: "replace", path: "/selected_model", value: "haiku-tier" }],
    raw_event: { trace_id: TRACE },
  };
  return [first!, delta, ...rest];
}

test.describe("Eval mode (binary: Are captures pinned, traced, and badged?)", () => {
  test.beforeEach(async ({ page }) => {
    await page.route("**/api/run/stream", async (route) => {
      await route.fulfill({
        status: 200,
        headers: buildSSEHeaders(),
        body: buildSSEBody(withModelDelta(plainMarkdown({ traceId: TRACE }))),
      });
    });
    await page.goto("/?eval=GJ-F-008");
  });

  test("pins the case id and surfaces the copyable trace chip", async ({ page }) => {
    test.skip((await composer(page).count()) === 0, "Skipped: composer not rendered.");

    await expect(page.locator("[data-testid='eval-banner']")).toContainText(
      "GJ-F-008",
    );

    await sendMessage(page, "moon facts");
    const message = page.locator("[data-testid='assistant-message']");
    await expect(message).toHaveAttribute("data-state", "complete", {
      timeout: 10_000,
    });

    // F6: the chip shows the backend-forwarded trace id, never invented.
    await expect(page.locator("[data-testid='trace-chip']")).toContainText(TRACE);
    // F5: the model badge renders from the /selected_model delta.
    await expect(page.locator("[data-testid='model-badge']")).toHaveText(
      "haiku-tier",
    );
    // D-A: eval mode renders the status surface without animation classes.
    expect(await page.locator(".animate-pulse").count()).toBe(0);
  });

  test("without ?eval the banner and trace chip stay hidden (prod stays clean)", async ({
    page,
  }) => {
    await page.goto("/");
    test.skip((await composer(page).count()) === 0, "Skipped: composer not rendered.");

    await sendMessage(page, "moon facts");
    await expect(
      page.locator("[data-testid='assistant-message']"),
    ).toHaveAttribute("data-state", "complete", { timeout: 10_000 });

    expect(await page.locator("[data-testid='eval-banner']").count()).toBe(0);
    expect(await page.locator("[data-testid='trace-chip']").count()).toBe(0);
  });
});
