/**
 * Local full-stack validation — Phase-2 memory AUTOCAPTURE write-back + recall.
 *
 * Mirrors the manual SS-MEM autocapture check: with the backend booted with
 * MEMORY_ENABLED=true + MEMORY_AUTOCAPTURE_ENABLED=true + a passing enable-policy
 * certificate (write-back ON), a fact stated in session 1 is auto-captured and
 * recalled in a FRESH thread (session 2) for the same authenticated owner.
 *
 * On-demand / local only (real model calls + a LOCAL-ONLY synthetic cert). Run:
 *   cd frontend
 *   E2E_AUTHENTICATED=1 BASE_URL=http://localhost:3000 \
 *     pnpm exec playwright test e2e/full-stack/autocapture-recall-local.spec.ts \
 *     --project=chromium-desktop
 *
 * Backend must be up on :8000 with the flags set (cache/local_validation/run_backend.sh).
 *
 * Non-determinism: the ONLY hard assertion is that a non-empty answer rendered
 * AND it surfaces the seeded fact (normalized substring). The recall indicator
 * is a soft cross-check (logged, not asserted) since autocapture is debounced.
 */
import { test, expect } from "../fixtures/auth.fixture";
import { sendMessage, waitForResponse, waitForComposerReady } from "../fixtures/helpers";

const FACT_TOKEN = "Reykjavik"; // a distinctive, unlikely-to-be-guessed token
// Neutral phrasing — a "secret"/"sensitive" framing makes the model refuse to
// store, which suppresses autocapture extraction. A benign preference is stored.
const SEED = `Remember for later: my favorite city to visit is ${FACT_TOKEN}.`;
const PROBE = "Which city do I most like to visit?";

async function newThreadIfAvailable(page: import("@playwright/test").Page): Promise<void> {
  const btn = page.locator(
    "[data-testid='new-thread'], button:has-text('New chat'), button:has-text('New')",
  );
  if ((await btn.count()) > 0) await btn.first().click();
}

test.describe("Autocapture write-back + recall (local full-stack)", () => {
  test.skip(process.env.MOCK_MIDDLEWARE === "1", "Requires the real backend.");

  test("a fact stated in session 1 is recalled in a fresh session 2", async ({
    authenticatedPage: page,
  }) => {
    test.setTimeout(220_000);

    // ── Session 1: state the fact ─────────────────────────────────────
    await page.goto("/");
    await newThreadIfAvailable(page);
    await sendMessage(page, SEED);
    const seedResp = await waitForResponse(page, { timeoutMs: 150_000 });
    await waitForComposerReady(page, { timeoutMs: 5_000 }).catch(() => {});
    const seedText = (await seedResp.textContent()) ?? "";
    expect(seedText.length).toBeGreaterThan(0);

    // autocapture is debounced (~2s) + runs as a post-run background task; give
    // it time to extract + write-back before we open a fresh thread.
    await page.waitForTimeout(8_000);

    // ── Session 2: fresh thread, ask the fact back ────────────────────
    await page.goto("/");
    await newThreadIfAvailable(page);
    await sendMessage(page, PROBE);
    const probeResp = await waitForResponse(page, { timeoutMs: 150_000 });
    await waitForComposerReady(page, { timeoutMs: 5_000 }).catch(() => {});
    const probeText = (await probeResp.textContent()) ?? "";

    // Soft cross-check: did the recall indicator render a count?
    const indicator = page.locator("[data-testid='recall-indicator']");
    const indicatorText =
      (await indicator.count()) > 0 ? (await indicator.first().textContent()) ?? "" : "(none)";
    // eslint-disable-next-line no-console
    console.log(`[autocapture-recall] recall-indicator: ${indicatorText.trim()}`);
    // eslint-disable-next-line no-console
    console.log(`[autocapture-recall] probe answer: ${probeText.slice(0, 240)}`);

    // Hard assertions: a real answer rendered AND it recalled the fact.
    expect(probeText.length).toBeGreaterThan(0);
    expect(probeText.toLowerCase()).toContain(FACT_TOKEN.toLowerCase());
  });
});
