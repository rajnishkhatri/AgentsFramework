/**
 * Tier 3 full-stack -- TTFT p50 benchmark (SS2.14).
 *
 * Measures time from message submit to first response token paint across
 * 5 runs and asserts the median is below the SS2.14 threshold (500ms).
 *
 * The single-measurement check in `e2e/smoke.spec.ts` uses a generous 2000ms
 * cap to absorb cold starts; this spec computes a p50 from 5 warm runs and
 * is suitable for release-gate sign-off.
 */

import { test, expect } from "../fixtures/auth.fixture";
import { sendMessage, waitForResponse } from "../fixtures/helpers";
import { PROMPTS } from "../fixtures/prompts";

const RUNS = 5;
const TTFT_P50_THRESHOLD_MS = 500;

test.describe("T3 TTFT benchmark (binary: Is TTFT p50 < 500ms?)", () => {
  test.skip(
    process.env.MOCK_MIDDLEWARE === "1",
    "Skipped: T3 benchmark requires the real backend (unset MOCK_MIDDLEWARE).",
  );

  test(`p50 of ${RUNS} runs is below ${TTFT_P50_THRESHOLD_MS}ms`, async ({ authenticatedPage: page }) => {
    test.setTimeout(120_000);

    await page.goto("/");

    const measurements: number[] = [];
    for (let i = 0; i < RUNS; i++) {
      const start = Date.now();
      await sendMessage(page, PROMPTS.TTFT_SHORT);
      await waitForResponse(page);
      measurements.push(Date.now() - start);
      await page.waitForTimeout(2_000);
    }

    measurements.sort((a, b) => a - b);
    const p50 = measurements[Math.floor(measurements.length / 2)]!;
    console.log(`[TTFT] runs=${measurements.join(",")} p50=${p50}ms`);

    expect(p50, `TTFT p50 (${p50}ms) must be < ${TTFT_P50_THRESHOLD_MS}ms`).toBeLessThan(
      TTFT_P50_THRESHOLD_MS,
    );
  });
});
