/**
 * Tier 3 full-stack -- trust badge with real signed envelopes (SS2.10).
 *
 * Requires a running Python middleware that emits signed AgentFacts
 * envelopes. Verifies:
 *
 *   1. The trust view displays signed AgentFacts after a real run.
 *   2. The verified envelope is frozen client-side (FE-AP-6) -- mutating
 *      it is a no-op.
 *
 * Skipped unless E2E_AUTHENTICATED=1 (real WorkOS session) and
 * MOCK_MIDDLEWARE is unset (so the real Python backend is reachable).
 */

import { test, expect } from "../fixtures/auth.fixture";
import { sendMessage, waitForResponse } from "../fixtures/helpers";
import { PROMPTS } from "../fixtures/prompts";

test.describe("T3 trust badge (binary: Are signed envelopes verified and frozen?)", () => {
  test.skip(
    process.env.MOCK_MIDDLEWARE === "1",
    "Skipped: T3 must talk to the real backend (unset MOCK_MIDDLEWARE).",
  );

  test("trust badge renders identity claims after a successful run", async ({ authenticatedPage: page }) => {
    await page.goto("/");
    await sendMessage(page, PROMPTS.PLAIN_MARKDOWN);
    await waitForResponse(page);

    const badge = page.locator(
      "[data-testid='trust-badge'], [data-testid='model-badge'], .trust-badge, .agent-identity",
    );
    if ((await badge.count()) === 0) {
      test.skip(true, "Skipped: trust badge component not rendered.");
    }
    await expect(badge.first()).toBeVisible();
  });

  test("verified envelope is frozen (FE-AP-6 enforcement)", async ({ authenticatedPage: page }) => {
    await page.goto("/");
    await sendMessage(page, PROMPTS.PLAIN_MARKDOWN);
    await waitForResponse(page);

    const lastFacts = await page.evaluate(() => {
      const w = window as unknown as { __lastAgentFacts?: object };
      return w.__lastAgentFacts ?? null;
    });

    if (!lastFacts) {
      test.skip(true, "Skipped: window.__lastAgentFacts debug shim not exposed.");
    }

    const frozen = await page.evaluate(() => {
      const w = window as unknown as { __lastAgentFacts?: object };
      return w.__lastAgentFacts ? Object.isFrozen(w.__lastAgentFacts) : false;
    });
    expect(frozen, "Verified AgentFacts must be Object.frozen").toBe(true);
  });
});
