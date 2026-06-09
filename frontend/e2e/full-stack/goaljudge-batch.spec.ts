/**
 * Tier 3 — GoalJudge registry prompt injection against a hosted frontend (G1).
 *
 * Drives each case prompt through the real chat composer on Cloud Run (or any
 * BASE_URL). On-demand only; requires WorkOS credentials.
 *
 * Plan: docs/plans/goaljudge_gcp_playwright_batch.plan.md
 *
 * Prerequisites:
 *   BASE_URL=https://agent-frontend-w65nrxwkiq-uc.a.run.app
 *   E2E_AUTHENTICATED=1
 *   E2E_USER_EMAIL + E2E_USER_PASSWORD (or E2E_USER_OTP)
 *
 * Optional:
 *   GJ_CASE_FILTER=GJ-010     — single case
 *   GOALJUDGE_BATCH_MODE=pilot — 43-case Stage 5 pilot (default: walkthrough, 22 cases)
 *   GOALJUDGE_BATCH_LIMIT=5   — cap batch size
 *   GOALJUDGE_BATCH_JSONL     — override JSONL output path
 *   GOALJUDGE_BATCH_SCREENSHOT_DIR — override screenshot output dir
 *
 * JSONL schema (one row per case):
 *   case_id, trace_id, session_id, target_code, target_axes, prompt,
 *   thread_title, response_text, tool_card_count, screenshot_path,
 *   outcome ("pass" | "fail"), error (fail only), finished_at, base_url
 *
 * Screenshots: pass → {caseId}.png, fail → {caseId}_FAILED.png
 */

import fs from "node:fs";
import path from "node:path";
import { test, expect } from "../fixtures/auth.fixture";
import {
  sendMessage,
  waitForResponse,
  waitForComposerReady,
} from "../fixtures/helpers";
import { filterCases } from "../fixtures/goaljudge_registry";

const CASES = filterCases({
  caseFilter: process.env.GJ_CASE_FILTER,
  limit: process.env.GOALJUDGE_BATCH_LIMIT
    ? Number(process.env.GOALJUDGE_BATCH_LIMIT)
    : undefined,
});

const OUTPUT_JSONL =
  process.env.GOALJUDGE_BATCH_JSONL ??
  path.join(process.cwd(), "..", "cache", "goaljudge_eval", "ui_batch.jsonl");

const OUTPUT_SCREENSHOT_DIR =
  process.env.GOALJUDGE_BATCH_SCREENSHOT_DIR ??
  path.join(path.dirname(OUTPUT_JSONL), "ui_batch_screenshots");

const REPO_ROOT = path.resolve(process.cwd(), "..");

function appendCapture(row: Record<string, unknown>): void {
  const dir = path.dirname(OUTPUT_JSONL);
  fs.mkdirSync(dir, { recursive: true });
  fs.appendFileSync(OUTPUT_JSONL, `${JSON.stringify(row)}\n`, "utf8");
}

function screenshotAbsPath(caseId: string, outcome: "pass" | "fail"): string {
  const suffix = outcome === "fail" ? "_FAILED" : "";
  return path.join(OUTPUT_SCREENSHOT_DIR, `${caseId}${suffix}.png`);
}

/** Repo-relative path when the screenshot lives under the workspace root. */
function screenshotRelPath(absPath: string): string {
  const resolved = path.resolve(absPath);
  if (resolved.startsWith(`${REPO_ROOT}${path.sep}`)) {
    return path.relative(REPO_ROOT, resolved);
  }
  return resolved;
}

async function captureCaseScreenshot(
  page: import("@playwright/test").Page,
  caseId: string,
  outcome: "pass" | "fail",
): Promise<string> {
  fs.mkdirSync(OUTPUT_SCREENSHOT_DIR, { recursive: true });
  const absPath = screenshotAbsPath(caseId, outcome);
  const attachName = path.basename(absPath);
  const buffer = await page.screenshot({ fullPage: true });
  fs.writeFileSync(absPath, buffer);
  await test.info().attach(attachName, {
    body: buffer,
    contentType: "image/png",
  });
  return screenshotRelPath(absPath);
}

async function newThreadIfAvailable(page: import("@playwright/test").Page): Promise<void> {
  const btn = page.locator(
    "[data-testid='new-thread'], button:has-text('New chat'), button:has-text('New')",
  );
  if ((await btn.count()) > 0) {
    await btn.first().click();
  }
}

/**
 * Rewrite outbound /api/run/stream bodies so thread_id encodes the registry
 * join key as ``gj:{case_id}:{trace_id}``. Middleware derives deterministic
 * trace_id server-side (FE-AP-7: no client ``trace_id`` field).
 */
function installGoalJudgeThreadBridge(
  page: import("@playwright/test").Page,
  caseRow: { id: string; trace_id: string },
): void {
  const gjThreadId = `gj:${caseRow.id}:${caseRow.trace_id}`;
  page.route("**/api/run/stream", async (route) => {
    const request = route.request();
    const raw = request.postData() ?? "{}";
    let body: Record<string, unknown>;
    try {
      body = JSON.parse(raw) as Record<string, unknown>;
    } catch {
      await route.continue();
      return;
    }
    if ("trace_id" in body) {
      throw new Error("goaljudge batch must not send client-generated trace_id");
    }
    body.thread_id = gjThreadId;
    await route.continue({
      postData: JSON.stringify(body),
      headers: {
        ...request.headers(),
        "content-type": "application/json",
      },
    });
  });
}

test.describe("GoalJudge GCP batch (L4: registry prompt injection)", () => {
  test.skip(
    process.env.MOCK_MIDDLEWARE === "1",
    "Requires real backend — unset MOCK_MIDDLEWARE.",
  );

  test.skip(
    CASES.length === 0,
    "No cases — run export_goaljudge_registry_json.py and check GJ_CASE_FILTER.",
  );

  for (const caseRow of CASES) {
    test(`inject ${caseRow.id} (${caseRow.target_code})`, async ({ authenticatedPage: page }) => {
      test.setTimeout(180_000);

      installGoalJudgeThreadBridge(page, caseRow);

      const title = `gj:${caseRow.id}:${caseRow.trace_id}`;
      let responseText = "";
      let toolCardCount = 0;

      try {
        await page.goto("/");
        await newThreadIfAvailable(page);

        await sendMessage(page, caseRow.prompt);
        // Source of truth is the settled response text (see waitForResponse):
        // some Cloud Run runs never disable the composer / never render an
        // answer, so we cannot gate on composer state. waitForComposerReady
        // afterward is a soft confirmation only.
        const response = await waitForResponse(page, { timeoutMs: 150_000 });
        await waitForComposerReady(page, { timeoutMs: 5_000 }).catch(() => {});

        responseText = (await response.textContent()) ?? "";
        expect(responseText.length).toBeGreaterThan(0);

        const toolCards = page.locator("[data-testid='tool-card'], .tool-card");
        toolCardCount = await toolCards.count();

        const screenshotPath = await captureCaseScreenshot(page, caseRow.id, "pass");

        appendCapture({
          case_id: caseRow.id,
          trace_id: caseRow.trace_id,
          session_id: caseRow.session_id,
          target_code: caseRow.target_code,
          target_axes: caseRow.target_axes,
          prompt: caseRow.prompt,
          thread_title: title,
          response_text: responseText.slice(0, 4000),
          tool_card_count: toolCardCount,
          screenshot_path: screenshotPath,
          outcome: "pass",
          finished_at: new Date().toISOString(),
          base_url: process.env.BASE_URL ?? "http://localhost:3000",
        });
      } catch (err) {
        let screenshotPath: string | undefined;
        try {
          screenshotPath = await captureCaseScreenshot(page, caseRow.id, "fail");
        } catch {
          // Page may be closed; still record the failure row.
        }

        const errorMessage = err instanceof Error ? err.message : String(err);
        appendCapture({
          case_id: caseRow.id,
          trace_id: caseRow.trace_id,
          session_id: caseRow.session_id,
          target_code: caseRow.target_code,
          target_axes: caseRow.target_axes,
          prompt: caseRow.prompt,
          thread_title: title,
          response_text: responseText.slice(0, 4000),
          tool_card_count: toolCardCount,
          screenshot_path: screenshotPath,
          outcome: "fail",
          error: errorMessage,
          finished_at: new Date().toISOString(),
          base_url: process.env.BASE_URL ?? "http://localhost:3000",
        });
        throw err;
      }
    });
  }
});
