/**
 * Tier 1 (mocked, CI-safe) — memory multi-session WIRING guard.
 *
 * This is the cheap per-commit guard for the memory_recalled wire chain:
 *   CUSTOM `memory_recalled` (SSE)  →  ag_ui translator  →  reducer field
 *   →  RecallIndicator ("Recalled N memories about you")
 *
 * It does NOT prove real cross-session recall — that's the T3 job
 * (memory-multisession.spec.ts, on-demand against the live mem revision). It
 * proves the transport + translation + render chain doesn't regress, with no
 * model call and no network.
 *
 * Two mocked runs share a user (one browser session). The first run "seeds"
 * (a plain answer); the second emits `memory_recalled` count=1 and we assert the
 * indicator lights up. Failure path first: count=0 must render NO indicator
 * (the precision guard — a no-hit/memory-off run stays quiet).
 *
 * page.route intercepts `fetch()` (the BFF SSE is read over fetch+ReadableStream
 * via connectFetchSSE — NOT EventSource), so T1 browser-level mocking works here
 * (skill: the stream_transport field is the one that silently breaks T1 if it's
 * EventSource). Plan: docs/plans/memory_multisession_e2e_stress.plan.md §4.1.
 */

import { test, expect } from "@playwright/test";
import { sendMessage, composer } from "../fixtures/helpers";
import { buildSSEBody, buildSSEHeaders } from "../fixtures/sse-mock";
import type { AGUIEvent } from "../../lib/wire/ag_ui_events";

const TRACE = "mem-t1-trace-0001";
const h = { raw_event: { trace_id: TRACE } };

/** A run that answers, optionally emitting a CUSTOM memory_recalled frame. */
function memoryRun(opts: { recalledCount?: number; answer: string }): ReadonlyArray<AGUIEvent> {
  const runId = "mem-t1-run";
  const threadId = "mem-t1-thread";
  const messageId = "mem-t1-msg";
  const frames: AGUIEvent[] = [
    { type: "RUN_STARTED", run_id: runId, thread_id: threadId, ...h },
    { type: "TEXT_MESSAGE_START", message_id: messageId, role: "assistant", ...h },
    { type: "TEXT_MESSAGE_CONTENT", message_id: messageId, delta: opts.answer, ...h },
    { type: "TEXT_MESSAGE_END", message_id: messageId, ...h },
  ];
  if (opts.recalledCount !== undefined) {
    // memory_recalled rides the AG-UI CUSTOM channel (memory layer Phase 3):
    // name "memory_recalled", value { trace_id, count } — count only, never
    // memory content on the wire.
    frames.push({
      type: "CUSTOM",
      name: "memory_recalled",
      value: { trace_id: TRACE, count: opts.recalledCount },
      ...h,
    });
  }
  frames.push({ type: "RUN_FINISHED", run_id: runId, thread_id: threadId, ...h });
  return frames;
}

async function routeOnce(
  page: import("@playwright/test").Page,
  events: ReadonlyArray<AGUIEvent>,
): Promise<void> {
  await page.unroute("**/api/run/stream").catch(() => {});
  await page.route("**/api/run/stream", async (route) => {
    await route.fulfill({
      status: 200,
      headers: buildSSEHeaders(),
      body: buildSSEBody(events),
    });
  });
}

test.describe("Memory multi-session wiring (T1 mock: recall indicator chain)", () => {
  test("count 0 renders NO recall indicator (failure path first — quiet on no-hit)", async ({
    page,
  }) => {
    await routeOnce(page, memoryRun({ recalledCount: 0, answer: "Here is a summary." }));
    await page.goto("/");
    test.skip((await composer(page).count()) === 0, "composer not rendered");

    await sendMessage(page, "what units do I prefer?");
    await page.waitForTimeout(1_500);

    await expect(page.locator("[data-testid='recall-indicator']")).toHaveCount(0);
  });

  test("a memory_recalled count>=1 lights the recall indicator (the wiring chain)", async ({
    page,
  }) => {
    // Session 1: seed (a plain run, no recall frame).
    await routeOnce(page, memoryRun({ answer: "Noted — you prefer metric units." }));
    await page.goto("/");
    test.skip((await composer(page).count()) === 0, "composer not rendered");
    await sendMessage(page, "Remember I prefer metric units.");
    await page.waitForTimeout(1_000);

    // Session 2 (same browser session / user): recall fires count=1.
    await routeOnce(page, memoryRun({ recalledCount: 1, answer: "I'll use metric units." }));
    await sendMessage(page, "what units should you use?");
    await page.waitForTimeout(1_500);

    const indicator = page.locator("[data-testid='recall-indicator']");
    await expect(indicator).toBeVisible();
    await expect(indicator).toContainText(/recalled\s+1\s+memor/i);
    // The indicator never carries memory CONTENT — only the count.
    await expect(indicator).not.toContainText("metric units");
  });
});
