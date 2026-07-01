/**
 * PreAct Coach surface with a mocked SSE stream (T1).
 *
 * The Coach rides the CHAT runtime and streams from `/api/coach/run/stream`
 * (design §7 divergence #1). Phase-2 backend flags are OFF, so there is no live
 * coach persona — this spec mocks the route with a canned Socratic transcript
 * (`coach_transcript.ts`) so the surface is walkable and video-recorded without a
 * backend. Because the coach stream route is fully intercepted, the real BFF
 * handler (and its WorkOS auth) never runs.
 *
 * Asserts STRUCTURE + PROVENANCE, not exact prose: a coach turn streamed into the
 * single `role="log"` region, the typing indicator appeared and then cleared
 * (FR-F3/F4 — retry, never a stuck spinner), and the reply is Socratic (never an
 * answer key).
 */

import { test, expect } from "@playwright/test";
import { buildSSEBody, buildSSEHeaders } from "../fixtures/sse-mock";
import { coachTurn, COACH_TURN_1_TEXT } from "../fixtures/coach_transcript";

test.describe("PreAct Coach (mocked SSE)", () => {
  test("a learner ask streams a Socratic reply into the coach log", async ({ page }) => {
    await page.route("**/api/coach/run/stream", async (route) => {
      await route.fulfill({
        status: 200,
        headers: buildSSEHeaders(),
        body: buildSSEBody(coachTurn()),
      });
    });

    await page.goto("/learn/coach");

    const log = page.locator("[role='log']");
    await expect(log).toBeVisible();

    // The coach composer is the shared chat Composer (a textarea).
    const composer = page.locator("textarea").first();
    await expect(composer).toBeVisible({ timeout: 10_000 });
    await composer.fill("Why is B correct here?");
    await composer.press("Enter");

    // The streamed reply settles into the log region (structure, not exact prose).
    await expect(log).toContainText("what job is that comma doing", { timeout: 10_000 });
    // Provenance: the reply is Socratic — it never states the answer letter.
    await expect(log).not.toContainText(/the answer is [A-D]/i);
    // A full-turn sanity check on the reassembled text.
    await expect(log).toContainText(COACH_TURN_1_TEXT.slice(0, 24));

    // FR-F3/F4: the typing indicator is transient — it must not be stuck after
    // the terminal RUN_FINISHED (no infinite spinner).
    await expect(page.locator("[data-testid='coach-typing']")).toHaveCount(0, {
      timeout: 10_000,
    });
  });
});
