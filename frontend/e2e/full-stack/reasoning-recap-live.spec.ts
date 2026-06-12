/**
 * Phase 2 live GCP smoke — F10 Tier-2 reasoning recap end-to-end.
 *
 * Plan: docs/plans/critical_path_smoke_testing.plan.md §Phase 2.
 *
 * Two real runs against a deployed target:
 * 1. Quick smoke — a prompt that forces ≥2 tool calls (write a file,
 *    then read it back) so the recap cost guard (`len(tool_results) >= 2`)
 *    admits the run. Asserts the three Phase 2 criteria: terminal
 *    `data-state="complete"`, ≥1 tool card, and a non-empty
 *    `[data-testid='reasoning-summary']` recap.
 * 2. L2 planning stress — a τ-bench-style three-turn conversation with a
 *    mid-task revision; asserts every turn completes, ≥6 tool cards with
 *    zero errored, and ≥1 recap.
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

/**
 * Send one user turn and wait for ITS assistant message to settle.
 * `.last()` alone races on multi-turn threads: until the new assistant
 * message mounts, `.last()` still points at the previous (already
 * complete) turn — so anchor on the message index instead.
 */
async function runTurn(
  page: import("@playwright/test").Page,
  text: string,
  timeoutMs = 150_000,
): Promise<void> {
  const messages = page.locator("[data-testid='assistant-message']");
  const before = await messages.count();
  await sendMessage(page, text);
  await expect(messages.nth(before)).toHaveAttribute("data-state", "complete", {
    timeout: timeoutMs,
  });
}

/**
 * Pass/fail evidence screenshot: saved to SCREENSHOT_DIR and attached.
 * Tool cards and the reasoning expander are force-opened first so the
 * capture shows every tool's input/output — on failures this is the
 * difference between seeing "file_io errored" and seeing the actual
 * error payload.
 */
async function captureEvidence(
  page: import("@playwright/test").Page,
  outcome: "pass" | "fail",
  basename = "recap-live",
): Promise<string> {
  await page
    .$$eval(
      "details[data-testid='tool-card'], details[data-testid='reasoning-summary']",
      (els) => els.forEach((el) => ((el as HTMLDetailsElement).open = true)),
    )
    .catch(() => {});
  // Long unbroken JSON lines in expanded <pre> blocks push the cards past
  // the viewport's right edge, and full-page screenshots cannot capture
  // horizontal overflow — wrap them (capture-only) so no payload text is
  // cut off in the evidence. Set styles via the CSSOM, not addStyleTag:
  // the deployed target's strict CSP (nonce-only style-src) silently
  // blocks injected <style> tags.
  await page
    .$$eval(
      "[data-testid='tool-card'] pre, [data-testid='reasoning-summary'] p",
      (els) =>
        els.forEach((el) => {
          const s = (el as HTMLElement).style;
          s.whiteSpace = "pre-wrap";
          s.wordBreak = "break-word";
        }),
    )
    .catch(() => {});
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
  const name = outcome === "fail" ? `${basename}_FAILED.png` : `${basename}.png`;
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

  // L2 planning stress test (τ-bench-style): long-horizon plan spread
  // over three user turns in ONE thread, including a mid-task revision —
  // the turn shape where naive ReAct agents and checkpointer state
  // continuity break down. Component-level check: a minimum tool-card
  // count with zero errored cards proves the plan actually executed
  // multi-step instead of the model narrating its way out.
  test("L2 planning stress: multi-turn pipeline with mid-task revision", async ({
    authenticatedPage: page,
  }) => {
    test.setTimeout(420_000);

    // 3 writes + 3 read-backs (turn 1), 2 more writes + verify (turn 2),
    // re-reads (turn 3). 6 is the conservative floor across model variance.
    const MIN_TOOL_CARDS = 6;

    try {
      await page.goto("/");

      // Turn 1 — the plan: parallel file pipeline.
      await runTurn(
        page,
        "Plan and execute this step by step: create three inventory files " +
          "in /workspace/stress/ — apples.txt containing only the number 12, " +
          "bananas.txt containing only 7, cherries.txt containing only 31. " +
          "Then read each file back to verify its contents.",
      );

      // Turn 2 — non-collaborative mid-task revision (τ-bench stressor):
      // changes a requirement from turn 1 and extends the plan.
      await runTurn(
        page,
        "Change of plan: bananas should be 9, not 7 — fix that file. " +
          "Also add dates.txt containing only 5. Verify both files.",
      );

      // Turn 3 — continuation that only makes sense with turn-1/2 state.
      await runTurn(
        page,
        "Now read all four inventory files back and report each value.",
      );

      const toolCards = page.locator("[data-testid='tool-card']");
      const total = await toolCards.count();
      expect(total).toBeGreaterThanOrEqual(MIN_TOOL_CARDS);

      // Zero errored tool calls across the whole conversation.
      const errored = await page
        .locator("[data-testid='tool-card'][data-status='errored']")
        .count();
      expect(errored).toBe(0);

      // Cross-turn continuity: the turn-2 revision (bananas 7 -> 9) must
      // be visible in the LAST read of bananas.txt. Tool outputs report
      // success even when an overwrite silently fails to stick (seen live
      // 2026-06-12: write "9" succeeded, reads kept returning "7"), so
      // anchor on the read-back payload, not on success flags or prose.
      const lastBananaRead = toolCards
        .filter({ hasText: '"operation": "read"' })
        .filter({ hasText: "bananas.txt" })
        .last();
      await expect(lastBananaRead).toContainText('"content":"9"');

      // At least one turn was multi-tool, so at least one recap rendered.
      const recaps = page.locator("[data-testid='reasoning-summary']");
      expect(await recaps.count()).toBeGreaterThanOrEqual(1);

      await captureEvidence(page, "pass", "stress-live");
    } catch (err) {
      await captureEvidence(page, "fail", "stress-live").catch(() => {});
      throw err;
    }
  });
});
