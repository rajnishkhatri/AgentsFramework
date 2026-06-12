/**
 * Phase 2 live GCP smoke — F10 Tier-2 reasoning recap end-to-end.
 *
 * Plan: docs/plans/critical_path_smoke_testing.plan.md §Phase 2.
 *
 * One real run against a deployed target: a prompt that forces ≥2 tool
 * calls (write a file, then read it back) so the recap cost guard
 * (`len(tool_results) >= 2`) admits the run. Asserts the three Phase 2
 * criteria: terminal `data-state="complete"`, ≥1 tool card, and a
 * non-empty `[data-testid='reasoning-summary']` recap.
 *
 * On-demand only; never in per-commit CI. Requires:
 *   BASE_URL=https://agent-frontend-w65nrxwkiq-uc.a.run.app
 *   E2E_AUTHENTICATED=1 (+ WorkOS creds for global-setup)
 */

import fs from "node:fs";
import path from "node:path";
import { test, expect } from "../fixtures/auth.fixture";
import { sendMessage } from "../fixtures/helpers";

const PROMPT =
  "Write the text 'recap smoke 2026-06-12' to a file named recap_smoke.txt, " +
  "then read the file back and confirm its contents.";

const SCREENSHOT_DIR =
  process.env.SMOKE_SCREENSHOT_DIR ??
  path.join(process.cwd(), "smoke-screenshots");

/** Pass/fail evidence screenshot: saved to SCREENSHOT_DIR and attached. */
async function captureEvidence(
  page: import("@playwright/test").Page,
  outcome: "pass" | "fail",
): Promise<string> {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
  const name = outcome === "fail" ? "recap-live_FAILED.png" : "recap-live.png";
  const absPath = path.join(SCREENSHOT_DIR, name);
  const buffer = await page.screenshot({ fullPage: true });
  fs.writeFileSync(absPath, buffer);
  await test.info().attach(name, { body: buffer, contentType: "image/png" });
  return absPath;
}

test.describe("Reasoning recap live smoke (L4: real stack)", () => {
  test.skip(
    process.env.MOCK_MIDDLEWARE === "1",
    "Requires real backend — unset MOCK_MIDDLEWARE.",
  );

  test("2-tool run completes with tool cards and a non-empty recap", async ({
    authenticatedPage: page,
  }) => {
    test.setTimeout(180_000);

    try {
      await page.goto("/");
      await sendMessage(page, PROMPT);

      // Terminal anchor: the assistant message settles to complete (same
      // marker the GoalJudge T3 batch harness waits on).
      const message = page.locator("[data-testid='assistant-message']").last();
      await expect(message).toHaveAttribute("data-state", "complete", {
        timeout: 150_000,
      });

      const toolCards = page.locator("[data-testid='tool-card'], .tool-card");
      expect(await toolCards.count()).toBeGreaterThanOrEqual(1);

      // The recap expander must exist (cost guard admits a ≥2-tool run),
      // stay collapsed by default, and reveal non-empty recap text.
      const expander = page.locator("[data-testid='reasoning-summary']");
      await expect(expander).toBeVisible({ timeout: 10_000 });
      await expect(expander).not.toHaveAttribute("open", "");

      await expander.locator("summary").click();
      const recapText = ((await expander.locator("p").textContent()) ?? "").trim();
      expect(recapText.length).toBeGreaterThan(0);

      await captureEvidence(page, "pass");
    } catch (err) {
      await captureEvidence(page, "fail").catch(() => {});
      throw err;
    }
  });
});
